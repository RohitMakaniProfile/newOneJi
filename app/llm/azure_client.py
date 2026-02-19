from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from openai import AsyncAzureOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

from app.core.settings import settings


@dataclass(frozen=True)
class LLMResponse:
    text: str
    raw: Any


class AzureLLM:
    """
    Thin, testable wrapper over AsyncAzureOpenAI.
    - Centralizes retries/timeouts
    - Keeps the rest of the system provider-agnostic
    """

    def __init__(
        self,
        *,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        api_version: Optional[str] = None,
        deployment: Optional[str] = None,
        timeout_s: float = 60.0,
    ) -> None:
        self.deployment = deployment or settings.azure_openai_deployment
        self.client = AsyncAzureOpenAI(
            azure_endpoint=endpoint or settings.azure_openai_endpoint,
            api_key=api_key or settings.azure_openai_api_key,
            api_version=api_version or settings.azure_openai_api_version,
            timeout=timeout_s,
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.8, max=8),
        retry=retry_if_exception_type(Exception),
    )
    async def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_output_tokens: int = 800,
        extra: Optional[dict[str, Any]] = None,
    ) -> LLMResponse:
        """
        Uses Chat Completions. We’ll later switch to structured tool calling
        (still via chat) when we wire LangGraph tools.
        """
        payload: dict[str, Any] = {
            "model": self.deployment,  # Azure uses deployment name in the model field
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        if extra:
            payload.update(extra)

        resp = await self.client.chat.completions.create(**payload)
        text = (resp.choices[0].message.content or "").strip()
        return LLMResponse(text=text, raw=resp)
