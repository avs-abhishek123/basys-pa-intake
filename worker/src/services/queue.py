"""Queue service for worker"""
import redis
import json
import logging
import time
from typing import Optional, Dict, Any
from src.config import settings

logger = logging.getLogger(__name__)


class QueueMessage:
    """Queue message wrapper"""
    
    def __init__(self, data: Dict[str, Any]):
        self.message_id = data['messageId']
        self.request_id = data['requestId']
        self.document_id = data.get('documentId')
        self.job_type = data['jobType']
        self.payload = data['payload']
        self.timestamp = data['timestamp']
        self.trace_id = data['traceId']
        self.attempt_count = data['attemptCount']
        self._raw_data = data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self._raw_data
    
    def increment_attempt(self):
        """Increment attempt count"""
        self.attempt_count += 1
        self._raw_data['attemptCount'] = self.attempt_count


class QueueService:
    """Redis queue service"""
    
    QUEUE_NAME = "pa:documents"
    DLQ_NAME = "pa:documents:dlq"
    PROCESSING_SET = "pa:processing"
    RATE_LIMIT_KEY = "pa:rate_limit"
    
    def __init__(self):
        self.client = redis.from_url(settings.redis_url, decode_responses=True)
        self.rate_limiter = RateLimiter(self.client, settings.rate_limit_per_second)
    
    def connect(self):
        """Test connection"""
        try:
            self.client.ping()
            logger.info("✓ Redis connection established")
        except Exception as e:
            logger.error(f"✗ Redis connection failed: {e}")
            raise
    
    def close(self):
        """Close connection"""
        self.client.close()
    
    def dequeue(self, timeout: int = 5) -> Optional[QueueMessage]:
        """Dequeue message from queue (blocking)"""
        try:
            result = self.client.blpop(self.QUEUE_NAME, timeout=timeout)
            if not result:
                return None
            
            _, message_data = result
            data = json.loads(message_data)
            message = QueueMessage(data)
            
            # Add to processing set
            self.client.sadd(self.PROCESSING_SET, message.message_id)
            
            logger.info(f"Dequeued message: {message.message_id} (request: {message.request_id})")
            return message
        except Exception as e:
            logger.error(f"Error dequeuing message: {e}")
            return None
    
    def requeue_with_backoff(self, message: QueueMessage):
        """Requeue message with incremented attempt count"""
        message.increment_attempt()
        
        # Calculate backoff delay
        backoff = min(
            settings.retry_backoff_base ** message.attempt_count,
            settings.retry_backoff_max
        )
        
        logger.info(
            f"Requeuing message {message.message_id} "
            f"(attempt {message.attempt_count}, backoff {backoff}s)"
        )
        
        # For simplicity, just requeue immediately
        # In production, use a delayed queue or scheduled task
        self.client.rpush(self.QUEUE_NAME, json.dumps(message.to_dict()))
        self.mark_complete(message.message_id)
    
    def send_to_dlq(self, message: QueueMessage, error: str):
        """Send message to Dead Letter Queue"""
        dlq_data = {
            **message.to_dict(),
            'error': error,
            'failedAt': time.time()
        }
        
        self.client.rpush(self.DLQ_NAME, json.dumps(dlq_data))
        self.mark_complete(message.message_id)
        
        logger.error(
            f"Message {message.message_id} sent to DLQ: {error[:200]}"
        )
    
    def mark_complete(self, message_id: str):
        """Mark message as completed"""
        self.client.srem(self.PROCESSING_SET, message_id)
    
    def get_queue_size(self) -> int:
        """Get queue size"""
        return self.client.llen(self.QUEUE_NAME)
    
    def get_dlq_size(self) -> int:
        """Get DLQ size"""
        return self.client.llen(self.DLQ_NAME)
    
    def get_processing_count(self) -> int:
        """Get processing count"""
        return self.client.scard(self.PROCESSING_SET)
    
    def check_rate_limit(self) -> bool:
        """Check if rate limit allows processing"""
        return self.rate_limiter.check()


class RateLimiter:
    """Simple token bucket rate limiter"""
    
    def __init__(self, redis_client: redis.Redis, rate_per_second: int):
        self.client = redis_client
        self.rate = rate_per_second
        self.key = "pa:rate_limit:tokens"
    
    def check(self) -> bool:
        """Check if rate limit allows processing"""
        try:
            # Simple sliding window rate limiter
            now = time.time()
            window_start = now - 1.0
            
            # Remove old entries
            self.client.zremrangebyscore(self.key, 0, window_start)
            
            # Count current window
            current_count = self.client.zcard(self.key)
            
            if current_count >= self.rate:
                logger.warning("Rate limit exceeded, throttling...")
                return False
            
            # Add current request
            self.client.zadd(self.key, {str(now): now})
            self.client.expire(self.key, 2)  # Expire after 2 seconds
            
            return True
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            return True  # Fail open


queue_service = QueueService()
