"""Local test runner for discovering and executing tests without CI/CD."""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional

from app.devops_agent.analyzer import BugInfo, parse_test_output


@dataclass
class TestResults:
    success: bool
    output: str
    passed: int = 0
    failed: int = 0
    bugs: List[BugInfo] = field(default_factory=list)


@dataclass
class LintError:
    file_path: str
    line_number: Optional[int]
    message: str
    code: str = ""


class LocalTestRunner:
    """Run tests and linters locally without relying on CI/CD."""

    def discover_test_files(self, repo_path: str) -> List[str]:
        """Find all test files (test_*.py, *_test.py) under repo_path."""
        test_files: List[str] = []
        for root, _dirs, files in os.walk(repo_path):
            # Skip hidden directories (e.g. .git)
            _dirs[:] = [d for d in _dirs if not d.startswith(".")]
            for fname in files:
                if fname.startswith("test_") or fname.endswith("_test.py"):
                    test_files.append(os.path.join(root, fname))
        return test_files

    def run_pytest(self, repo_path: str) -> TestResults:
        """Execute pytest and capture results."""
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "--tb=short", "-q"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except FileNotFoundError:
            return TestResults(success=False, output="pytest not found")
        except subprocess.TimeoutExpired:
            return TestResults(success=False, output="pytest timed out")

        output = result.stdout + result.stderr
        passed, failed = _count_tests(output)
        bugs = parse_test_output(output)
        return TestResults(
            success=result.returncode == 0,
            output=output,
            passed=passed,
            failed=failed,
            bugs=bugs,
        )

    def run_unittest(self, repo_path: str) -> TestResults:
        """Execute unittest discover and capture results."""
        try:
            result = subprocess.run(
                ["python", "-m", "unittest", "discover", "-v"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except FileNotFoundError:
            return TestResults(success=False, output="python not found")
        except subprocess.TimeoutExpired:
            return TestResults(success=False, output="unittest timed out")

        output = result.stdout + result.stderr
        passed, failed = _count_tests(output)
        bugs = parse_test_output(output)
        return TestResults(
            success=result.returncode == 0,
            output=output,
            passed=passed,
            failed=failed,
            bugs=bugs,
        )

    def run_syntax_check(self, repo_path: str) -> List[LintError]:
        """Run python -m py_compile on all .py files to detect syntax errors."""
        errors: List[LintError] = []
        for root, _dirs, files in os.walk(repo_path):
            _dirs[:] = [d for d in _dirs if not d.startswith(".")]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    result = subprocess.run(
                        ["python", "-m", "py_compile", fpath],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode != 0:
                        rel_path = os.path.relpath(fpath, repo_path)
                        errors.append(LintError(
                            file_path=rel_path,
                            line_number=None,
                            message=result.stderr.strip(),
                            code="SyntaxError",
                        ))
                except FileNotFoundError:
                    break
        return errors

    def run_linters(self, repo_path: str) -> List[LintError]:
        """Run flake8 if available and return lint errors."""
        errors: List[LintError] = []
        try:
            result = subprocess.run(
                ["python", "-m", "flake8", "--format=%(path)s:%(row)d:%(col)d: %(code)s %(text)s", "."],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            for line in result.stdout.splitlines():
                parts = line.split(":", 3)
                if len(parts) >= 4:
                    try:
                        lineno = int(parts[1])
                    except ValueError:
                        lineno = None
                    rest = parts[3].strip()
                    code = rest.split()[0] if rest else ""
                    errors.append(LintError(
                        file_path=parts[0],
                        line_number=lineno,
                        message=rest,
                        code=code,
                    ))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return errors

    def run(self, repo_path: str) -> TestResults:
        """Auto-detect test framework and run tests; fall back to unittest."""
        test_files = self.discover_test_files(repo_path)
        if not test_files:
            return TestResults(
                success=True,
                output="No test files found.",
                passed=0,
                failed=0,
            )
        # Prefer pytest
        result = self.run_pytest(repo_path)
        if "pytest" in result.output or result.passed > 0 or result.failed > 0:
            return result
        # Fall back to unittest
        return self.run_unittest(repo_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_tests(output: str) -> tuple[int, int]:
    """Extract passing/failing counts from pytest/unittest summary."""
    passed = failed = 0
    m = re.search(r"(\d+) passed", output)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+) failed", output)
    if m:
        failed = int(m.group(1))
    # unittest format: "Ran N tests" / "FAILED (failures=N)"
    if passed == 0 and failed == 0:
        m = re.search(r"Ran (\d+) test", output)
        total = int(m.group(1)) if m else 0
        m = re.search(r"failures=(\d+)", output)
        failed = int(m.group(1)) if m else 0
        passed = total - failed
    return passed, failed
