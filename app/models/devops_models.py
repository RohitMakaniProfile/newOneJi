from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, HttpUrl, field_validator


class AnalyzeRequest(BaseModel):
    repo_url: str
    team_name: str
    team_leader: str

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: str) -> str:
        # Basic validation that it looks like a URL
        if not v.startswith("http"):
            raise ValueError("repo_url must be a valid HTTP/HTTPS URL")
        return v


class AnalyzeResponse(BaseModel):
    job_id: str
    status: str


class BugType(str, Enum):
    LINTING = "LINTING"
    SYNTAX = "SYNTAX"
    LOGIC = "LOGIC"
    TYPE_ERROR = "TYPE_ERROR"
    IMPORT = "IMPORT"
    INDENTATION = "INDENTATION"


class FixRecord(BaseModel):
    file: str
    bug_type: BugType
    line_number: Optional[int] = None
    commit_message: str
    status: str = "fixed"


class CIRun(BaseModel):
    iteration: int
    status: str
    timestamp: str
    logs: Optional[str] = None


class ScoreBreakdown(BaseModel):
    base_score: int = 100
    speed_bonus: int = 0
    efficiency_penalty: int = 0
    final_score: int = 100


class JobProgress(BaseModel):
    current_iteration: int = 0
    total_iterations: int = 5
    tests_passing: int = 0
    tests_failing: int = 0


class JobStatus(BaseModel):
    status: str = "running"
    progress: JobProgress = JobProgress()
    fixes: List[FixRecord] = []
    ci_runs: List[CIRun] = []
    score: Optional[ScoreBreakdown] = None
