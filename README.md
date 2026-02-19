# Autonomous DevOps Agent (FastAPI + React)

A full-stack system that analyzes GitHub repositories, identifies test failures, generates AI-powered fixes, and monitors CI/CD pipelines — with a live React dashboard.

## Architecture

```
┌─────────────────────────────────────┐    ┌───────────────────────────┐
│        React Dashboard (Vite)       │◄──►│   FastAPI Backend          │
│  - InputSection                     │SSE │  - DevOps Agent Engine     │
│  - RunSummaryCard                   │    │  - Bug Analyzer            │
│  - ScoreBreakdownPanel              │    │  - Fix Generator (LLM)     │
│  - FixesAppliedTable                │    │  - Git Manager             │
│  - CIStatusTimeline                 │    │  - CI/CD Monitor           │
└─────────────────────────────────────┘    └───────────────────────────┘
```

## File Structure

```
├── app/
│   ├── devops_agent/
│   │   ├── agent.py          # Main orchestration (up to 5 iterations)
│   │   ├── analyzer.py       # Test failure classification
│   │   ├── fixer.py          # LLM-powered fix generation
│   │   ├── git_manager.py    # Git clone/branch/commit/push
│   │   ├── ci_monitor.py     # GitHub Actions polling
│   │   └── scorer.py         # Scoring system
│   ├── api/
│   │   ├── routes.py         # Existing session/run routes
│   │   └── devops_routes.py  # DevOps API endpoints
│   ├── models/
│   │   └── devops_models.py  # Pydantic models
│   └── main.py
├── frontend/                  # React + TypeScript + Tailwind
│   └── src/
│       ├── components/
│       ├── pages/Dashboard.tsx
│       ├── services/api.ts
│       └── types/index.ts
├── tests/
│   └── test_devops_agent.py
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Quick Start

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your credentials
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
```

### Docker (full stack)

```bash
cp .env.example .env   # fill in your credentials
docker-compose up --build
```

## Environment Variables

| Variable | Description |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name (e.g., `gpt-4`) |
| `AZURE_OPENAI_API_VERSION` | API version (e.g., `2024-02-15-preview`) |
| `GITHUB_TOKEN` | GitHub personal access token for private repos and CI polling |
| `MAX_ITERATIONS` | Maximum fix iterations (default: 5) |
| `STAKPAK_CORS_ORIGINS` | Comma-separated allowed CORS origins |

## DevOps Agent API

### Start Analysis

```bash
curl -s -X POST http://localhost:8000/api/devops/analyze \
  -H 'content-type: application/json' \
  -d '{
    "repo_url": "https://github.com/owner/repo",
    "team_name": "RIFT ORGANISERS",
    "team_leader": "Saiyam Kumar"
  }'
```

Response: `{"job_id": "uuid", "status": "running"}`

### Poll Status

```bash
curl http://localhost:8000/api/devops/status/{job_id}
```

### Stream Updates (SSE)

```bash
curl -N "http://localhost:8000/api/devops/stream/{job_id}"
```

## Scoring System

| Component | Points |
|---|---|
| Base score | 100 |
| Speed bonus (under 5 minutes) | +10 |
| Efficiency penalty (per commit over 20) | -2 each |
| Minimum score | 0 |

## Running Tests

```bash
python -m pytest tests/test_devops_agent.py -v
```

## Deployment

### Frontend (Vercel / Netlify)

- Build command: `npm run build`
- Output directory: `dist`
- Set `VITE_API_URL` to your backend URL

### Backend (Railway / Render)

- Set all environment variables from `.env.example`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

---

*Original scaffold notes:* Sessions, Runs, Tool approval loop (pause/resume), SSE realtime updates, and SQLite persistence remain available at `/api/sessions/*`.
