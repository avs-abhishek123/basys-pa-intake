"""Database service for worker"""
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import logging
from typing import Any, Dict, List, Optional
from src.config import settings

logger = logging.getLogger(__name__)


class DatabaseService:
    """PostgreSQL database service"""
    
    def __init__(self):
        self.connection_string = settings.database_url
        self._connection = None
    
    def connect(self):
        """Establish database connection"""
        try:
            self._connection = psycopg2.connect(
                self.connection_string,
                cursor_factory=RealDictCursor
            )
            logger.info("✓ Database connection established")
        except Exception as e:
            logger.error(f"✗ Database connection failed: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
            logger.info("Database connection closed")
    
    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor"""
        cursor = self._connection.cursor()
        try:
            yield cursor
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        finally:
            cursor.close()
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description:
                return cursor.fetchall()
            return []
    
    def execute_update(self, query: str, params: Optional[tuple] = None) -> int:
        """Execute an update/insert query and return affected rows"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount
    
    def get_document_content(self, document_id: str) -> Optional[str]:
        """Retrieve document content from PHI schema"""
        results = self.execute_query(
            "SELECT content_text FROM phi.document_content WHERE document_id = %s",
            (document_id,)
        )
        return results[0]['content_text'] if results else None
    
    def update_job_status(self, job_id: str, status: str, error_message: Optional[str] = None):
        """Update job status"""
        query = """
            UPDATE core.jobs 
            SET status = %s, error_message = %s, updated_at = NOW()
            WHERE job_id = %s
        """
        self.execute_update(query, (status, error_message, job_id))
    
    def update_job_stage(self, job_id: str, stage: str, attempt_count: int):
        """Update job stage and attempt count"""
        query = """
            UPDATE core.jobs 
            SET current_stage = %s, attempt_count = %s, updated_at = NOW()
            WHERE job_id = %s
        """
        self.execute_update(query, (stage, attempt_count, job_id))
    
    def mark_job_started(self, job_id: str):
        """Mark job as started"""
        query = """
            UPDATE core.jobs 
            SET status = 'PROCESSING', started_at = NOW(), updated_at = NOW()
            WHERE job_id = %s
        """
        self.execute_update(query, (job_id,))
    
    def mark_job_completed(self, job_id: str):
        """Mark job as completed"""
        query = """
            UPDATE core.jobs 
            SET status = 'COMPLETED', completed_at = NOW(), updated_at = NOW()
            WHERE job_id = %s
        """
        self.execute_update(query, (job_id,))
    
    def mark_job_failed(self, job_id: str, error_message: str):
        """Mark job as failed"""
        query = """
            UPDATE core.jobs 
            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
            WHERE job_id = %s
        """
        self.execute_update(query, (error_message, job_id))
    
    def insert_to_dlq(self, job_id: str, request_id: str, job_type: str, 
                      failure_reason: str, attempt_count: int, last_error: str, payload: Dict):
        """Insert failed job to DLQ"""
        query = """
            INSERT INTO core.dlq (job_id, request_id, job_type, failure_reason, 
                                  attempt_count, last_error, payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        import json
        self.execute_update(
            query, 
            (job_id, request_id, job_type, failure_reason, attempt_count, last_error, json.dumps(payload))
        )
    
    def save_extracted_evidence(self, request_id: str, document_id: str, evidence: Dict):
        """Save extracted evidence to PHI schema"""
        query = """
            INSERT INTO phi.extracted_evidence 
            (request_id, document_id, diagnosis, conservative_therapy_attempted,
             conservative_therapy_details, imaging_evidence_present, imaging_details,
             functional_limitation, functional_limitation_details, missing_info, 
             extraction_metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        self.execute_update(query, (
            request_id,
            document_id,
            evidence.get('diagnosis'),
            evidence.get('conservative_therapy_attempted'),
            evidence.get('conservative_therapy_details'),
            evidence.get('imaging_evidence_present'),
            evidence.get('imaging_details'),
            evidence.get('functional_limitation'),
            evidence.get('functional_limitation_details'),
            evidence.get('missing_info'),
            evidence.get('extraction_metadata')
        ))
    
    def save_evidence_pack(self, request_id: str, decision: str, explanation: str,
                          evidence_data: Dict, sources: Dict, metadata: Dict):
        """Save evidence pack to core schema"""
        import json
        query = """
            INSERT INTO core.evidence_packs 
            (request_id, decision, explanation, evidence_data, sources, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        self.execute_update(query, (
            request_id,
            decision,
            explanation,
            json.dumps(evidence_data),
            json.dumps(sources),
            json.dumps(metadata)
        ))
    
    def update_request_status(self, request_id: str, status: str):
        """Update PA request status"""
        query = """
            UPDATE core.pa_requests 
            SET status = %s, updated_at = NOW()
            WHERE request_id = %s
        """
        self.execute_update(query, (status, request_id))
    
    def log_audit_event(self, actor: str, action: str, request_id: Optional[str] = None,
                       job_id: Optional[str] = None, metadata: Optional[Dict] = None):
        """Log audit event"""
        import json
        query = """
            INSERT INTO core.audit_log (actor, action, request_id, job_id, metadata)
            VALUES (%s, %s, %s, %s, %s)
        """
        self.execute_update(query, (
            actor,
            action,
            request_id,
            job_id,
            json.dumps(metadata) if metadata else None
        ))
    
    def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job details by ID"""
        results = self.execute_query(
            """SELECT * FROM core.jobs WHERE job_id = %s""",
            (job_id,)
        )
        return dict(results[0]) if results else None


db_service = DatabaseService()
