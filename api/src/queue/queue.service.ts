import { Injectable, OnModuleInit, OnModuleDestroy } from '@nestjs/common';
import { createClient, RedisClientType } from 'redis';
import { ConfigService } from '@nestjs/config';
import { v4 as uuidv4 } from 'uuid';

export interface QueueMessage {
  messageId: string;
  requestId: string;
  documentId?: string;
  jobType: string;
  payload: any;
  timestamp: string;
  traceId: string;
  attemptCount: number;
}

@Injectable()
export class QueueService implements OnModuleInit, OnModuleDestroy {
  private client: RedisClientType;
  private readonly QUEUE_NAME = 'pa:documents';
  private readonly DLQ_NAME = 'pa:documents:dlq';
  private readonly PROCESSING_SET = 'pa:processing';

  constructor(private configService: ConfigService) {}

  async onModuleInit() {
    this.client = createClient({
      url: this.configService.get<string>('REDIS_URL'),
    });

    this.client.on('error', (err) => console.error('Redis Client Error', err));
    this.client.on('connect', () => console.log('✓ Redis connection established'));

    await this.client.connect();
  }

  async onModuleDestroy() {
    await this.client.quit();
  }

  async enqueue(message: Omit<QueueMessage, 'messageId' | 'timestamp' | 'attemptCount'>): Promise<string> {
    const fullMessage: QueueMessage = {
      ...message,
      messageId: uuidv4(),
      timestamp: new Date().toISOString(),
      attemptCount: 0,
    };

    await this.client.rPush(this.QUEUE_NAME, JSON.stringify(fullMessage));

    console.log(
      JSON.stringify({
        type: 'queue_enqueue',
        queue: this.QUEUE_NAME,
        message_id: fullMessage.messageId,
        request_id: message.requestId,
        job_type: message.jobType,
        trace_id: message.traceId,
      }),
    );

    return fullMessage.messageId;
  }

  async enqueueDLQ(message: QueueMessage, error: string): Promise<void> {
    const dlqMessage = {
      ...message,
      error,
      failedAt: new Date().toISOString(),
    };

    await this.client.rPush(this.DLQ_NAME, JSON.stringify(dlqMessage));

    console.log(
      JSON.stringify({
        type: 'queue_dlq',
        queue: this.DLQ_NAME,
        message_id: message.messageId,
        request_id: message.requestId,
        error: error.substring(0, 200), // Truncate error for logging
        trace_id: message.traceId,
      }),
    );
  }

  async dequeue(): Promise<QueueMessage | null> {
    const message = await this.client.lPop(this.QUEUE_NAME);
    if (!message) {
      return null;
    }

    const parsed = JSON.parse(message) as QueueMessage;

    // Add to processing set for visibility
    await this.client.sAdd(this.PROCESSING_SET, parsed.messageId);

    return parsed;
  }

  async markComplete(messageId: string): Promise<void> {
    await this.client.sRem(this.PROCESSING_SET, messageId);
  }

  async getQueueSize(): Promise<number> {
    return await this.client.lLen(this.QUEUE_NAME);
  }

  async getDLQSize(): Promise<number> {
    return await this.client.lLen(this.DLQ_NAME);
  }

  async getProcessingCount(): Promise<number> {
    return await this.client.sCard(this.PROCESSING_SET);
  }

  // Idempotency check
  async checkIdempotency(idempotencyKey: string): Promise<boolean> {
    const key = `idempotency:${idempotencyKey}`;
    const exists = await this.client.exists(key);
    if (exists) {
      return true; // Already processed
    }
    // Set with TTL of 24 hours
    await this.client.setEx(key, 86400, '1');
    return false;
  }
}
