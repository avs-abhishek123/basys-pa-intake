# Submission Checklist

## Required Deliverables

### ✅ 1. Git Repository Structure
- [x] docker-compose.yml
- [x] api/ directory with NestJS service
- [x] worker/ directory with FastAPI service
- [x] migrations/ directory with SQL
- [x] tests/ directory with 2+ tests

### ✅ 2. Tests (Minimum 2)
- [x] Idempotency test (`tests/test_idempotency.py`)
- [x] Retry → DLQ test (`tests/test_retry_dlq.py`)

### ✅ 3. Documentation
- [x] README.md with:
  - [x] How to run locally
  - [x] Example curl commands
  - [x] Architecture diagram (ASCII)
  - [x] Key trade-offs
  - [x] Production hardening plan

### ✅ 4. AI-First Development Evidence
- [x] AI_NOTES.md with:
  - [x] Tools used (Claude 3.5 Sonnet)
  - [x] 5+ important prompts
  - [x] What was accepted/rejected
  - [x] One AI suggestion corrected (PHI in logs)

## Assignment Requirements Checklist

### Architecture
- [x] API Service (NestJS/TypeScript)
- [x] Worker Service (FastAPI/Python)
- [x] PostgreSQL database
- [x] Queue system (Redis)
- [x] Docker Compose setup

### API Endpoints
- [x] POST /v1/pa-requests
- [x] POST /v1/pa-requests/:id/documents (with Idempotency-Key)
- [x] GET /v1/pa-requests/:id
- [x] GET /v1/audit

### Data Model
- [x] PHI separation (core vs phi schemas)
- [x] Request tracking
- [x] Job tracking
- [x] Audit log
- [x] DLQ table

### Async Workflow
- [x] Stage A: OCR (mocked with proper error handling)
- [x] Stage B: Evidence extraction with traceability
- [x] Stage C: Policy evaluation (TKA policy)
- [x] Stage D: Evidence Pack generation

### Reliability
- [x] Retries with backoff (3 attempts)
- [x] Idempotency (API + Queue level)
- [x] DLQ for failed jobs
- [x] Backpressure control (worker semaphore)
- [x] Rate limit simulation

### Observability
- [x] Structured JSON logs
- [x] No PHI in logs
- [x] /health endpoint
- [x] /metrics endpoint
- [x] Audit trail

### Policy Implementation
- [x] TKA policy rules
- [x] Decision: APPROVE or NEEDS_MORE_INFO
- [x] Missing requirements list
- [x] Evidence validation

### Test Data
- [x] Synthetic clinical note (John Doe)
- [x] Expected outcome: NEEDS_MORE_INFO
- [x] Examples in README

## Pre-Submission Verification

### Local Testing
```bash
# 1. Start services
docker-compose up --build

# 2. Wait 30 seconds, then check health
curl http://localhost:3000/health

# 3. Run tests
cd tests
pip install -r requirements.txt
python test_idempotency.py
python test_retry_dlq.py

# 4. Test manual flow
# Follow curl examples in README or EXAMPLES.md
```

### File Checklist
```
basys-pa-intake/
├── README.md                    ✅
├── AI_NOTES.md                  ✅
├── EXAMPLES.md                  ✅
├── docker-compose.yml           ✅
├── Makefile                     ✅
├── start.sh                     ✅
├── .gitignore                   ✅
│
├── migrations/
│   └── init.sql                 ✅
│
├── api/
│   ├── Dockerfile               ✅
│   ├── package.json             ✅
│   ├── tsconfig.json            ✅
│   ├── nest-cli.json            ✅
│   └── src/
│       ├── main.ts              ✅
│       ├── app.module.ts        ✅
│       ├── health.controller.ts ✅
│       ├── database/            ✅
│       ├── queue/               ✅
│       ├── pa-requests/         ✅
│       └── audit/               ✅
│
├── worker/
│   ├── Dockerfile               ✅
│   ├── requirements.txt         ✅
│   └── src/
│       ├── main.py              ✅
│       ├── config.py            ✅
│       ├── services/            ✅
│       └── stages/              ✅
│
└── tests/
    ├── requirements.txt         ✅
    ├── test_idempotency.py      ✅
    └── test_retry_dlq.py        ✅
```

## Follow-Up Call Preparation

### Be Ready to Discuss:

1. **Failure Modes**
   - What happens if worker crashes mid-stage?
   - Answer: Job remains in processing set; can implement recovery via scheduled cleanup task

2. **Exactly-once vs At-least-once**
   - System uses at-least-once delivery with idempotency
   - Duplicate messages handled via idempotency keys

3. **Evolution Plans**
   - Real OCR: Replace mock with AWS Textract/Google Vision SDK
   - FHIR mapping: Add transformation stage to convert Evidence Pack to FHIR Claim resources
   - Multi-tenant: Add tenant_id to all tables, isolate data per payer

4. **Security Posture (HIPAA + SOC 2)**
   - PHI separation in database
   - No PHI in logs
   - Audit trail
   - API key authentication (would enhance to JWT)
   - Encryption at rest/transit needed for production

## Known Limitations (To Discuss)

1. **Simple API key auth** - Would use JWT + RBAC in production
2. **No LLM integration** - Used deterministic regex for predictability
3. **Limited test coverage** - Only 2 integration tests due to time
4. **Single-file migrations** - Would use Alembic/Prisma in production
5. **No distributed tracing** - Would add OpenTelemetry

## Submission Format

### Option 1: GitHub/GitLab Repository
1. Create new repository
2. Push code
3. Share repository URL
4. Ensure README is visible

### Option 2: ZIP File
1. Create zip: `tar -czf basys-pa-intake.tar.gz basys-pa-intake/`
2. Or: `zip -r basys-pa-intake.zip basys-pa-intake/`
3. Upload to file sharing service
4. Share download link

## Final Pre-Flight Check

- [ ] All services start successfully
- [ ] Health endpoint returns 200
- [ ] Can create PA request
- [ ] Can upload document
- [ ] Evidence pack is generated
- [ ] Idempotency test passes
- [ ] Retry test demonstrates retry infrastructure
- [ ] README is clear and complete
- [ ] AI_NOTES.md documents AI usage
- [ ] No passwords/secrets committed

## Contact

For questions, reply to the hiring email from Team Basys.ai.

Good luck! 🚀
