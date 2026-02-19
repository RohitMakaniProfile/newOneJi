from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.llm.azure_client import AzureLLM
from app.llm.deps import get_llm

router = APIRouter(prefix="/api/llm", tags=["llm"])


class LlmTestRequest(BaseModel):
    prompt: str


@router.post("/test")
async def llm_test(req: LlmTestRequest, llm: AzureLLM = Depends(get_llm)):
    out = await llm.chat(system="You are a helpful assistant.", user=req.prompt)
    return {"text": out.text}
