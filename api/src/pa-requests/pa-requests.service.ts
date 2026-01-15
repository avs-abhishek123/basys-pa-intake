import { Injectable, NotFoundException, ConflictException } from '@nestjs/common';
import { DatabaseService } from '../database/database.service';
import { QueueService } from '../queue/queue.service';
import { v4 as uuidv4 } from 'uuid';
import { PoolClient } from 'pg';
import {
  CreatePARequestDto,
  PARequestResponse,
  DocumentResponse,
  PARequestWithEvidenceResponse,
  EvidencePack,
} from './pa-requests.dto';
import * as crypto from 'crypto';

@Injectable()
export class PARequestsService {
  constructor(
    private db: DatabaseService,
    private queue: QueueService,
  ) {}

  async createPARequest(dto: CreatePARequestDto, actorId: string): Promise<PARequestResponse> {
    const requestId = `PA-${Date.now()}-${uuidv4().substring(0, 8)}`;

    const result = await this.db.query(
      `INSERT INTO core.pa_requests (request_id, status, created_by)
       VALUES ($1, $2, $3)
       RETURNING id, request_id, status, created_at, updated_at`,
      [requestId, 'PENDING', actorId],
    );

    // Audit log
    await this.db.query(
      `INSERT INTO core.audit_log (actor, action, request_id, metadata)
       VALUES ($1, $2, $3, $4)`,
      [actorId, 'PA_REQUEST_CREATED', requestId, JSON.stringify({ procedure: dto.procedure })],
    );

    const row = result.rows[0];

    console.log(
      JSON.stringify({
        type: 'pa_request_created',
        request_id: requestId,
        actor: actorId,
        timestamp: new Date().toISOString(),
      }),
    );

    return {
      requestId: row.request_id,
      status: row.status,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    };
  }

  async uploadDocument(
    requestId: string,
    documentText: string,
    idempotencyKey: string,
    actorId: string,
  ): Promise<DocumentResponse> {
    // Check if request exists
    const requestCheck = await this.db.query(`SELECT id FROM core.pa_requests WHERE request_id = $1`, [requestId]);

    if (requestCheck.rows.length === 0) {
      throw new NotFoundException(`PA Request ${requestId} not found`);
    }

    // Check idempotency
    const isProcessed = await this.queue.checkIdempotency(idempotencyKey);
    if (isProcessed) {
      // Return existing document
      const existing = await this.db.query(
        `SELECT document_id, request_id, status, uploaded_at
         FROM core.documents
         WHERE idempotency_key = $1`,
        [idempotencyKey],
      );

      if (existing.rows.length > 0) {
        const doc = existing.rows[0];
        return {
          documentId: doc.document_id,
          requestId: doc.request_id,
          status: doc.status,
          uploadedAt: doc.uploaded_at,
        };
      }
    }

    const documentId = `DOC-${Date.now()}-${uuidv4().substring(0, 8)}`;
    const contentHash = crypto.createHash('sha256').update(documentText).digest('hex');
    const traceId = uuidv4();

    // Use transaction to ensure atomicity
    await this.db.transaction(async (client: PoolClient) => {
      // Insert document metadata
      await client.query(
        `INSERT INTO core.documents (document_id, request_id, status, idempotency_key)
         VALUES ($1, $2, $3, $4)`,
        [documentId, requestId, 'UPLOADED', idempotencyKey],
      );

      // Store document content in PHI schema
      await client.query(
        `INSERT INTO phi.document_content (document_id, content_text, content_hash)
         VALUES ($1, $2, $3)`,
        [documentId, documentText, contentHash],
      );

      // Create job record
      const jobId = `JOB-${Date.now()}-${uuidv4().substring(0, 8)}`;
      await client.query(
        `INSERT INTO core.jobs (job_id, request_id, document_id, job_type, status, trace_id)
         VALUES ($1, $2, $3, $4, $5, $6)`,
        [jobId, requestId, documentId, 'DOCUMENT_PROCESSING', 'QUEUED', traceId],
      );

      // Audit log
      await client.query(
        `INSERT INTO core.audit_log (actor, action, request_id, metadata)
         VALUES ($1, $2, $3, $4)`,
        [actorId, 'DOCUMENT_UPLOADED', requestId, JSON.stringify({ document_id: documentId })],
      );
    });

    // Enqueue processing job
    await this.queue.enqueue({
      requestId,
      documentId,
      jobType: 'DOCUMENT_PROCESSING',
      payload: {
        documentId,
        requestId,
      },
      traceId,
    });

    console.log(
      JSON.stringify({
        type: 'document_uploaded',
        request_id: requestId,
        document_id: documentId,
        trace_id: traceId,
        idempotency_key: idempotencyKey,
        timestamp: new Date().toISOString(),
      }),
    );

    const result = await this.db.query(
      `SELECT document_id, request_id, status, uploaded_at
       FROM core.documents
       WHERE document_id = $1`,
      [documentId],
    );

    const doc = result.rows[0];
    return {
      documentId: doc.document_id,
      requestId: doc.request_id,
      status: doc.status,
      uploadedAt: doc.uploaded_at,
    };
  }

  async getPARequest(requestId: string): Promise<PARequestWithEvidenceResponse> {
    const result = await this.db.query(
      `SELECT id, request_id, status, created_at, updated_at
       FROM core.pa_requests
       WHERE request_id = $1`,
      [requestId],
    );

    if (result.rows.length === 0) {
      throw new NotFoundException(`PA Request ${requestId} not found`);
    }

    const request = result.rows[0];

    // Get latest evidence pack if exists
    const evidenceResult = await this.db.query(
      `SELECT decision, explanation, evidence_data, sources, metadata, created_at
       FROM core.evidence_packs
       WHERE request_id = $1
       ORDER BY created_at DESC
       LIMIT 1`,
      [requestId],
    );

    let evidencePack: EvidencePack | undefined;
    if (evidenceResult.rows.length > 0) {
      const ep = evidenceResult.rows[0];
      evidencePack = {
        decision: ep.decision,
        explanation: ep.explanation,
        evidenceData: ep.evidence_data,
        sources: ep.sources,
        metadata: {
          ...ep.metadata,
          createdAt: ep.created_at,
        },
      };
    }

    return {
      requestId: request.request_id,
      status: request.status,
      createdAt: request.created_at,
      updatedAt: request.updated_at,
      evidencePack,
    };
  }
}
