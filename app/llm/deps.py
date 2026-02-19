from __future__ import annotations

from functools import lru_cache

from app.llm.azure_client import AzureLLM


@lru_cache(maxsize=1)
def get_llm() -> AzureLLM:
    # singleton per process
    return AzureLLM()
