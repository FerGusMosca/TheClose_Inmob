from pathlib import Path
from langchain.prompts import ChatPromptTemplate

class IntentPromptLoader:
    # Fixed base directory for prompts
    BASE_DIR = Path(__file__).resolve().parents[3] / "input" / "intent_prompts"

    @classmethod
    def get_prompt(cls, prompt_name: str, role: str = "system") -> ChatPromptTemplate:
        """
        Load a prompt file from BASE_DIR and return a ChatPromptTemplate
        with the specified role.
        """
        fpath = cls.BASE_DIR / f"{prompt_name}.md"
        if not fpath.exists():
            raise FileNotFoundError(f"Prompt file not found: {fpath}")
        content = fpath.read_text(encoding="utf-8")
        return ChatPromptTemplate.from_messages([(role, content)])

    @classmethod
    def get_text(cls, prompt_name: str) -> str:
        """
        Load a prompt file from BASE_DIR and return its raw text content.
        """
        fpath = cls.BASE_DIR / f"{prompt_name}.md"
        if not fpath.exists():
            raise FileNotFoundError(f"Prompt file not found: {fpath}")
        return fpath.read_text(encoding="utf-8")
