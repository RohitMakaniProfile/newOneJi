"""Tests for critical fixes: CI/CD detection and branch creation."""
from __future__ import annotations

import os
import tempfile

import pytest

from app.devops_agent.git_manager import GitManager
from app.devops_agent.test_runner import LocalTestRunner
from app.devops_agent.ci_monitor import CIMonitor
from app.models.devops_models import JobStatus


# ---------------------------------------------------------------------------
# Branch name sanitization
# ---------------------------------------------------------------------------

class TestBranchNameSanitization:
    def test_spaces_replaced(self):
        name = GitManager._sanitize_branch_name("RIFT ORGANISERS", "Saiyam Kumar")
        assert " " not in name

    def test_correct_format(self):
        name = GitManager._sanitize_branch_name("RIFT ORGANISERS", "Saiyam Kumar")
        assert name == "RIFT_ORGANISERS_Saiyam_Kumar_AI_Fix"

    def test_suffix_always_present(self):
        name = GitManager._sanitize_branch_name("TEAM", "Leader")
        assert name.endswith("_AI_Fix")

    def test_special_characters_removed(self):
        name = GitManager._sanitize_branch_name("Team@#1", "Lead/er")
        assert "@" not in name
        assert "#" not in name
        assert "/" not in name

    def test_hyphens_replaced(self):
        name = GitManager._sanitize_branch_name("Team-A", "My-Leader")
        assert "-" not in name
        assert "Team_A_My_Leader_AI_Fix" == name

    def test_no_double_underscores(self):
        name = GitManager._sanitize_branch_name("TEAM  A", "Lead  er")
        assert "__" not in name

    def test_simple_names(self):
        name = GitManager._sanitize_branch_name("ALPHA", "Bob")
        assert name == "ALPHA_Bob_AI_Fix"


# ---------------------------------------------------------------------------
# Local test discovery
# ---------------------------------------------------------------------------

class TestLocalTestDiscovery:
    def test_finds_test_prefix_files(self):
        runner = LocalTestRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "test_foo.py"), "w").close()
            open(os.path.join(tmpdir, "bar.py"), "w").close()
            files = runner.discover_test_files(tmpdir)
            assert any("test_foo.py" in f for f in files)
            assert not any("bar.py" in f for f in files)

    def test_finds_test_suffix_files(self):
        runner = LocalTestRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "foo_test.py"), "w").close()
            files = runner.discover_test_files(tmpdir)
            assert any("foo_test.py" in f for f in files)

    def test_no_tests_returns_empty(self):
        runner = LocalTestRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "main.py"), "w").close()
            files = runner.discover_test_files(tmpdir)
            assert files == []

    def test_skips_hidden_directories(self):
        runner = LocalTestRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            hidden = os.path.join(tmpdir, ".git")
            os.makedirs(hidden)
            open(os.path.join(hidden, "test_hidden.py"), "w").close()
            files = runner.discover_test_files(tmpdir)
            assert files == []


# ---------------------------------------------------------------------------
# Local test execution
# ---------------------------------------------------------------------------

class TestLocalTestExecution:
    def test_run_with_no_tests_returns_success(self):
        runner = LocalTestRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.run(tmpdir)
            assert result.success is True
            assert "No test files found" in result.output

    def test_run_passing_test(self):
        runner = LocalTestRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_pass.py")
            with open(test_file, "w") as f:
                f.write("def test_always_passes():\n    assert 1 == 1\n")
            result = runner.run(tmpdir)
            assert result.success is True
            assert result.passed >= 1

    def test_run_failing_test(self):
        runner = LocalTestRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_fail.py")
            with open(test_file, "w") as f:
                f.write("def test_always_fails():\n    assert 1 == 2\n")
            result = runner.run(tmpdir)
            assert result.success is False
            assert result.failed >= 1


# ---------------------------------------------------------------------------
# CI/CD workflow detection
# ---------------------------------------------------------------------------

class TestCIMonitorWorkflowDetection:
    def test_has_workflows_false_when_no_dir(self):
        monitor = CIMonitor("https://github.com/owner/repo")
        with tempfile.TemporaryDirectory() as tmpdir:
            assert monitor.has_workflows(tmpdir) is False

    def test_has_workflows_false_when_empty_dir(self):
        monitor = CIMonitor("https://github.com/owner/repo")
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, ".github", "workflows"))
            assert monitor.has_workflows(tmpdir) is False

    def test_has_workflows_true_with_yml(self):
        monitor = CIMonitor("https://github.com/owner/repo")
        with tempfile.TemporaryDirectory() as tmpdir:
            wf_dir = os.path.join(tmpdir, ".github", "workflows")
            os.makedirs(wf_dir)
            open(os.path.join(wf_dir, "ci.yml"), "w").close()
            assert monitor.has_workflows(tmpdir) is True

    def test_has_workflows_true_with_yaml(self):
        monitor = CIMonitor("https://github.com/owner/repo")
        with tempfile.TemporaryDirectory() as tmpdir:
            wf_dir = os.path.join(tmpdir, ".github", "workflows")
            os.makedirs(wf_dir)
            open(os.path.join(wf_dir, "ci.yaml"), "w").close()
            assert monitor.has_workflows(tmpdir) is True


# ---------------------------------------------------------------------------
# JobStatus model has branch fields
# ---------------------------------------------------------------------------

class TestJobStatusBranchFields:
    def test_branch_name_defaults_none(self):
        status = JobStatus()
        assert status.branch_name is None

    def test_branch_url_defaults_none(self):
        status = JobStatus()
        assert status.branch_url is None

    def test_branch_name_can_be_set(self):
        status = JobStatus(branch_name="TEAM_Leader_AI_Fix")
        assert status.branch_name == "TEAM_Leader_AI_Fix"

    def test_branch_url_can_be_set(self):
        url = "https://github.com/owner/repo/tree/TEAM_Leader_AI_Fix"
        status = JobStatus(branch_url=url)
        assert status.branch_url == url


# ---------------------------------------------------------------------------
# GitManager token injection
# ---------------------------------------------------------------------------

class TestGitManagerTokenInjection:
    def test_token_injected_into_url(self):
        gm = GitManager("https://github.com/owner/repo.git", token="mytoken")
        url = gm._inject_token("https://github.com/owner/repo.git")
        assert "mytoken" in url
        assert "x-access-token" in url

    def test_no_token_returns_original(self):
        gm = GitManager("https://github.com/owner/repo.git")
        url = gm._inject_token("https://github.com/owner/repo.git")
        assert url == "https://github.com/owner/repo.git"
