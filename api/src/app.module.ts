import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { PARequestsController } from './pa-requests/pa-requests.controller';
import { PARequestsService } from './pa-requests/pa-requests.service';
import { AuditController } from './audit/audit.controller';
import { AuditService } from './audit/audit.service';
import { HealthController } from './health.controller';
import { DatabaseService } from './database/database.service';
import { QueueService } from './queue/queue.service';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
    }),
  ],
  controllers: [PARequestsController, AuditController, HealthController],
  providers: [PARequestsService, AuditService, DatabaseService, QueueService],
})
export class AppModule {}
