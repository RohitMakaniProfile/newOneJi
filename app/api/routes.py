from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncIterator, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    StartRunRequest,
    StartRunResponse,
    ToolDecisionRequest,
    SessionSummary,
    Message,
)
from app.core.runner import SessionRunner
from app.core.tools import ToolDecision, ToolRegistry
from app.storage.store import Store


router = APIRouter()


# ----------------------------
# Dependency helpers
# ----------------------------

def get_store(request: Request) -> Store:
    return request.app.state.store


def get_bus(request: Request):
    return request.app.state.bus


def get_registry(request: Request) -> ToolRegistry:
    return request.app.state.registry


def get_runners(request: Request) -> Dict[str, SessionRunner]:
    return request.app.state.runners


# ----------------------------
# Health
# ----------------------------

@router.get("/healthz")
async def healthz():
    return {"ok": True}


# ----------------------------
# Sessions
# ----------------------------

@router.post("/api/sessions", response_model=CreateSessionResponse)
async def create_session(req: CreateSessionRequest, request: Request):
    store = get_store(request)
    rec = store.create_session(
        title=req.title,
        cwd=req.cwd,
        parent_session_id=req.parent_session_id,
    )
    return CreateSessionResponse(session_id=rec.id)


@router.get("/api/sessions", response_model=list[SessionSummary])
async def list_sessions(request: Request):
    store = get_store(request)
    sessions = store.list_sessions(limit=100)
    return [SessionSummary(**s.__dict__) for s in sessions]


@router.get("/api/sessions/{session_id}/messages", response_model=list[Message])
async def list_messages(session_id: str, request: Request):
    store = get_store(request)
    if not store.get_session(session_id):
        raise HTTPException(status_code=404, detail="session not found")

    msgs = store.list_messages(session_id=session_id)
    return [Message(**m) for m in msgs]


# ----------------------------
# Runs
# ----------------------------

@router.post("/api/sessions/{session_id}/runs", response_model=StartRunResponse)
async def start_run(session_id: str, req: StartRunRequest, request: Request):
    store = get_store(request)
    bus = get_bus(request)
    registry = get_registry(request)
    runners = get_runners(request)

    sess = store.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    if session_id in runners:
        raise HTTPException(status_code=409, detail="run already active for this session")

    cwd = Path(sess.cwd or ".").resolve()

    runner = SessionRunner(
        store=store,
        bus=bus,
        registry=registry,
        session_id=session_id,
        cwd=cwd,
        model=req.model,
        auto_approve=req.auto_approve,
        max_steps=req.max_steps,
        allowed_tools=req.allowed_tools,
    )

    runners[session_id] = runner

    async def _bg():
        try:
            await runner.run(req.user_message)
        finally:
            runners.pop(session_id, None)

    asyncio.create_task(_bg())

    return StartRunResponse(run_id=runner.run_id, status="running")


@router.post("/api/sessions/{session_id}/runs/{run_id}/tools/{tool_id}/decision")
async def tool_decision(
    session_id: str,
    run_id: str,
    tool_id: str,
    req: ToolDecisionRequest,
    request: Request,
):
    runners = get_runners(request)
    runner = runners.get(session_id)

    if not runner or runner.run_id != run_id:
        raise HTTPException(status_code=404, detail="active run not found")

    if req.decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="decision must be approve|reject")

    await runner.submit_decision(
        ToolDecision(
            call_id=tool_id,
            decision=req.decision,
            reason=req.reason,
        )
    )

    return {"ok": True}


# ----------------------------
# SSE Event Stream
# ----------------------------

@router.get("/api/sessions/{session_id}/events/stream")
async def stream_events(
    session_id: str,
    request: Request,
    since: Optional[int] = None,
):
    """
    Server-Sent Events stream for a session.

    Supports:
      - ?since=<event_id>
      - Last-Event-ID header
    """

    store = get_store(request)
    bus = get_bus(request)

    if not store.get_session(session_id):
        raise HTTPException(status_code=404, detail="session not found")

    # Support Last-Event-ID header for resume
    last_event_id = request.headers.get("last-event-id")
    if last_event_id and since is None:
        try:
            since = int(last_event_id)
        except ValueError:
            since = None

    async def gen() -> AsyncIterator[bytes]:
        topic = f"session:{session_id}"

        # 1️⃣ Replay persisted DB events (best effort)
        if since is not None:
            for _id, type_, payload_json, ts_ms in store.list_events_since(
                session_id,
                since_ts_ms=int(since),
            ):
                meta = {
                    "id": _id,
                    "ts_ms": ts_ms,
                    "source": "store",
                    "correlation_id": None,
                }
                env = {
                    "meta": meta,
                    "type": type_,
                    "data": json.loads(payload_json),
                }
                yield f"id: {_id}\nevent: {type_}\ndata: {json.dumps(env, ensure_ascii=False)}\n\n".encode(
                    "utf-8"
                )

        # 2️⃣ Subscribe to live bus
        sub = await bus.subscribe(
            topic,
            since_id=int(since) if since is not None else None,
        )

        try:
            while True:
                if await request.is_disconnected():
                    break

                env = await sub.next(timeout=15)

                if env is None:
                    # Keepalive comment
                    yield b": keep-alive\n\n"
                    continue

                yield env.to_sse().encode("utf-8")

        finally:
            await sub.close()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # important for nginx
        },
    )
