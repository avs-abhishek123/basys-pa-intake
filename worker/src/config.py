"""Configuration for the worker service"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Worker configuration"""
    
    database_url: str = os.getenv("DATABASE_URL", "postgresql://basys:basys_local_dev@postgres:5432/basys_pa")
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379")
    worker_concurrency: int = int(os.getenv("WORKER_CONCURRENCY", "3"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    retry_backoff_base: float = 2.0
    retry_backoff_max: float = 60.0
    ocr_timeout: int = 30
    extraction_timeout: int = 60
    rate_limit_per_second: int = 2
    
    class Config:
        env_file = ".env"


settings = Settings()
