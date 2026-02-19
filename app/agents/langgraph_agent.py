from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Tuple

from app.core.tools import ToolCall


class AgentState(TypedDict, total=False):
    messages: List[Dict[str, Any]]  # {role, content}
    pending_tools: List[ToolCall]
    final: Optional[str]


# ----------------------------
# Tool schema (what LLM sees)
# ----------------------------
# IMPORTANT:
# Keep these aligned with your ToolRegistry tool names and arg shapes.
# I’m including the “core” tools your demo implies: read_file, write_file.
# Add more here ONLY if they exist in ToolRegistry.
TOOL_SPECS: Dict[str, Dict[str, Any]] = {
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file from the working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to the file."},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    "write_file": {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write UTF-8 text content to a file (creates directories if needed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to write."},
                    "content": {"type": "string", "description": "Full file content."},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
}


def _make_tool_call(name: str, args: Dict[str, Any]) -> ToolCall:
    return ToolCall(id=str(uuid.uuid4()), name=name, args=args)


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v is not None and v != "" else default


def _azure_config() -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    endpoint = _env("AZURE_OPENAI_ENDPOINT")
    api_key = _env("AZURE_OPENAI_API_KEY")
    deployment = _env("AZURE_OPENAI_DEPLOYMENT")
    api_version = _env("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    return endpoint, api_key, deployment, api_version


def _build_system_prompt(cwd: Path, allowed_tools: Optional[List[str]]) -> str:
    allowed = allowed_tools or list(TOOL_SPECS.keys())
    allowed_str = ", ".join(allowed) if allowed else "(none)"

    return (
        "You are a senior coding agent. You must be precise, safe, and actionable.\n"
        f"Working directory: {str(cwd)}\n"
        f"Allowed tools: {allowed_str}\n\n"
        "Rules:\n"
        "1) If you need to inspect or change files, use tools instead of guessing.\n"
        "2) Prefer small, correct steps.\n"
        "3) When calling a tool, only call allowed tools and provide valid JSON args.\n"
        "4) If no tool is needed, respond with a clear final answer.\n"
    )


def _tool_list_for_llm(allowed_tools: Optional[List[str]]) -> List[Dict[str, Any]]:
    if not allowed_tools:
        return list(TOOL_SPECS.values())
    return [TOOL_SPECS[name] for name in allowed_tools if name in TOOL_SPECS]


async def _call_azure_chat(
    *,
    endpoint: str,
    api_key: str,
    deployment: str,
    api_version: str,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Uses openai>=1.x AzureOpenAI client if available.
    Returns a normalized dict:
      - {"tool_calls":[{"name":..., "arguments":{...}}, ...]} OR {"content":"..."}
    """
    try:
        from openai import AzureOpenAI  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "openai python package not available. Install: pip install openai"
        ) from e

    client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
    )

    # NOTE: In Azure OpenAI, "model" is your deployment name.
    resp = client.chat.completions.create(
        model=deployment,
        messages=messages,
        tools=tools if tools else None,
        tool_choice="auto" if tools else None,
        temperature=0.2,
    )

    choice = resp.choices[0]
    msg = choice.message

    # Tool calls (newer API)
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        norm_calls: List[Dict[str, Any]] = []
        for tc in tool_calls:
            fn = tc.function
            name = fn.name
            raw_args = fn.arguments or "{}"
            # arguments is a JSON string in the API
            try:
                import json as _json

                args = _json.loads(raw_args)
            except Exception:
                args = {"_raw": raw_args}

            norm_calls.append({"name": name, "arguments": args})
        return {"tool_calls": norm_calls}

    # Otherwise text
    content = msg.content or ""
    return {"content": content}


# ----------------------------
# Public entrypoint
# ----------------------------
async def run_agent_once(
    *,
    user_text: str,
    cwd: Path,
    allowed_tools: Optional[List[str]] = None,
) -> AgentState:
    """
    Real agent step:
      - Uses Azure OpenAI tool calling if configured
      - Else falls back to the old regex demo behavior
    """

    # Always keep a state message log (useful later for multi-turn)
    state: AgentState = {"messages": [{"role": "user", "content": user_text}]}

    # ---------------------------------------
    # Fallback demo behavior (no Azure config)
    # ---------------------------------------
    endpoint, api_key, deployment, api_version = _azure_config()
    if not (endpoint and api_key and deployment and api_version):
        # old behavior so server still runs if env not set
        m = re.match(r"^write\s+(?P<path>[^:]+)::(?P<content>[\s\S]*)$", user_text.strip())
        if m:
            state["pending_tools"] = [
                _make_tool_call("write_file", {"path": m.group("path").strip(), "content": m.group("content")})
            ]
            return state

        m = re.match(r"^read\s+(?P<path>.+)$", user_text.strip())
        if m:
            state["pending_tools"] = [_make_tool_call("read_file", {"path": m.group("path").strip()})]
            return state

        state["final"] = f"Echo: {user_text}"
        return state

    # ---------------------------------------
    # Azure OpenAI tool-calling path
    # ---------------------------------------
    sys_prompt = _build_system_prompt(cwd=cwd, allowed_tools=allowed_tools)
    llm_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_text},
    ]
    tools = _tool_list_for_llm(allowed_tools)

    try:
        out = await _call_azure_chat(
            endpoint=endpoint,
            api_key=api_key,
            deployment=deployment,
            api_version=api_version,
            messages=llm_messages,
            tools=tools,
        )
    except Exception as e:
        # hard-safe fallback: never crash runner due to LLM client errors
        state["final"] = f"LLM error: {str(e)}"
        return state

    if "tool_calls" in out:
        pending: List[ToolCall] = []
        for tc in out["tool_calls"]:
            name = tc.get("name")
            args = tc.get("arguments") or {}
            if not isinstance(args, dict):
                args = {"_raw": args}

            # enforce allowed tools at agent boundary as well
            if allowed_tools and name not in allowed_tools:
                # convert to final message instead of illegal tool call
                state["final"] = (
                    f"Tool '{name}' is not allowed. Allowed tools: {', '.join(allowed_tools)}.\n"
                    "Please rephrase or allow this tool."
                )
                return state

            pending.append(_make_tool_call(name=name, args=args))

        if pending:
            state["pending_tools"] = pending
            return state

    content = (out.get("content") or "").strip()
    state["final"] = content if content else "I have no output."
    return state


# ---------------------------------------
# Optional LangGraph scaffolding
# ---------------------------------------
def build_langgraph_if_available():
    """
    Optional: if you install langgraph, this provides a tiny StateGraph skeleton.
    Not required for runtime.
    """
    try:
        from langgraph.graph import StateGraph, END  # type: ignore
    except Exception:
        return None

    async def plan(state: AgentState) -> AgentState:
        # placeholder: in real graph you'd call run_agent_once here
        return state

    async def router(state: AgentState) -> str:
        return "tools" if state.get("pending_tools") else "final"

    async def tools_node(state: AgentState) -> AgentState:
        return state

    async def finalize(state: AgentState) -> AgentState:
        if not state.get("final"):
            msgs = state.get("messages") or []
            last = msgs[-1]["content"] if msgs else ""
            state["final"] = f"Echo: {last}"
        return state

    g = StateGraph(AgentState)
    g.add_node("plan", plan)
    g.add_node("tools", tools_node)
    g.add_node("final", finalize)
    g.set_entry_point("plan")
    g.add_conditional_edges("plan", router, {"tools": "tools", "final": "final"})
    g.add_edge("tools", "final")
    g.add_edge("final", END)
    return g.compile()
