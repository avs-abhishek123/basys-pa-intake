import { Controller, Get } from '@nestjs/common';
import { DatabaseService } from '../database/database.service';
import { QueueService } from '../queue/queue.service';

interface HealthResponse {
  status: string;
  timestamp: string;
  services: {
    database: string;
    queue: string;
  };
}

interface MetricsResponse {
  jobs: {
    processed: number;
    failed: number;
    inQueue: number;
    inDLQ: number;
    processing: number;
  };
  requests: {
    total: number;
    pending: number;
    completed: number;
  };
  latency: {
    avg_ms: number;
    p50_ms: number;
    p95_ms: number;
    p99_ms: number;
  };
}

@Controller()
export class HealthController {
  constructor(
    private db: DatabaseService,
    private queue: QueueService,
  ) {}

  @Get('health')
  async getHealth(): Promise<HealthResponse> {
    const dbHealthy = await this.checkDatabase();
    const queueHealthy = await this.checkQueue();

    return {
      status: dbHealthy && queueHealthy ? 'healthy' : 'unhealthy',
      timestamp: new Date().toISOString(),
      services: {
        database: dbHealthy ? 'healthy' : 'unhealthy',
        queue: queueHealthy ? 'healthy' : 'unhealthy',
      },
    };
  }

  @Get('metrics')
  async getMetrics(): Promise<MetricsResponse> {
    // Get job statistics
    const jobStats = await this.db.query(`
      SELECT 
        COUNT(*) FILTER (WHERE status = 'COMPLETED') as processed,
        COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
        COUNT(*) FILTER (WHERE status = 'QUEUED') as queued
      FROM core.jobs
    `);

    const dlqSize = await this.queue.getDLQSize();
    const queueSize = await this.queue.getQueueSize();
    const processingCount = await this.queue.getProcessingCount();

    // Get request statistics
    const requestStats = await this.db.query(`
      SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE status = 'PENDING') as pending,
        COUNT(*) FILTER (WHERE status = 'COMPLETED') as completed
      FROM core.pa_requests
    `);

    // Get latency statistics (completed jobs)
    const latencyStats = await this.db.query(`
      SELECT 
        AVG(EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000)::int as avg_ms,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000)::int as p50_ms,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000)::int as p95_ms,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000)::int as p99_ms
      FROM core.jobs
      WHERE completed_at IS NOT NULL AND started_at IS NOT NULL
    `);

    return {
      jobs: {
        processed: parseInt(jobStats.rows[0].processed || '0'),
        failed: parseInt(jobStats.rows[0].failed || '0'),
        inQueue: queueSize,
        inDLQ: dlqSize,
        processing: processingCount,
      },
      requests: {
        total: parseInt(requestStats.rows[0].total || '0'),
        pending: parseInt(requestStats.rows[0].pending || '0'),
        completed: parseInt(requestStats.rows[0].completed || '0'),
      },
      latency: {
        avg_ms: latencyStats.rows[0]?.avg_ms || 0,
        p50_ms: latencyStats.rows[0]?.p50_ms || 0,
        p95_ms: latencyStats.rows[0]?.p95_ms || 0,
        p99_ms: latencyStats.rows[0]?.p99_ms || 0,
      },
    };
  }

  private async checkDatabase(): Promise<boolean> {
    try {
      await this.db.query('SELECT 1');
      return true;
    } catch {
      return false;
    }
  }

  private async checkQueue(): Promise<boolean> {
    try {
      await this.queue.getQueueSize();
      return true;
    } catch {
      return false;
    }
  }
}
