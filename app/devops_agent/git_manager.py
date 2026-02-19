from __future__ import annotations

import os
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
        authed = parsed._replace(netloc=f"{self.token}@{parsed.hostname}")
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

    def create_branch(self, repo_path: str, branch_name: str) -> None:
        """Create and checkout a new branch."""
        self._run(["git", "checkout", "-b", branch_name], cwd=repo_path)

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
