import { IsString, IsNotEmpty, IsOptional, IsUUID } from 'class-validator';

export class CreatePARequestDto {
  @IsString()
  @IsNotEmpty()
  patientName: string;

  @IsString()
  @IsNotEmpty()
  procedure: string;

  @IsString()
  @IsOptional()
  notes?: string;
}

export class UploadDocumentDto {
  @IsString()
  @IsNotEmpty()
  documentText: string;
}

export class PARequestResponse {
  requestId: string;
  status: string;
  createdAt: string;
  updatedAt: string;
}

export class DocumentResponse {
  documentId: string;
  requestId: string;
  status: string;
  uploadedAt: string;
}

export class EvidencePack {
  decision: string;
  explanation: string;
  evidenceData: {
    diagnosis?: string;
    conservativeTherapyAttempted?: boolean;
    conservativeTherapyDetails?: string;
    imagingEvidencePresent?: boolean;
    imagingDetails?: string;
    functionalLimitation?: boolean;
    functionalLimitationDetails?: string;
    missingInfo?: string[];
  };
  sources: {
    diagnosis?: string;
    conservativeTherapy?: string;
    imaging?: string;
    functionalLimitation?: string;
  };
  metadata: {
    attemptCount: number;
    processingLatencyMs: number;
    traceId: string;
    createdAt: string;
  };
}

export class PARequestWithEvidenceResponse extends PARequestResponse {
  evidencePack?: EvidencePack;
}
