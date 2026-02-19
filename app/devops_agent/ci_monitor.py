from __future__ import annotations

import asyncio
import time
from typing import Optional, Tuple
from urllib.parse import urlparse

try:
    import aiohttp
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False


class CIMonitor:
    GITHUB_API = "https://api.github.com"

    def __init__(self, repo_url: str, token: Optional[str] = None) -> None:
        self.repo_url = repo_url
        self.token = token

    def extract_owner_repo(self) -> Tuple[str, str]:
        """Parse GitHub URL to extract owner and repo name."""
        parsed = urlparse(self.repo_url)
        parts = parsed.path.strip("/").removesuffix(".git").split("/")
        if len(parts) < 2:
            raise ValueError(f"Cannot parse owner/repo from URL: {self.repo_url}")
        return parts[0], parts[1]

    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_latest_run(self, branch: str, session=None) -> Optional[dict]:
        """Query GitHub Actions API for the latest workflow run on a branch."""
        if not _AIOHTTP_AVAILABLE:
            return None

        owner, repo = self.extract_owner_repo()
        url = f"{self.GITHUB_API}/repos/{owner}/{repo}/actions/runs"
        params = {"branch": branch, "per_page": 1}

        async def _fetch(s):
            async with s.get(url, headers=self._headers(), params=params) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                runs = data.get("workflow_runs", [])
                if not runs:
                    return None
                run = runs[0]
                return {
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "run_id": run.get("id"),
                    "html_url": run.get("html_url"),
                }

        if session is not None:
            return await _fetch(session)

        async with aiohttp.ClientSession() as s:
            return await _fetch(s)

    async def wait_for_completion(self, branch: str, timeout_seconds: int = 300) -> dict:
        """Poll GitHub Actions until the run completes or timeout is reached."""
        if not _AIOHTTP_AVAILABLE:
            return {"status": "timed_out", "conclusion": None, "run_id": None, "html_url": None}

        deadline = time.monotonic() + timeout_seconds
        async with aiohttp.ClientSession() as session:
            while time.monotonic() < deadline:
                run = await self.get_latest_run(branch, session=session)
                if run is None:
                    await asyncio.sleep(10)
                    continue
                if run.get("status") == "completed":
                    return run
                await asyncio.sleep(15)

        return {
            "status": "timed_out",
            "conclusion": None,
            "run_id": None,
            "html_url": None,
        }
