from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.models.devops_models import BugType


@dataclass
class BugInfo:
    file_path: str
    line_number: Optional[int]
    bug_type: BugType
    error_text: str
    context: str = ""


def _classify_error(error_text: str) -> BugType:
    text_lower = error_text.lower()
    if "indentationerror" in text_lower or "unexpected indent" in text_lower:
        return BugType.INDENTATION
    if "syntaxerror" in text_lower:
        return BugType.SYNTAX
    if "importerror" in text_lower or "modulenotfounderror" in text_lower or "no module named" in text_lower:
        return BugType.IMPORT
    if "typeerror" in text_lower or "attributeerror" in text_lower:
        return BugType.TYPE_ERROR
    if "e1" in text_lower or "w0" in text_lower or "flake8" in text_lower or "pylint" in text_lower:
        return BugType.LINTING
    return BugType.LOGIC


def parse_test_output(output: str) -> List[BugInfo]:
    """Parse pytest/unittest output and return structured BugInfo list."""
    bugs: List[BugInfo] = []

    # Match pytest FAILED lines: FAILED path/to/test.py::TestClass::test_method
    failed_pattern = re.compile(r"FAILED\s+([\w/\\.\-]+\.py)(?:::\S+)?")
    # Match error location lines: path/to/file.py:42: ErrorType
    error_location_pattern = re.compile(r"([\w/\\.\-]+\.py):(\d+):\s*(.*)")
    # Match "E  ErrorText" lines from pytest output
    error_line_pattern = re.compile(r"^\s*E\s+(.+)", re.MULTILINE)

    seen: set[str] = set()

    # Collect error blocks around FAILED markers
    lines = output.splitlines()
    for i, line in enumerate(lines):
        failed_match = failed_pattern.search(line)
        if not failed_match:
            continue

        file_path = failed_match.group(1)
        if file_path in seen:
            continue
        seen.add(file_path)

        # Search surrounding context for error details
        context_start = max(0, i - 20)
        context_end = min(len(lines), i + 5)
        context_block = "\n".join(lines[context_start:context_end])

        line_number: Optional[int] = None
        error_text = ""

        # Try to extract error location and message from context
        for ctx_line in lines[context_start:context_end]:
            loc_match = error_location_pattern.search(ctx_line)
            if loc_match and loc_match.group(1) in (file_path, file_path.replace("\\", "/")):
                try:
                    line_number = int(loc_match.group(2))
                except ValueError:
                    pass
                error_text = loc_match.group(3).strip()
                break

        # Fall back: grab first "E ..." line in context
        if not error_text:
            e_matches = error_line_pattern.findall(context_block)
            if e_matches:
                error_text = e_matches[0].strip()

        if not error_text:
            error_text = line.strip()

        bug_type = _classify_error(context_block)
        bugs.append(BugInfo(
            file_path=file_path,
            line_number=line_number,
            bug_type=bug_type,
            error_text=error_text,
            context=context_block,
        ))

    return bugs
