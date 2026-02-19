from __future__ import annotations

import asyncio
import json
import uuid
from typing import Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from app.devops_agent.agent import DevOpsAgent
from app.models.devops_models import AnalyzeRequest, AnalyzeResponse, JobStatus

router = APIRouter(prefix="/api/devops", tags=["devops"])

# Simple in-memory job store: job_id -> dict (serialized JobStatus)
job_store: Dict[str, dict] = {}


def _is_github_url(url: str) -> bool:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.hostname in ("github.com", "www.github.com")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest, background_tasks: BackgroundTasks) -> AnalyzeResponse:
    if not _is_github_url(request.repo_url):
        raise HTTPException(status_code=400, detail="repo_url must be a GitHub URL")

    job_id = str(uuid.uuid4())
    job_store[job_id] = JobStatus(status="running").model_dump()

    agent = DevOpsAgent(
        repo_url=request.repo_url,
        team_name=request.team_name,
        team_leader=request.team_leader,
    )
    background_tasks.add_task(_run_agent, agent, job_id)

    return AnalyzeResponse(job_id=job_id, status="running")


async def _run_agent(agent: DevOpsAgent, job_id: str) -> None:
    await agent.run(job_id, job_store)


@router.get("/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: str) -> JobStatus:
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(**job_store[job_id])


@router.get("/stream/{job_id}")
async def stream_status(job_id: str) -> StreamingResponse:
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        while True:
            data = job_store.get(job_id)
            if data is None:
                break
            yield f"data: {json.dumps(data)}\n\n"
            status = data.get("status", "running")
            if status in ("completed", "failed"):
                break
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
