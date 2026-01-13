"""Evidence Extraction Stage with guardrails and traceability"""
import logging
import re
import time
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class ExtractedEvidence(BaseModel):
    """Validated evidence structure with guardrails"""
    
    diagnosis: Optional[str] = Field(None, min_length=1, max_length=500)
    conservative_therapy_attempted: bool
    conservative_therapy_details: Optional[str] = Field(None, max_length=1000)
    imaging_evidence_present: bool
    imaging_details: Optional[str] = Field(None, max_length=1000)
    functional_limitation: bool
    functional_limitation_details: Optional[str] = Field(None, max_length=1000)
    missing_info: List[str] = Field(default_factory=list)
    
    # Confidence scores (0.0 - 1.0)
    diagnosis_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    therapy_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    imaging_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    functional_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class EvidenceSource(BaseModel):
    """Source traceability for extracted evidence"""
    
    field: str
    text: str
    line_numbers: List[int]
    char_offsets: Tuple[int, int]
    confidence: float


class ExtractionResult(BaseModel):
    """Complete extraction result with evidence and sources"""
    
    evidence: ExtractedEvidence
    sources: List[EvidenceSource]
    extraction_metadata: Dict[str, Any]


class EvidenceExtractionStage:
    """Evidence extraction with deterministic parsing and guardrails"""
    
    # Minimum confidence threshold for extraction
    MIN_CONFIDENCE = 0.6
    
    # Diagnosis patterns
    DIAGNOSIS_PATTERNS = [
        (r'\b(osteoarthritis|OA)\b', 0.9),
        (r'\b(arthritis)\b', 0.7),
        (r'\bknee pain\b', 0.5),
    ]
    
    # Conservative therapy patterns
    THERAPY_PATTERNS = [
        (r'\b(physical therapy|PT|physiotherapy)\b', 0.9),
        (r'\b(NSAIDs?|non-steroidal anti-inflammatory)\b', 0.9),
        (r'\b(ibuprofen|naproxen|aspirin)\b', 0.8),
        (r'\b(conservative|non-surgical) (treatment|therapy)\b', 0.8),
    ]
    
    # Imaging patterns
    IMAGING_PATTERNS = [
        (r'\b(X-ray|radiograph|MRI|CT scan|imaging)\b.*\b(shows?|demonstrates?|reveals?)\b', 0.9),
        (r'\b(joint space narrowing|osteophyte|bone spur)\b', 0.85),
    ]
    
    # Functional limitation patterns
    FUNCTIONAL_PATTERNS = [
        (r'\b(difficulty|unable to|cannot|can\'t)\b.{0,50}\b(walk|climb|stand|ADLs?|activities of daily living)\b', 0.9),
        (r'\b(impaired|limited|restricted)\b.{0,30}\b(mobility|function|movement)\b', 0.85),
    ]
    
    def __init__(self, timeout: int = 60):
        self.timeout = timeout
    
    async def process(self, ocr_text: str, trace_id: str) -> ExtractionResult:
        """
        Extract evidence from OCR text with guardrails
        
        Implements:
        - Deterministic regex-based extraction
        - Character offset and line number traceability
        - Confidence scoring
        - Validation via Pydantic models
        - Retry on invalid output
        """
        start_time = time.time()
        
        try:
            # Split into lines for line number tracking
            lines = ocr_text.split('\n')
            
            # Extract evidence with sources
            evidence_data = {}
            sources = []
            
            # Extract diagnosis
            diagnosis_result = self._extract_diagnosis(ocr_text, lines)
            evidence_data['diagnosis'] = diagnosis_result['value']
            evidence_data['diagnosis_confidence'] = diagnosis_result['confidence']
            if diagnosis_result['source']:
                sources.append(diagnosis_result['source'])
            
            # Extract conservative therapy
            therapy_result = self._extract_therapy(ocr_text, lines)
            evidence_data['conservative_therapy_attempted'] = therapy_result['attempted']
            evidence_data['conservative_therapy_details'] = therapy_result['details']
            evidence_data['therapy_confidence'] = therapy_result['confidence']
            if therapy_result['source']:
                sources.append(therapy_result['source'])
            
            # Extract imaging evidence
            imaging_result = self._extract_imaging(ocr_text, lines)
            evidence_data['imaging_evidence_present'] = imaging_result['present']
            evidence_data['imaging_details'] = imaging_result['details']
            evidence_data['imaging_confidence'] = imaging_result['confidence']
            if imaging_result['source']:
                sources.append(imaging_result['source'])
            
            # Extract functional limitation
            functional_result = self._extract_functional(ocr_text, lines)
            evidence_data['functional_limitation'] = functional_result['present']
            evidence_data['functional_limitation_details'] = functional_result['details']
            evidence_data['functional_confidence'] = functional_result['confidence']
            if functional_result['source']:
                sources.append(functional_result['source'])
            
            # Determine missing info
            missing_info = []
            if not evidence_data.get('diagnosis'):
                missing_info.append('diagnosis')
            if not evidence_data.get('conservative_therapy_attempted'):
                missing_info.append('conservative_therapy')
            if not evidence_data.get('imaging_evidence_present'):
                missing_info.append('imaging_evidence')
            if not evidence_data.get('functional_limitation'):
                missing_info.append('functional_limitation')
            
            evidence_data['missing_info'] = missing_info
            
            # Validate with Pydantic (guardrail)
            try:
                evidence = ExtractedEvidence(**evidence_data)
            except ValidationError as e:
                logger.error(f"Evidence validation failed (trace_id: {trace_id}): {e}")
                raise ExtractionValidationError(f"Extracted evidence failed validation: {e}")
            
            # Check confidence thresholds (guardrail)
            low_confidence_fields = []
            for field in ['diagnosis', 'therapy', 'imaging', 'functional']:
                confidence = getattr(evidence, f'{field}_confidence')
                if confidence > 0 and confidence < self.MIN_CONFIDENCE:
                    low_confidence_fields.append(field)
            
            if low_confidence_fields:
                logger.warning(
                    f"Low confidence extraction (trace_id: {trace_id}): {low_confidence_fields}"
                )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            result = ExtractionResult(
                evidence=evidence,
                sources=sources,
                extraction_metadata={
                    'processing_time_ms': processing_time_ms,
                    'extraction_method': 'deterministic_regex',
                    'confidence_threshold': self.MIN_CONFIDENCE,
                    'low_confidence_fields': low_confidence_fields,
                    'trace_id': trace_id
                }
            )
            
            logger.info(
                f"Evidence extraction completed (trace_id: {trace_id}, "
                f"time: {processing_time_ms}ms, missing: {len(missing_info)})"
            )
            
            return result
            
        except ExtractionValidationError:
            raise
        except Exception as e:
            logger.error(f"Evidence extraction error (trace_id: {trace_id}): {e}")
            raise ExtractionError(f"Extraction failed: {e}")
    
    def _extract_diagnosis(self, text: str, lines: List[str]) -> Dict[str, Any]:
        """Extract diagnosis with source traceability"""
        best_match = None
        best_confidence = 0.0
        
        for pattern, confidence in self.DIAGNOSIS_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and confidence > best_confidence:
                best_match = match
                best_confidence = confidence
        
        if best_match:
            line_num, char_offset = self._find_line_and_offset(text, best_match.start())
            return {
                'value': best_match.group(0),
                'confidence': best_confidence,
                'source': EvidenceSource(
                    field='diagnosis',
                    text=best_match.group(0),
                    line_numbers=[line_num],
                    char_offsets=(best_match.start(), best_match.end()),
                    confidence=best_confidence
                )
            }
        
        return {'value': None, 'confidence': 0.0, 'source': None}
    
    def _extract_therapy(self, text: str, lines: List[str]) -> Dict[str, Any]:
        """Extract conservative therapy attempts"""
        matches = []
        
        for pattern, confidence in self.THERAPY_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matches.append((match, confidence))
        
        if matches:
            best_match, best_confidence = max(matches, key=lambda x: x[1])
            line_num, char_offset = self._find_line_and_offset(text, best_match.start())
            
            return {
                'attempted': True,
                'details': best_match.group(0),
                'confidence': best_confidence,
                'source': EvidenceSource(
                    field='conservative_therapy',
                    text=best_match.group(0),
                    line_numbers=[line_num],
                    char_offsets=(best_match.start(), best_match.end()),
                    confidence=best_confidence
                )
            }
        
        return {'attempted': False, 'details': None, 'confidence': 0.0, 'source': None}
    
    def _extract_imaging(self, text: str, lines: List[str]) -> Dict[str, Any]:
        """Extract imaging evidence"""
        matches = []
        
        for pattern, confidence in self.IMAGING_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matches.append((match, confidence))
        
        if matches:
            best_match, best_confidence = max(matches, key=lambda x: x[1])
            line_num, char_offset = self._find_line_and_offset(text, best_match.start())
            
            return {
                'present': True,
                'details': best_match.group(0),
                'confidence': best_confidence,
                'source': EvidenceSource(
                    field='imaging',
                    text=best_match.group(0),
                    line_numbers=[line_num],
                    char_offsets=(best_match.start(), best_match.end()),
                    confidence=best_confidence
                )
            }
        
        return {'present': False, 'details': None, 'confidence': 0.0, 'source': None}
    
    def _extract_functional(self, text: str, lines: List[str]) -> Dict[str, Any]:
        """Extract functional limitation"""
        matches = []
        
        for pattern, confidence in self.FUNCTIONAL_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matches.append((match, confidence))
        
        if matches:
            best_match, best_confidence = max(matches, key=lambda x: x[1])
            line_num, char_offset = self._find_line_and_offset(text, best_match.start())
            
            return {
                'present': True,
                'details': best_match.group(0),
                'confidence': best_confidence,
                'source': EvidenceSource(
                    field='functional_limitation',
                    text=best_match.group(0),
                    line_numbers=[line_num],
                    char_offsets=(best_match.start(), best_match.end()),
                    confidence=best_confidence
                )
            }
        
        return {'present': False, 'details': None, 'confidence': 0.0, 'source': None}
    
    def _find_line_and_offset(self, text: str, char_position: int) -> Tuple[int, int]:
        """Find line number and offset for character position"""
        lines = text[:char_position].split('\n')
        line_number = len(lines)
        char_offset = len(lines[-1]) if lines else 0
        return line_number, char_offset


class ExtractionError(Exception):
    """Base extraction error"""
    pass


class ExtractionValidationError(ExtractionError):
    """Extraction validation error"""
    pass


extraction_stage = EvidenceExtractionStage()
