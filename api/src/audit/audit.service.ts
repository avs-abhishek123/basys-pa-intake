import { Injectable } from '@nestjs/common';
import { DatabaseService } from '../database/database.service';

export interface AuditEntry {
  auditId: string;
  actor: string;
  action: string;
  requestId?: string;
  jobId?: string;
  metadata?: any;
  createdAt: string;
}

@Injectable()
export class AuditService {
  constructor(private db: DatabaseService) {}

  async getAuditLog(requestId?: string, limit = 100, offset = 0): Promise<AuditEntry[]> {
    let query = `
      SELECT audit_id, actor, action, request_id, job_id, metadata, created_at
      FROM core.audit_log
    `;
    const params: any[] = [];

    if (requestId) {
      query += ` WHERE request_id = $1`;
      params.push(requestId);
      query += ` ORDER BY created_at DESC LIMIT $2 OFFSET $3`;
      params.push(limit, offset);
    } else {
      query += ` ORDER BY created_at DESC LIMIT $1 OFFSET $2`;
      params.push(limit, offset);
    }

    const result = await this.db.query(query, params);

    return result.rows.map((row: any) => ({
      auditId: row.audit_id,
      actor: row.actor,
      action: row.action,
      requestId: row.request_id,
      jobId: row.job_id,
      metadata: row.metadata,
      createdAt: row.created_at,
    }));
  }

  async logAuditEvent(
    actor: string,
    action: string,
    requestId?: string,
    jobId?: string,
    metadata?: any,
  ): Promise<void> {
    await this.db.query(
      `INSERT INTO core.audit_log (actor, action, request_id, job_id, metadata)
       VALUES ($1, $2, $3, $4, $5)`,
      [actor, action, requestId, jobId, metadata ? JSON.stringify(metadata) : null],
    );

    console.log(
      JSON.stringify({
        type: 'audit_event',
        actor,
        action,
        request_id: requestId,
        job_id: jobId,
        timestamp: new Date().toISOString(),
      }),
    );
  }
}
