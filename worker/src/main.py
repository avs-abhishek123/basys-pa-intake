"""Main worker for processing PA document jobs"""
import logging
import asyncio
import time
import sys
from typing import Optional
from src.config import settings
from src.services.database import db_service
from src.services.queue import queue_service, QueueMessage
from src.stages.ocr import ocr_stage, OCRTimeoutError, OCRRetryableError, OCRNonRetryableError
from src.stages.extraction import extraction_stage, ExtractionError, ExtractionValidationError
from src.stages.policy import policy_stage, PolicyEvaluationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s", "module": "%(module)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)


class WorkerMetrics:
    """Worker metrics tracking"""
    
    def __init__(self):
        self.jobs_processed = 0
        self.jobs_failed = 0
        self.jobs_retried = 0
        self.total_processing_time_ms = 0
    
    def log_metrics(self):
        """Log current metrics"""
        avg_time = (
            self.total_processing_time_ms / self.jobs_processed
            if self.jobs_processed > 0
            else 0
        )
        logger.info(
            f"Worker metrics: processed={self.jobs_processed}, "
            f"failed={self.jobs_failed}, retried={self.jobs_retried}, "
            f"avg_time_ms={avg_time:.2f}"
        )


class JobProcessor:
    """Processes individual jobs through all stages"""
    
    def __init__(self):
        self.metrics = WorkerMetrics()
    
    async def process_job(self, message: QueueMessage) -> bool:
        """
        Process a single job through all stages
        
        Returns:
            True if job completed successfully
            False if job should be retried
            Raises exception if job should go to DLQ
        """
        job_id = None
        start_time = time.time()
        
        try:
            # Get job from database
            request_id = message.request_id
            document_id = message.document_id
            trace_id = message.trace_id
            
            logger.info(
                f"Processing job (request_id: {request_id}, "
                f"document_id: {document_id}, trace_id: {trace_id}, "
                f"attempt: {message.attempt_count + 1})"
            )
            
            # Find job in database
            jobs = db_service.execute_query(
                """SELECT job_id FROM core.jobs 
                   WHERE request_id = %s AND document_id = %s 
                   ORDER BY created_at DESC LIMIT 1""",
                (request_id, document_id)
            )
            
            if not jobs:
                raise Exception(f"Job not found for request {request_id}")
            
            job_id = jobs[0]['job_id']
            
            # Mark job as started
            db_service.mark_job_started(job_id)
            db_service.update_job_stage(job_id, 'STARTED', message.attempt_count + 1)
            
            # Check rate limit
            if not queue_service.check_rate_limit():
                logger.warning(f"Rate limit hit, requeuing job {job_id}")
                await asyncio.sleep(1)  # Brief delay before requeue
                return False  # Retry
            
            # Stage A: OCR (mocked)
            db_service.update_job_stage(job_id, 'OCR', message.attempt_count + 1)
            document_text = await self._stage_ocr(document_id, trace_id)
            
            # Stage B: Evidence extraction
            db_service.update_job_stage(job_id, 'EXTRACTION', message.attempt_count + 1)
            extraction_result = await self._stage_extraction(document_text, trace_id)
            
            # Save extracted evidence to PHI schema
            evidence_dict = extraction_result.evidence.model_dump()
            evidence_dict['extraction_metadata'] = extraction_result.extraction_metadata
            db_service.save_extracted_evidence(request_id, document_id, evidence_dict)
            
            # Stage C: Policy evaluation
            db_service.update_job_stage(job_id, 'POLICY_EVALUATION', message.attempt_count + 1)
            policy_decision = await self._stage_policy(extraction_result.evidence, trace_id)
            
            # Stage D: Produce Evidence Pack
            db_service.update_job_stage(job_id, 'EVIDENCE_PACK', message.attempt_count + 1)
            await self._stage_evidence_pack(
                request_id,
                extraction_result,
                policy_decision,
                job_id,
                trace_id,
                message.attempt_count + 1,
                start_time
            )
            
            # Mark job as completed
            db_service.mark_job_completed(job_id)
            db_service.update_request_status(request_id, 'COMPLETED')
            
            # Update metrics
            processing_time = int((time.time() - start_time) * 1000)
            self.metrics.jobs_processed += 1
            self.metrics.total_processing_time_ms += processing_time
            
            logger.info(
                f"Job completed successfully (job_id: {job_id}, "
                f"trace_id: {trace_id}, time: {processing_time}ms)"
            )
            
            return True
            
        except (OCRTimeoutError, OCRRetryableError) as e:
            # Retryable OCR errors
            logger.warning(f"Retryable OCR error (job_id: {job_id}): {e}")
            if job_id:
                db_service.update_job_status(job_id, 'RETRYING', str(e))
            self.metrics.jobs_retried += 1
            return False  # Retry
            
        except ExtractionValidationError as e:
            # Validation errors might be retryable with different approach
            logger.warning(f"Extraction validation error (job_id: {job_id}): {e}")
            if job_id:
                db_service.update_job_status(job_id, 'RETRYING', str(e))
            self.metrics.jobs_retried += 1
            return False  # Retry
            
        except (OCRNonRetryableError, ExtractionError, PolicyEvaluationError) as e:
            # Non-retryable errors - send to DLQ
            logger.error(f"Non-retryable error (job_id: {job_id}): {e}")
            if job_id:
                db_service.mark_job_failed(job_id, str(e))
            self.metrics.jobs_failed += 1
            raise  # Will be caught by worker and sent to DLQ
            
        except Exception as e:
            # Unknown errors - log and send to DLQ after max retries
            logger.error(f"Unexpected error (job_id: {job_id}): {e}", exc_info=True)
            if job_id:
                db_service.update_job_status(job_id, 'FAILED', str(e))
            self.metrics.jobs_failed += 1
            raise
    
    async def _stage_ocr(self, document_id: str, trace_id: str) -> str:
        """Stage A: OCR processing"""
        # Get document content from PHI schema
        document_text = db_service.get_document_content(document_id)
        
        if not document_text:
            raise Exception(f"Document content not found: {document_id}")
        
        # Process through OCR stage (mocked but with proper error handling)
        ocr_result = await ocr_stage.process(document_text, trace_id)
        
        return ocr_result['text']
    
    async def _stage_extraction(self, document_text: str, trace_id: str):
        """Stage B: Evidence extraction"""
        extraction_result = await extraction_stage.process(document_text, trace_id)
        return extraction_result
    
    async def _stage_policy(self, evidence, trace_id: str):
        """Stage C: Policy evaluation"""
        policy_decision = await policy_stage.process(evidence, trace_id)
        return policy_decision
    
    async def _stage_evidence_pack(
        self,
        request_id: str,
        extraction_result,
        policy_decision,
        job_id: str,
        trace_id: str,
        attempt_count: int,
        start_time: float
    ):
        """Stage D: Produce Evidence Pack"""
        
        processing_latency_ms = int((time.time() - start_time) * 1000)
        
        # Build evidence data
        evidence_data = extraction_result.evidence.model_dump(exclude={'missing_info'})
        evidence_data['missingInfo'] = extraction_result.evidence.missing_info
        
        # Build sources
        sources = {}
        for source in extraction_result.sources:
            sources[source.field] = {
                'text': source.text,
                'lineNumbers': source.line_numbers,
                'charOffsets': list(source.char_offsets),
                'confidence': source.confidence
            }
        
        # Build metadata
        metadata = {
            'attemptCount': attempt_count,
            'processingLatencyMs': processing_latency_ms,
            'traceId': trace_id,
            'extractionMetadata': extraction_result.extraction_metadata
        }
        
        # Save evidence pack
        db_service.save_evidence_pack(
            request_id,
            policy_decision.decision,
            policy_decision.explanation,
            evidence_data,
            sources,
            metadata
        )
        
        # Audit log
        db_service.log_audit_event(
            actor='WORKER',
            action='EVIDENCE_PACK_CREATED',
            request_id=request_id,
            job_id=job_id,
            metadata={
                'decision': policy_decision.decision,
                'trace_id': trace_id
            }
        )


