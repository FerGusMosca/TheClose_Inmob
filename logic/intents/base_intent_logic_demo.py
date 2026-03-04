from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple

class BaseIntentLogicDemo(ABC):
    """
    Minimal base class for demo intents.
    """

    name: str = "BASE"

    def __init__(self, logger):
        self.logger = logger

    @abstractmethod
    def required_slots(self) -> Dict[str, str]:
        """
        Dict of required slots -> human-friendly description.
        Example: {"amount": "monto a transferir", "recipient": "destinatario"}
        """
        ...

    @abstractmethod
    def try_extract(self, user_text: str) -> Dict[str, str]:
        """
        Best-effort extraction from free text. May return partials.
        """
        ...

    @abstractmethod
    def execute(self, slots: Dict[str, str]) -> str:
        """
        Perform the action (demo). Return final user message.
        """
        ...

    # --- Helpers (generic) ---
    def missing_slots(self, current: Dict[str, str]) -> Dict[str, str]:
        req = self.required_slots()
        return {k: v for k, v in req.items() if not current.get(k)}

    def build_prompt_for_missing(self, missing: Dict[str, str]) -> str:
        # Minimal, friendly ask
        lines = [f"Necesito estos datos para continuar:"]
        for k, desc in missing.items():
            lines.append(f"- {k}: {desc}")
        lines.append("Podés dármelos en una sola frase (ej: 'mandale 10,000 ARS a Juan').")
        return "\n".join(lines)
