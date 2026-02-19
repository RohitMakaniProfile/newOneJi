from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.event_bus import EventBus
from app.core.tools import ToolDecision, ToolRegistry, ToolCall
from app.storage.store import Store
from app.agents.langgraph_agent import run_agent_once


class SessionRunner:
    """
    Owns a single live run for a session.
    Implements iterative reasoning loop with tool gating.
    """

    def __init__(
        self,
        *,
        store: Store,
        bus: EventBus,
        registry: ToolRegistry,
        session_id: str,
        cwd: Path,
        model: Optional[str],
        auto_approve: bool,
        max_steps: int,
        allowed_tools: Optional[List[str]],
    ):
        self.store = store
        self.bus = bus
        self.registry = registry.filter_allowed(allowed_tools)
        self.session_id = session_id
        self.cwd = cwd
        self.model = model
        self.auto_approve = auto_approve
        self.max_steps = max_steps
        self.allowed_tools = allowed_tools

        self._pending: Dict[str, ToolCall] = {}
        self._decisions: asyncio.Queue[ToolDecision] = asyncio.Queue()
        self._cancel = asyncio.Event()

        self.run_id = store.create_run(
            session_id=session_id,
            model=model,
            auto_approve=auto_approve,
            max_steps=max_steps,
            allowed_tools_json=json.dumps(allowed_tools) if allowed_tools else None,
        ).id

    # -------------------------------------------------------
    # Public API
    # -------------------------------------------------------

    async def cancel(self) -> None:
        self._cancel.set()
        self.store.update_run_status(self.run_id, "cancelled")
        await self._emit("run.cancelled", {})

    async def submit_decision(self, decision: ToolDecision) -> None:
        await self._decisions.put(decision)

    # -------------------------------------------------------
    # Main Execution Loop
    # -------------------------------------------------------

    async def run(self, user_text: str) -> None:
        topic = f"session:{self.session_id}"

        try:
            self.store.update_run_status(self.run_id, "running")
            await self._emit("run.started", {
                "model": self.model,
                "auto_approve": self.auto_approve,
                "max_steps": self.max_steps,
            })

            self.store.add_message(self.session_id, "user", user_text, run_id=self.run_id)
            await self._emit("assistant.user_message", {"text": user_text})

            state_input = {
                "user_text": user_text,
                "history": [],
            }

            step = 0

            while step < self.max_steps and not self._cancel.is_set():
                step += 1
                await self._emit("run.step.started", {"step": step})

                # -----------------------------------
                # Agent reasoning step
                # -----------------------------------
                state = await run_agent_once(
                    user_text=state_input["user_text"],
                    cwd=self.cwd,
                    allowed_tools=self.allowed_tools,
                )

                pending_tools: List[ToolCall] = list(state.get("pending_tools") or [])
                final_message: Optional[str] = state.get("final")

                # -----------------------------------
                # Tool Handling
                # -----------------------------------
                if pending_tools:
                    for call in pending_tools:
                        self._pending[call.id] = call

                    await self._emit("tool.calls.proposed", {
                        "tools": [
                            {"id": c.id, "name": c.name, "args": c.args}
                            for c in pending_tools
                        ],
                        "auto_approve": self.auto_approve,
                        "step": step,
                    })

                    if not self.auto_approve:
                        self.store.update_run_status(self.run_id, "paused")
                        await self._emit("run.paused", {
                            "reason": "awaiting_tool_approval",
                            "step": step,
                        })

                        await self._handle_decisions_loop()
                    else:
                        for call in pending_tools:
                            await self._execute_tool(call)

                    continue  # loop continues after tool execution

                # -----------------------------------
                # Final Response
                # -----------------------------------
                if final_message:
                    self.store.add_message(
                        self.session_id,
                        "assistant",
                        final_message,
                        run_id=self.run_id,
                    )
                    await self._emit("assistant.final", {
                        "text": final_message,
                        "step": step,
                    })
                    break

            # -----------------------------------
            # Completion
            # -----------------------------------
            if self._cancel.is_set():
                self.store.update_run_status(self.run_id, "cancelled")
                await self._emit("run.cancelled", {})
            else:
                self.store.update_run_status(self.run_id, "completed")
                await self._emit("run.completed", {"steps_used": step})

        except Exception as e:
            self.store.update_run_status(self.run_id, "failed")
            await self._emit("run.error", {
                "error": str(e),
            })

    # -------------------------------------------------------
    # Tool Decision Handling
    # -------------------------------------------------------

    async def _handle_decisions_loop(self) -> None:
        while self._pending and not self._cancel.is_set():
            decision = await self._decisions.get()

            call = self._pending.get(decision.call_id)
            if not call:
                continue

            if decision.decision == "approve":
                await self._emit("tool.call.approved", {
                    "tool_id": call.id,
                    "name": call.name,
                })
                await self._execute_tool(call)
            else:
                await self._emit("tool.call.rejected", {
                    "tool_id": call.id,
                    "name": call.name,
                    "reason": decision.reason,
                })

            self._pending.pop(call.id, None)

        if not self._pending:
            self.store.update_run_status(self.run_id, "running")
            await self._emit("run.resumed", {})

    # -------------------------------------------------------
    # Tool Execution
    # -------------------------------------------------------

    async def _execute_tool(self, call: ToolCall) -> None:
        result = await self.registry.execute(tool_call=call, cwd=self.cwd)

        await self._emit("tool.result", {
            "tool_id": call.id,
            "name": call.name,
            "ok": result.ok,
            "output": result.output,
        })

    # -------------------------------------------------------
    # Event Emission
    # -------------------------------------------------------

    async def _emit(self, type_: str, data: Dict[str, Any]) -> None:
        # persist to DB
        self.store.add_event(
            self.session_id,
            None,  # bus assigns ID
            type_,
            json.dumps(data, ensure_ascii=False),
            None,
        )

        # publish via upgraded bus
        await self.bus.publish(
            topic=f"session:{self.session_id}",
            type=type_,
            data=data,
            source="runner",
            correlation_id=self.run_id,
        )
