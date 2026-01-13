import {
  Controller,
  Post,
  Get,
  Body,
  Param,
  Headers,
  HttpCode,
  HttpStatus,
  BadRequestException,
} from '@nestjs/common';
import { PARequestsService } from './pa-requests.service';
import {
  CreatePARequestDto,
  UploadDocumentDto,
  PARequestResponse,
  DocumentResponse,
  PARequestWithEvidenceResponse,
} from './pa-requests.dto';

@Controller('v1/pa-requests')
export class PARequestsController {
  constructor(private readonly paRequestsService: PARequestsService) {}

  @Post()
  @HttpCode(HttpStatus.CREATED)
  async createPARequest(
    @Body() createDto: CreatePARequestDto,
    @Headers('x-api-key') apiKey: string,
  ): Promise<PARequestResponse> {
    // Simple API key validation (in production, use proper authentication)
    if (!apiKey) {
      throw new BadRequestException('API key required');
    }

    return await this.paRequestsService.createPARequest(createDto, apiKey);
  }

  @Post(':requestId/documents')
  @HttpCode(HttpStatus.CREATED)
  async uploadDocument(
    @Param('requestId') requestId: string,
    @Body() uploadDto: UploadDocumentDto,
    @Headers('idempotency-key') idempotencyKey: string,
    @Headers('x-api-key') apiKey: string,
  ): Promise<DocumentResponse> {
    if (!apiKey) {
      throw new BadRequestException('API key required');
    }

    if (!idempotencyKey) {
      throw new BadRequestException('Idempotency-Key header is required');
    }

    return await this.paRequestsService.uploadDocument(
      requestId,
      uploadDto.documentText,
      idempotencyKey,
      apiKey,
    );
  }

  @Get(':requestId')
  async getPARequest(@Param('requestId') requestId: string): Promise<PARequestWithEvidenceResponse> {
    return await this.paRequestsService.getPARequest(requestId);
  }
}
