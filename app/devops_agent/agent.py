from __future__ import annotations

import asyncio
import datetime
import os
import subprocess
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from app.devops_agent.analyzer import BugInfo, parse_test_output
from app.devops_agent.ci_monitor import CIMonitor
from app.devops_agent.fixer import FixGenerator
from app.devops_agent.git_manager import GitManager
from app.devops_agent.scorer import calculate_score
from app.devops_agent.test_runner import LocalTestRunner
from app.models.devops_models import (
    CIRun,
    FixRecord,
    JobProgress,
    JobStatus,
    ScoreBreakdown,
)

MAX_ITERATIONS = 5


class DevOpsAgent:
    def __init__(self, repo_url: str, team_name: str, team_leader: str) -> None:
        self.repo_url = repo_url
        self.team_name = team_name
        self.team_leader = team_leader

        token = os.getenv("GITHUB_TOKEN")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

        self.git = GitManager(repo_url, token=token)
        self.ci = CIMonitor(repo_url, token=token)
        self.fixer = FixGenerator(
            endpoint=azure_endpoint,
            api_key=azure_key,
            deployment=azure_deployment,
        )
        self.local_runner = LocalTestRunner()

    @property
    def branch_name(self) -> str:
        return GitManager._sanitize_branch_name(self.team_name, self.team_leader)

    def _branch_url(self) -> Optional[str]:
        """Return the GitHub URL for the branch."""
        parsed = urlparse(self.repo_url)
        if parsed.hostname and (parsed.hostname == "github.com" or parsed.hostname.endswith(".github.com")):
            repo_path = parsed.path.rstrip("/").removesuffix(".git")
            return f"https://github.com{repo_path}/tree/{self.branch_name}"
        return None

    async def run(self, job_id: str, job_store: dict) -> None:
        repo_path = f"/tmp/{job_id}"
        start_time = asyncio.get_event_loop().time()
        commit_count = 0

        # Initialize job status
        job_store[job_id] = JobStatus(status="running").model_dump()

        try:
            # Step 1: Clone repository
            await asyncio.to_thread(self.git.clone, repo_path)

            # Step 2: Create branch IMMEDIATELY and push to remote
            branch = await asyncio.to_thread(
                self.git.create_and_checkout_branch,
                repo_path,
                self.team_name,
                self.team_leader,
            )
            job_store[job_id]["branch_name"] = branch
            job_store[job_id]["branch_url"] = self._branch_url()

            # Push the branch to remote so it exists on GitHub
            try:
                await asyncio.to_thread(self.git.push_branch, repo_path, branch)
            except subprocess.CalledProcessError:
                pass  # Non-fatal: push may fail if no auth; branch is still local

            fixes: List[FixRecord] = []
            ci_runs: List[CIRun] = []

            # Determine whether the repo has CI/CD workflows
            has_ci = self.ci.has_workflows(repo_path)

            for iteration in range(1, MAX_ITERATIONS + 1):
                _update_progress(job_store, job_id, iteration, MAX_ITERATIONS)

                # Step 3: Run tests locally (preferred) or via CI/CD
                if has_ci:
                    success, output = await asyncio.to_thread(self.run_tests, repo_path)
                else:
                    result = await asyncio.to_thread(self.local_runner.run, repo_path)
                    success, output = result.success, result.output

                # Count passing/failing
                passing, failing = _count_tests(output)
                _update_test_counts(job_store, job_id, passing, failing)

                timestamp = datetime.datetime.utcnow().isoformat()

                if success:
                    ci_runs.append(CIRun(
                        iteration=iteration,
                        status="success",
                        timestamp=timestamp,
                    ))
                    job_store[job_id]["ci_runs"] = [r.model_dump() for r in ci_runs]
                    break

                # Parse failures and attempt fixes
                bugs = parse_test_output(output)
                for bug in bugs:
                    fix_record = await self._attempt_fix(repo_path, bug)
                    if fix_record:
                        fixes.append(fix_record)
                        job_store[job_id]["fixes"] = [f.model_dump() for f in fixes]

                # Commit if there are staged changes
                try:
                    sha = await asyncio.to_thread(
                        self.git.commit_and_push,
                        repo_path,
                        f"[AI-AGENT] Fix iteration {iteration}",
                    )
                    commit_count += 1
                except subprocess.CalledProcessError:
                    # Nothing to commit
                    pass

                # Check CI if available
                if has_ci:
                    ci_result = await self.ci.wait_for_completion(self.branch_name, timeout_seconds=120)
                    ci_status = ci_result.get("conclusion") or ci_result.get("status") or "unknown"
                    ci_runs.append(CIRun(
                        iteration=iteration,
                        status=ci_status,
                        timestamp=timestamp,
                        logs=ci_result.get("html_url"),
                    ))
                else:
                    ci_runs.append(CIRun(
                        iteration=iteration,
                        status="local",
                        timestamp=timestamp,
                    ))
                job_store[job_id]["ci_runs"] = [r.model_dump() for r in ci_runs]

            # Final score
            elapsed = asyncio.get_event_loop().time() - start_time
            score_dict = calculate_score(elapsed, commit_count)
            score = ScoreBreakdown(**score_dict)

            job_store[job_id]["status"] = "completed"
            job_store[job_id]["score"] = score.model_dump()

        except Exception as exc:  # noqa: BLE001
            job_store[job_id]["status"] = "failed"
            job_store[job_id].setdefault("error", str(exc))
        finally:
            await asyncio.to_thread(self.git.cleanup, repo_path)

    async def _attempt_fix(self, repo_path: str, bug: BugInfo) -> Optional[FixRecord]:
        """Try to generate and apply a fix for a single bug. Returns FixRecord."""
        abs_path = os.path.join(repo_path, bug.file_path)
        if not os.path.isfile(abs_path):
            return None
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()

            new_content = await asyncio.to_thread(self.fixer.generate_fix, bug, content)
            if new_content is None:
                return None

            if not self.fixer.validate_syntax(abs_path, new_content):
                return FixRecord(
                    file=bug.file_path,
                    bug_type=bug.bug_type,
                    line_number=bug.line_number,
                    commit_message=f"Fix {bug.bug_type} in {bug.file_path}",
                    status="failed",
                )

            await asyncio.to_thread(self.fixer.apply_fix, abs_path, new_content)
            return FixRecord(
                file=bug.file_path,
                bug_type=bug.bug_type,
                line_number=bug.line_number,
                commit_message=f"Fix {bug.bug_type} in {bug.file_path}",
                status="fixed",
            )
        except Exception:  # noqa: BLE001
            return FixRecord(
                file=bug.file_path,
                bug_type=bug.bug_type,
                line_number=bug.line_number,
                commit_message=f"Attempted fix for {bug.bug_type} in {bug.file_path}",
                status="failed",
            )

    def run_tests(self, repo_path: str) -> Tuple[bool, str]:
        """Run pytest in repo_path. Returns (success, output)."""
        result = subprocess.run(
            ["python", "-m", "pytest", "--tb=short", "-q"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output

    def discover_test_files(self, repo_path: str) -> List[str]:
        """Find test_*.py and *_test.py files under repo_path."""
        test_files: List[str] = []
        for root, _dirs, files in os.walk(repo_path):
            for fname in files:
                if fname.startswith("test_") or fname.endswith("_test.py"):
                    test_files.append(os.path.join(root, fname))
        return test_files


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _update_progress(job_store: dict, job_id: str, iteration: int, total: int) -> None:
    job_store[job_id]["progress"] = JobProgress(
        current_iteration=iteration,
        total_iterations=total,
    ).model_dump()


def _update_test_counts(job_store: dict, job_id: str, passing: int, failing: int) -> None:
    if "progress" not in job_store[job_id]:
        job_store[job_id]["progress"] = JobProgress().model_dump()
    job_store[job_id]["progress"]["tests_passing"] = passing
    job_store[job_id]["progress"]["tests_failing"] = failing


def _count_tests(output: str) -> Tuple[int, int]:
    """Extract passing/failing counts from pytest summary line."""
    import re
    passed = failed = 0
    m = re.search(r"(\d+) passed", output)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+) failed", output)
    if m:
        failed = int(m.group(1))
    return passed, failed
