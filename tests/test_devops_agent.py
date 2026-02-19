"""Tests for the DevOps agent modules."""
from __future__ import annotations

import pytest

from app.devops_agent.analyzer import BugInfo, parse_test_output
from app.devops_agent.scorer import calculate_score
from app.models.devops_models import BugType


# ---------------------------------------------------------------------------
# Scorer tests
# ---------------------------------------------------------------------------

class TestCalculateScore:
    def test_base_score_only(self):
        result = calculate_score(total_time_seconds=600, commit_count=5)
        assert result["base_score"] == 100
        assert result["speed_bonus"] == 0
        assert result["efficiency_penalty"] == 0
        assert result["final_score"] == 100

    def test_speed_bonus_earned(self):
        result = calculate_score(total_time_seconds=200, commit_count=5)
        assert result["speed_bonus"] == 10
        assert result["final_score"] == 110

    def test_efficiency_penalty(self):
        result = calculate_score(total_time_seconds=600, commit_count=22)
        assert result["efficiency_penalty"] == 4  # (22-20)*2
        assert result["final_score"] == 96

    def test_both_bonus_and_penalty(self):
        result = calculate_score(total_time_seconds=100, commit_count=25)
        assert result["speed_bonus"] == 10
        assert result["efficiency_penalty"] == 10  # (25-20)*2
        assert result["final_score"] == 100

    def test_no_penalty_below_threshold(self):
        result = calculate_score(total_time_seconds=600, commit_count=20)
        assert result["efficiency_penalty"] == 0

    def test_score_never_goes_negative(self):
        result = calculate_score(total_time_seconds=600, commit_count=200)
        assert result["final_score"] >= 0


# ---------------------------------------------------------------------------
# Analyzer tests
# ---------------------------------------------------------------------------

PYTEST_OUTPUT_SYNTAX_ERROR = """\
FAILED tests/test_example.py::test_something - SyntaxError: invalid syntax
  File "tests/test_example.py", line 10
    def bad_func(
               ^
SyntaxError: invalid syntax
"""

PYTEST_OUTPUT_IMPORT_ERROR = """\
FAILED tests/test_imports.py::test_module - ImportError: cannot import name 'foo' from 'bar'
ImportError: cannot import name 'foo' from 'bar' (bar/__init__.py)
"""

PYTEST_OUTPUT_ASSERTION = """\
FAILED tests/test_logic.py::test_add - AssertionError: assert 3 == 5
AssertionError: assert 3 == 5
 +  where 3 = add(1, 2)
"""

PYTEST_OUTPUT_INDENTATION = """\
FAILED tests/test_indent.py::test_x - IndentationError: unexpected indent
  File "tests/test_indent.py", line 5
    x = 1
    ^
IndentationError: unexpected indent
"""

PYTEST_OUTPUT_TYPE_ERROR = """\
FAILED tests/test_types.py::test_types - TypeError: unsupported operand type(s) for +: 'int' and 'str'
TypeError: unsupported operand type(s) for +: 'int' and 'str'
"""


class TestParseTestOutput:
    def test_empty_output(self):
        bugs = parse_test_output("")
        assert bugs == []

    def test_detects_syntax_error(self):
        bugs = parse_test_output(PYTEST_OUTPUT_SYNTAX_ERROR)
        assert len(bugs) >= 1
        assert any(b.bug_type == BugType.SYNTAX for b in bugs)

    def test_detects_import_error(self):
        bugs = parse_test_output(PYTEST_OUTPUT_IMPORT_ERROR)
        assert len(bugs) >= 1
        assert any(b.bug_type == BugType.IMPORT for b in bugs)

    def test_detects_logic_error(self):
        bugs = parse_test_output(PYTEST_OUTPUT_ASSERTION)
        assert len(bugs) >= 1
        assert any(b.bug_type == BugType.LOGIC for b in bugs)

    def test_detects_indentation_error(self):
        bugs = parse_test_output(PYTEST_OUTPUT_INDENTATION)
        assert len(bugs) >= 1
        assert any(b.bug_type == BugType.INDENTATION for b in bugs)

    def test_detects_type_error(self):
        bugs = parse_test_output(PYTEST_OUTPUT_TYPE_ERROR)
        assert len(bugs) >= 1
        assert any(b.bug_type == BugType.TYPE_ERROR for b in bugs)

    def test_extracts_file_path(self):
        bugs = parse_test_output(PYTEST_OUTPUT_ASSERTION)
        assert any("test_logic.py" in b.file_path for b in bugs)

    def test_extracts_line_number(self):
        bugs = parse_test_output(PYTEST_OUTPUT_SYNTAX_ERROR)
        line_numbers = [b.line_number for b in bugs if b.line_number is not None]
        assert len(line_numbers) >= 1

    def test_bug_info_has_required_fields(self):
        bugs = parse_test_output(PYTEST_OUTPUT_ASSERTION)
        for bug in bugs:
            assert isinstance(bug, BugInfo)
            assert bug.file_path
            assert isinstance(bug.bug_type, BugType)
            assert bug.error_text


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

from app.models.devops_models import (
    AnalyzeRequest,
    JobStatus,
    JobProgress,
    ScoreBreakdown,
    FixRecord,
    CIRun,
)


class TestAnalyzeRequest:
    def test_valid_http_url(self):
        req = AnalyzeRequest(
            repo_url="https://github.com/owner/repo",
            team_name="TEAM",
            team_leader="Leader",
        )
        assert req.repo_url == "https://github.com/owner/repo"

    def test_invalid_url_raises(self):
        with pytest.raises(Exception):
            AnalyzeRequest(
                repo_url="not-a-url",
                team_name="TEAM",
                team_leader="Leader",
            )


class TestJobStatus:
    def test_default_status(self):
        status = JobStatus()
        assert status.status == "running"
        assert status.fixes == []
        assert status.ci_runs == []
        assert status.score is None

    def test_score_breakdown_defaults(self):
        score = ScoreBreakdown()
        assert score.base_score == 100
        assert score.speed_bonus == 0
        assert score.efficiency_penalty == 0
        assert score.final_score == 100

    def test_job_progress_defaults(self):
        progress = JobProgress()
        assert progress.current_iteration == 0
        assert progress.total_iterations == 5


class TestFixRecord:
    def test_fix_record_creation(self):
        fix = FixRecord(
            file="src/main.py",
            bug_type=BugType.SYNTAX,
            line_number=42,
            commit_message="[AI-AGENT] Fix SYNTAX in src/main.py at line 42",
            status="fixed",
        )
        assert fix.file == "src/main.py"
        assert fix.bug_type == BugType.SYNTAX
        assert fix.line_number == 42
        assert fix.status == "fixed"


class TestCIRun:
    def test_ci_run_creation(self):
        run = CIRun(
            iteration=1,
            status="success",
            timestamp="2024-01-01T00:00:00",
        )
        assert run.iteration == 1
        assert run.status == "success"
        assert run.logs is None
