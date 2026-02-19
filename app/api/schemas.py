from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------
# Common / Helpers
# ---------------------------

class APIModel(BaseModel):
    """
    Shared config:
    - forbid unknown fields (catches frontend/backend drift early)
    - allow from ORM/dataclasses (.model_validate(obj, from_attributes=True))
    """
    model_config = ConfigDict(extra="forbid", from_attributes=True)


# ---------------------------
# Sessions
# ---------------------------

class CreateSessionRequest(APIModel):
    title: str = Field(default="New session", min_length=1, max_length=200)
    cwd: Optional[str] = Field(default=None, description="Working directory for this session (server-side).")
    parent_session_id: Optional[str] = None


class CreateSessionResponse(APIModel):
    session_id: str = Field(..., min_length=1)


class SessionSummary(APIModel):
    id: str
    title: str
    cwd: Optional[str] = None
    parent_session_id: Optional[str] = None
    created_ts_ms: int = Field(..., ge=0)


# ---------------------------
# Messages
# ---------------------------

class Message(APIModel):
    id: str
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    created_ts_ms: int = Field(..., ge=0)
    run_id: Optional[str] = None


# ---------------------------
# Runs
# ---------------------------

class StartRunRequest(APIModel):
    user_message: str = Field(..., min_length=1)
    model: Optional[str] = Field(default=None, description="Model/deployment name (e.g., Azure deployment).")
    auto_approve: bool = False
    max_steps: int = Field(default=50, ge=1, le=500)
    allowed_tools: Optional[List[str]] = Field(
        default=None,
        description="If provided, only these tool names can be used during this run.",
    )


class StartRunResponse(APIModel):
    run_id: str
    status: Literal["running", "paused", "completed", "cancelled", "failed"]


# ---------------------------
# Tools
# ---------------------------

class ToolDecisionRequest(APIModel):
    decision: Literal["approve", "reject"]
    reason: Optional[str] = Field(default=None, max_length=500)


# ---------------------------
# SSE Event Types (optional but recommended)
# ---------------------------

class SSEMeta(APIModel):
    id: str
    ts_ms: int = Field(..., ge=0)
    source: str
    correlation_id: Optional[str] = None


class SSEEnvelope(APIModel):
    meta: SSEMeta
    type: str
    data: Dict[str, Any]


# If you want strongly typed assistant_event payloads:
class AssistantEvent(APIModel):
    event: Literal[
        "USER_MESSAGE",
        "TOOL_PROPOSAL",
        "TOOL_APPROVED",
        "TOOL_REJECTED",
        "TOOL_RESULT",
        "FINAL",
    ]
    run_id: str
    text: Optional[str] = None
    tool_id: Optional[str] = None
    name: Optional[str] = None
    ok: Optional[bool] = None
    output: Optional[Any] = None
    tools: Optional[List[Dict[str, Any]]] = None
    auto_approve: Optional[bool] = None
    reason: Optional[str] = None
