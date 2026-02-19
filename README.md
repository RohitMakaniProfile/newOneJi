# Stakpak Python Agent (FastAPI + SSE)

This is a minimal backend scaffold for an agent runtime with:
- Sessions
- Runs
- Tool approval loop (pause/resume)
- Server-Sent Events (SSE) for realtime UI updates
- SQLite persistence (sessions/messages/events)

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
```

## Try it

1) Create a session
```bash
curl -s -X POST http://localhost:8000/api/sessions \
  -H 'content-type: application/json' \
  -d '{"title":"demo","cwd":"."}'
```

2) Open SSE stream in another terminal (replace SESSION_ID)
```bash
curl -N "http://localhost:8000/api/sessions/SESSION_ID/events/stream"
```

3) Start a run
```bash
curl -s -X POST http://localhost:8000/api/sessions/SESSION_ID/runs \
  -H 'content-type: application/json' \
  -d '{"user_message":"write notes.txt::hello from agent","auto_approve":false}'
```

4) Approve the proposed tool (replace RUN_ID and TOOL_ID from SSE TOOL_PROPOSAL)
```bash
curl -s -X POST http://localhost:8000/api/sessions/SESSION_ID/runs/RUN_ID/tools/TOOL_ID/decision \
  -H 'content-type: application/json' \
  -d '{"decision":"approve"}'
```

## Notes
- The current agent is a tiny rule-based placeholder in `app/agents/langgraph_agent.py`.
- Swap `run_agent_once()` with a real LangGraph graph + model calls when ready.
