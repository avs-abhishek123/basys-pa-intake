import { Controller, Get, Query } from '@nestjs/common';
import { AuditService, AuditEntry } from './audit.service';

@Controller('v1/audit')
export class AuditController {
  constructor(private readonly auditService: AuditService) {}

  @Get()
  async getAuditLog(
    @Query('request_id') requestId?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<AuditEntry[]> {
    const limitNum = limit ? parseInt(limit, 10) : 100;
    const offsetNum = offset ? parseInt(offset, 10) : 0;

    return await this.auditService.getAuditLog(requestId, limitNum, offsetNum);
  }
}
