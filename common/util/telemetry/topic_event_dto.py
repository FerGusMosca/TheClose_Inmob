from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

@dataclass
class TopicEventDTO:
    """
    Rich topic + signals extracted from a user query.
    Keep this DTO small, serializable and validation-friendly.
    """
    run_id: str
    topic: str
    subtopic: Optional[str]
    intent: Optional[str]
    confidence: float
    sentiment: int          # -2..2
    urgency: int            # 0..3
    pii_detected: bool
    compliance_risk: str    # 'low' | 'med' | 'high'
    suggested_action: str   # e.g., 'ESCALATE_HUMAN'
    outcome: str            # 'unknown'| 'success'|'failed'|'escalated'|'fallback'

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)