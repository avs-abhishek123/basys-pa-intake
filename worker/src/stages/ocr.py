"""OCR Stage - Mocked but designed for real OCR service integration"""
import logging
import time
import random
from typing import Dict, Any

logger = logging.getLogger(__name__)


class OCRStage:
    """OCR stage for document processing"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    async def process(self, document_text: str, trace_id: str) -> Dict[str, Any]:
        """
        Process document through OCR
        
        For this assignment, we treat input text as OCR output,
        but implement the stage as if it could call a real OCR service
        """
        start_time = time.time()
        
        try:
            # Simulate OCR processing with potential failures
            await self._simulate_ocr_call(document_text, trace_id)
            
            # In real implementation, this would call external OCR service
            ocr_result = {
                'text': document_text,
                'confidence': 0.98,
                'pages': 1,
                'processing_time_ms': int((time.time() - start_time) * 1000)
            }
            
            logger.info(
                f"OCR stage completed (trace_id: {trace_id}, "
                f"time: {ocr_result['processing_time_ms']}ms)"
            )
            
            return ocr_result
            
        except OCRTimeoutError as e:
            logger.error(f"OCR timeout (trace_id: {trace_id}): {e}")
            raise
        except OCRRetryableError as e:
            logger.warning(f"OCR retryable error (trace_id: {trace_id}): {e}")
            raise
        except Exception as e:
            logger.error(f"OCR non-retryable error (trace_id: {trace_id}): {e}")
            raise OCRNonRetryableError(f"OCR failed: {e}")
    
    async def _simulate_ocr_call(self, text: str, trace_id: str):
        """
        Simulate OCR service call with potential failure scenarios
        
        In production, this would be replaced with actual OCR SDK/API call
        """
        import asyncio
        
        # Simulate processing delay (50-200ms)
        await asyncio.sleep(random.uniform(0.05, 0.2))
        
        # Simulate occasional failures (5% chance for retryable, 1% for timeout)
        rand = random.random()
        
        if rand < 0.01:
            raise OCRTimeoutError("OCR service timeout")
        elif rand < 0.06:
            raise OCRRetryableError("OCR service temporarily unavailable")
        
        # Simulate timeout check
        # In production, use timeout with actual API call
        if len(text) > 100000:  # Simulate large document timeout
            raise OCRTimeoutError("Document too large for OCR")


class OCRError(Exception):
    """Base OCR error"""
    pass


class OCRTimeoutError(OCRError):
    """OCR timeout error (retryable)"""
    pass


class OCRRetryableError(OCRError):
    """OCR retryable error (temporary failure)"""
    pass


class OCRNonRetryableError(OCRError):
    """OCR non-retryable error (permanent failure)"""
    pass


ocr_stage = OCRStage()