class Worker:
    """Main worker that consumes jobs from queue"""
    
    def __init__(self):
        self.processor = JobProcessor()
        self.running = False
        self.semaphore = asyncio.Semaphore(settings.worker_concurrency)
    
    async def start(self):
        """Start the worker"""
        logger.info(
            f"Starting worker (concurrency: {settings.worker_concurrency}, "
            f"max_retries: {settings.max_retries})"
        )
        
        # Connect to services
        db_service.connect()
        queue_service.connect()
        
        self.running = True
        
        # Start metrics logging task
        asyncio.create_task(self._log_metrics_periodically())
        
        # Start processing loop
        await self._process_loop()
    
    async def stop(self):
        """Stop the worker"""
        logger.info("Stopping worker...")
        self.running = False
        
        # Close connections
        db_service.close()
        queue_service.close()
    
    async def _process_loop(self):
        """Main processing loop"""
        while self.running:
            try:
                # Dequeue message (blocking with timeout)
                message = queue_service.dequeue(timeout=5)
                
                if not message:
                    # No messages, brief sleep
                    await asyncio.sleep(0.1)
                    continue
                
                # Process with concurrency control
                async with self.semaphore:
                    await self._process_message(message)
                    
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                break
            except Exception as e:
                logger.error(f"Error in processing loop: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def _process_message(self, message: QueueMessage):
        """Process a single message with retry logic"""
        try:
            # Process the job
            success = await self.processor.process_job(message)
            
            if success:
                # Job completed, mark as complete
                queue_service.mark_complete(message.message_id)
            else:
                # Job needs retry
                if message.attempt_count + 1 < settings.max_retries:
                    # Requeue with backoff
                    queue_service.requeue_with_backoff(message)
                else:
                    # Max retries exceeded, send to DLQ
                    error = f"Max retries ({settings.max_retries}) exceeded"
                    logger.error(
                        f"Job failed after {message.attempt_count + 1} attempts: "
                        f"request_id={message.request_id}"
                    )
                    
                    # Send to DLQ
                    queue_service.send_to_dlq(message, error)
                    
                    # Record in database DLQ
                    db_service.insert_to_dlq(
                        job_id=f"JOB-{message.message_id}",
                        request_id=message.request_id,
                        job_type=message.job_type,
                        failure_reason=error,
                        attempt_count=message.attempt_count + 1,
                        last_error="Max retries exceeded",
                        payload=message.payload
                    )
                    
        except Exception as e:
            # Unhandled exception - send to DLQ
            error_msg = f"Unhandled exception: {str(e)}"
            logger.error(
                f"Unhandled exception processing message {message.message_id}: {e}",
                exc_info=True
            )
            
            queue_service.send_to_dlq(message, error_msg)
            
            # Record in database DLQ
            db_service.insert_to_dlq(
                job_id=f"JOB-{message.message_id}",
                request_id=message.request_id,
                job_type=message.job_type,
                failure_reason=error_msg,
                attempt_count=message.attempt_count + 1,
                last_error=str(e),
                payload=message.payload
            )
    
    async def _log_metrics_periodically(self):
        """Log metrics every 30 seconds"""
        while self.running:
            await asyncio.sleep(30)
            self.processor.metrics.log_metrics()


async def main():
    """Main entry point"""
    worker = Worker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
    finally:
        await worker.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker terminated")
        sys.exit(0)
