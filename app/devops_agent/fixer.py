from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Optional

try:
    from openai import AzureOpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

if TYPE_CHECKING:
    from app.devops_agent.analyzer import BugInfo


class FixGenerator:
    def __init__(
        self,
        endpoint: Optional[str],
        api_key: Optional[str],
        deployment: Optional[str],
        api_version: str = "2024-02-15-preview",
    ) -> None:
        self.deployment = deployment
        self._client: Optional[AzureOpenAI] = None

        if _OPENAI_AVAILABLE and endpoint and api_key and deployment:
            self._client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version,
            )

    def generate_fix(self, bug_info: BugInfo, file_content: str) -> Optional[str]:
        """Generate fixed file content using Azure OpenAI. Returns None if not configured."""
        if self._client is None:
            return None

        prompt = (
            f"You are a Python code fixer. Fix the following bug in the file content provided.\n\n"
            f"Bug type: {bug_info.bug_type}\n"
            f"Error: {bug_info.error_text}\n"
            f"File: {bug_info.file_path}\n"
            f"Line number: {bug_info.line_number}\n"
            f"Context:\n{bug_info.context}\n\n"
            f"Current file content:\n```python\n{file_content}\n```\n\n"
            f"Return ONLY the fixed Python file content with no explanation or markdown fences."
        )

        response = self._client.chat.completions.create(
            model=self.deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content

    def apply_fix(self, file_path: str, new_content: str) -> None:
        """Write fixed content to file."""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    def validate_syntax(self, _file_path: str, content: str) -> bool:
        """Check Python syntax using ast.parse."""
        try:
            ast.parse(content)
            return True
        except SyntaxError:
            return False
