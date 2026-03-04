# custom_logging_logic.py
from langchain_openai import OpenAI


class CustomLoggingLogic:

    def __init__(self):
        pass

    """
    Base class for custom topic/event detection.
    Override detect() in subclasses.
    """

    def handle(self, question: str, logger) -> bool:
        return False
