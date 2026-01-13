-- Database initialization with PHI separation
-- Two schemas: 'core' for non-PHI data, 'phi' for protected health information

-- Create schemas
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS phi;

-- Set search path (core is default for most operations)
ALTER DATABASE basys_pa SET search_path TO core, phi, public;

-- ========================================
-- CORE SCHEMA (Non-PHI operational data)
-- ========================================

-- PA Requests (core metadata)
CREATE TABLE core.pa_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL,
    INDEX idx_request_id (request_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);

-- Documents (metadata only, no content)
CREATE TABLE core.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id VARCHAR(255) UNIQUE NOT NULL,
    request_id VARCHAR(255) NOT NULL REFERENCES core.pa_requests(request_id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'UPLOADED',
    uploaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP,
    idempotency_key VARCHAR(255) UNIQUE,
    INDEX idx_document_id (document_id),
    INDEX idx_request_id (request_id),
    INDEX idx_idempotency_key (idempotency_key)
);

-- Evidence Packs (structured, non-PHI output)
CREATE TABLE core.evidence_packs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id VARCHAR(255) NOT NULL REFERENCES core.pa_requests(request_id) ON DELETE CASCADE,
    decision VARCHAR(50) NOT NULL,
    explanation TEXT NOT NULL,
    evidence_data JSONB NOT NULL,
    sources JSONB NOT NULL,
    metadata JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_request_id (request_id),
    INDEX idx_decision (decision)
);

-- Jobs (workflow tracking)
CREATE TABLE core.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(255) UNIQUE NOT NULL,
    request_id VARCHAR(255) NOT NULL,
    document_id VARCHAR(255),
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    current_stage VARCHAR(50),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    error_message TEXT,
    trace_id VARCHAR(255),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_job_id (job_id),
    INDEX idx_request_id (request_id),
    INDEX idx_status (status),
    INDEX idx_job_type (job_type)
);

-- Dead Letter Queue (failed jobs)
CREATE TABLE core.dlq (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(255) NOT NULL,
    request_id VARCHAR(255) NOT NULL,
    job_type VARCHAR(50) NOT NULL,
    failure_reason TEXT NOT NULL,
    attempt_count INTEGER NOT NULL,
    last_error TEXT,
    payload JSONB NOT NULL,
    failed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_job_id (job_id),
    INDEX idx_request_id (request_id),
    INDEX idx_failed_at (failed_at)
);

-- Audit Log (non-PHI actions only)
CREATE TABLE core.audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id VARCHAR(255) UNIQUE NOT NULL DEFAULT gen_random_uuid()::TEXT,
    actor VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    request_id VARCHAR(255),
    job_id VARCHAR(255),
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_audit_id (audit_id),
    INDEX idx_request_id (request_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at),
    INDEX idx_actor (actor)
);

-- Metrics (observability)
CREATE TABLE core.metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC NOT NULL,
    labels JSONB,
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_metric_name (metric_name),
    INDEX idx_recorded_at (recorded_at)
);

-- ========================================
-- PHI SCHEMA (Protected Health Information)
-- ========================================

-- Document Content (PHI)
CREATE TABLE phi.document_content (
    document_id VARCHAR(255) PRIMARY KEY,
    content_text TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    stored_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_document_id (document_id)
);

-- Extracted Evidence (may contain PHI)
CREATE TABLE phi.extracted_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id VARCHAR(255) NOT NULL,
    document_id VARCHAR(255) NOT NULL,
    diagnosis TEXT,
    conservative_therapy_attempted BOOLEAN,
    conservative_therapy_details TEXT,
    imaging_evidence_present BOOLEAN,
    imaging_details TEXT,
    functional_limitation BOOLEAN,
    functional_limitation_details TEXT,
    missing_info TEXT[],
    extraction_metadata JSONB,
    extracted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_request_id (request_id),
    INDEX idx_document_id (document_id)
);

-- ========================================
-- FUNCTIONS AND TRIGGERS
-- ========================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION core.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_pa_requests_updated_at
    BEFORE UPDATE ON core.pa_requests
    FOR EACH ROW
    EXECUTE FUNCTION core.update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at
    BEFORE UPDATE ON core.jobs
    FOR EACH ROW
    EXECUTE FUNCTION core.update_updated_at_column();

-- ========================================
-- INITIAL DATA
-- ========================================

-- Grant appropriate permissions (for development)
GRANT USAGE ON SCHEMA core TO basys;
GRANT USAGE ON SCHEMA phi TO basys;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA core TO basys;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA phi TO basys;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA core TO basys;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA phi TO basys;

-- Create initial audit entry
INSERT INTO core.audit_log (actor, action, metadata, created_at)
VALUES ('SYSTEM', 'DATABASE_INITIALIZED', '{"version": "1.0.0"}'::jsonb, NOW());
