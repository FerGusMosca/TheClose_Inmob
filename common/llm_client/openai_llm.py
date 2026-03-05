# common/llm_client/openai_llm.py
"""
OpenAI concrete implementation of BaseLLM.
All comments in English.
"""
from typing import Any, Iterator, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage

from common.llm_client.base_llm import BaseLLM


class OpenAILLM(BaseLLM):

    def __init__(
        self,
        model_name:  str            = "gpt-4o-mini",
        temperature: float          = 0.0,
        max_tokens:  Optional[int]  = None,
    ):
        self.model_name  = model_name
        self.temperature = temperature
        self.max_tokens  = max_tokens
        self._client = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def invoke(self, prompt: str) -> str:
        return self._extract_content(self._client.invoke(prompt))

    def invoke_messages(self, messages: list[BaseMessage]) -> str:
        return self._extract_content(self._client.invoke(messages))

    def stream(self, prompt: str) -> Iterator[str]:
        for chunk in self._client.stream(prompt):
            content = self._extract_content(chunk)
            if content:
                yield content

    def handle(self, query: str) -> str:
        return self.invoke(query)

    def get_client(self) -> ChatOpenAI:
        return self._client

    @staticmethod
    def _extract_content(response: Any) -> str:
        if hasattr(response, "content"):
            c = response.content
            return c.strip() if isinstance(c, str) else str(c)
        return str(response).strip()