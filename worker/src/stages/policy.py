"""Policy Evaluation Stage"""
import logging
from typing import Dict, Any, List
from src.stages.extraction import ExtractedEvidence

logger = logging.getLogger(__name__)


class PolicyDecision:
    """Policy decision result"""
    
    def __init__(self, decision: str, explanation: str, missing_requirements: List[str]):
        self.decision = decision
        self.explanation = explanation
        self.missing_requirements = missing_requirements


class TKAPolicyEvaluator:
    """
    Total Knee Arthroplasty (TKA) Policy Evaluator
    
    Policy Requirements:
    - Must have: diagnosis = osteoarthritis
    - Must have: imaging evidence present
    - Must have: conservative therapy attempted (physical therapy or NSAIDs)
    - Must have: functional limitation affecting ADLs
    
    Decision Rules:
    - If all present → APPROVE
    - If any missing → NEEDS_MORE_INFO and list what's missing
    """
    
    REQUIRED_DIAGNOSIS = ['osteoarthritis', 'oa']
    
    def evaluate(self, evidence: ExtractedEvidence, trace_id: str) -> PolicyDecision:
        """Evaluate evidence against TKA policy"""
        
        logger.info(f"Starting policy evaluation (trace_id: {trace_id})")
        
        missing_requirements = []
        
        # Check diagnosis
        if not self._check_diagnosis(evidence):
            missing_requirements.append('diagnosis of osteoarthritis')
        
        # Check imaging evidence
        if not evidence.imaging_evidence_present:
            missing_requirements.append('imaging evidence')
        
        # Check conservative therapy
        if not evidence.conservative_therapy_attempted:
            missing_requirements.append('conservative therapy (physical therapy or NSAIDs)')
        
        # Check functional limitation
        if not evidence.functional_limitation:
            missing_requirements.append('functional limitation affecting ADLs')
        
        # Make decision
        if not missing_requirements:
            decision = 'APPROVE'
            explanation = (
                'All TKA policy requirements are met: '
                'osteoarthritis diagnosis confirmed, imaging evidence present, '
                'conservative therapy attempted, and functional limitations documented.'
            )
        else:
            decision = 'NEEDS_MORE_INFO'
            missing_str = ', '.join(missing_requirements)
            explanation = (
                f'Additional information required for TKA approval. '
                f'Missing: {missing_str}. '
                f'Please provide the required documentation to proceed with the request.'
            )
        
        result = PolicyDecision(decision, explanation, missing_requirements)
        
        logger.info(
            f"Policy evaluation completed (trace_id: {trace_id}, "
            f"decision: {decision}, missing: {len(missing_requirements)})"
        )
        
        return result
    
    def _check_diagnosis(self, evidence: ExtractedEvidence) -> bool:
        """Check if diagnosis matches required diagnosis"""
        if not evidence.diagnosis:
            return False
        
        diagnosis_lower = evidence.diagnosis.lower()
        return any(req in diagnosis_lower for req in self.REQUIRED_DIAGNOSIS)


class PolicyEvaluationStage:
    """Policy evaluation stage"""
    
    def __init__(self):
        self.tka_evaluator = TKAPolicyEvaluator()
    
    async def process(self, evidence: ExtractedEvidence, trace_id: str) -> PolicyDecision:
        """Process policy evaluation"""
        
        try:
            # Currently only TKA policy is implemented
            # In production, this would route to appropriate policy evaluator
            decision = self.tka_evaluator.evaluate(evidence, trace_id)
            
            return decision
            
        except Exception as e:
            logger.error(f"Policy evaluation error (trace_id: {trace_id}): {e}")
            raise PolicyEvaluationError(f"Policy evaluation failed: {e}")


class PolicyEvaluationError(Exception):
    """Policy evaluation error"""
    pass


policy_stage = PolicyEvaluationStage()
