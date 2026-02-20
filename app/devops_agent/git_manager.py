from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Optional
from urllib.parse import urlparse


class GitManager:
    def __init__(self, repo_url: str, token: Optional[str] = None) -> None:
        self.repo_url = repo_url
        self.token = token

    def _inject_token(self, url: str) -> str:
        """Inject token into GitHub URL for authentication."""
        if not self.token:
            return url
        parsed = urlparse(url)
        authed = parsed._replace(netloc=f"x-access-token:{self.token}@{parsed.hostname}")
        return authed.geturl()

    def _run(self, cmd: list[str], cwd: Optional[str] = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )

    def clone(self, target_dir: str) -> str:
        """Clone repo to target_dir. Returns path to cloned repo."""
        url = self._inject_token(self.repo_url)
        self._run(["git", "clone", url, target_dir])
        return target_dir

    @staticmethod
    def _sanitize_branch_name(team: str, leader: str) -> str:
        """Sanitize team and leader names to produce a valid Git branch name.

        Converts: "RIFT ORGANISERS" + "Saiyam Kumar"
        To:       "RIFT_ORGANISERS_Saiyam_Kumar_AI_Fix"
        """
        team_clean = re.sub(r"[^A-Za-z0-9_]", "_", team.replace(" ", "_").replace("-", "_"))
        leader_clean = re.sub(r"[^A-Za-z0-9_]", "_", leader.replace(" ", "_").replace("-", "_"))
        # Collapse consecutive underscores
        team_clean = re.sub(r"_+", "_", team_clean).strip("_")
        leader_clean = re.sub(r"_+", "_", leader_clean).strip("_")
        return f"{team_clean}_{leader_clean}_AI_Fix"

    def create_branch(self, repo_path: str, branch_name: str) -> None:
        """Create and checkout a new branch."""
        self._run(["git", "checkout", "-b", branch_name], cwd=repo_path)

    def create_and_checkout_branch(
        self, repo_path: str, team_name: str, leader_name: str
    ) -> str:
        """Sanitize names, create branch, checkout, and return branch name."""
        branch_name = self._sanitize_branch_name(team_name, leader_name)
        self._run(["git", "checkout", "-b", branch_name], cwd=repo_path)
        return branch_name

    def push_branch(self, repo_path: str, branch_name: str) -> None:
        """Push branch to remote origin, using token authentication."""
        if self.token:
            authed_url = self._inject_token(self.repo_url)
            self._run(["git", "remote", "set-url", "origin", authed_url], cwd=repo_path)
        self._run(
            ["git", "push", "--set-upstream", "origin", branch_name],
            cwd=repo_path,
        )

    def commit_and_push(self, repo_path: str, message: str) -> str:
        """Stage all changes, commit, push, and return commit SHA."""
        self._run(["git", "add", "-A"], cwd=repo_path)
        self._run(["git", "commit", "-m", message], cwd=repo_path)
        result = self._run(["git", "rev-parse", "HEAD"], cwd=repo_path)
        sha = result.stdout.strip()
        self._run(["git", "push", "--set-upstream", "origin", "HEAD"], cwd=repo_path)
        return sha

    def cleanup(self, repo_path: str) -> None:
        """Remove the cloned directory."""
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path, ignore_errors=True)
