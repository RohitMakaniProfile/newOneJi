from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    args: Dict[str, Any]


@dataclass
class ToolDecision:
    call_id: str
    decision: str  # approve|reject
    reason: Optional[str] = None


@dataclass
class ToolResult:
    call_id: str
    ok: bool
    output: str


class Tool(Protocol):
    name: str
    requires_approval: bool

    async def run(self, *, cwd: Path, args: Dict[str, Any]) -> str: ...


class EchoTool:
    name = "echo"
    requires_approval = False

    async def run(self, *, cwd: Path, args: Dict[str, Any]) -> str:
        return str(args.get("text", ""))


class ReadFileTool:
    name = "read_file"
    requires_approval = False

    async def run(self, *, cwd: Path, args: Dict[str, Any]) -> str:
        p = (cwd / str(args["path"])).resolve()
        # Basic safety: keep within project root
        if not str(p).startswith(str(cwd.resolve())):
            raise ValueError("Path escapes cwd")
        return p.read_text(encoding="utf-8")


class WriteFileTool:
    name = "write_file"
    requires_approval = True

    async def run(self, *, cwd: Path, args: Dict[str, Any]) -> str:
        p = (cwd / str(args["path"])).resolve()
        if not str(p).startswith(str(cwd.resolve())):
            raise ValueError("Path escapes cwd")
        content = str(args.get("content", ""))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {p}"


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {
            EchoTool.name: EchoTool(),
            ReadFileTool.name: ReadFileTool(),
            WriteFileTool.name: WriteFileTool(),
        }

    def list(self) -> List[str]:
        return sorted(self._tools.keys())

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def filter_allowed(self, allowed: Optional[List[str]]) -> "ToolRegistry":
        if not allowed:
            return self
        reg = ToolRegistry()
        reg._tools = {k: v for k, v in self._tools.items() if k in set(allowed)}
        return reg

    async def execute(self, *, tool_call: ToolCall, cwd: Path) -> ToolResult:
        tool = self.get(tool_call.name)
        if not tool:
            return ToolResult(call_id=tool_call.id, ok=False, output=f"Unknown tool: {tool_call.name}")
        try:
            out = await tool.run(cwd=cwd, args=tool_call.args)
            return ToolResult(call_id=tool_call.id, ok=True, output=out)
        except Exception as e:
            return ToolResult(call_id=tool_call.id, ok=False, output=f"{type(e).__name__}: {e}")
