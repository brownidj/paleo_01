#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

BLOCKED_TRACKED_PATHS = (
    re.compile(r"^\.env(?:\..+)?$"),
    re.compile(r"^config/env/.+\.env$"),
    re.compile(r"^secrets/.+\.txt$"),
)

ALLOWED_PLACEHOLDER_MARKERS = (
    "replace-with",
    "change-me",
    "example",
    "<",
    "${",
)

SENSITIVE_ASSIGNMENT_PATTERNS = (
    re.compile(r"^\s*(POSTGRES_PASSWORD|JWT_SECRET|JWT_REFRESH_SECRET|BOOTSTRAP_ADMIN_PASSWORD)\s*=\s*(.+?)\s*$"),
    re.compile(r'^\s*(database_url|jwt_secret|jwt_refresh_secret|bootstrap_admin_password)\s*:\s*str\s*=\s*"(.+?)"\s*$'),
)

JWT_LIKE_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")


def _tracked_files() -> list[str]:
    output = subprocess.check_output(["git", "ls-files"], cwd=REPO_ROOT, text=True)
    return [line.strip() for line in output.splitlines() if line.strip()]


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.strip().strip("\"'").lower()
    return any(marker in normalized for marker in ALLOWED_PLACEHOLDER_MARKERS)


def _is_blocked_tracked_path(path: str) -> bool:
    if path.endswith(".env.example"):
        return False
    return any(pattern.match(path) for pattern in BLOCKED_TRACKED_PATHS)


def _scan_file(path: str) -> list[str]:
    findings: list[str] = []
    full_path = REPO_ROOT / path
    try:
        content = full_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings

    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        for pattern in SENSITIVE_ASSIGNMENT_PATTERNS:
            match = pattern.match(line)
            if not match:
                continue
            value = match.group(2).strip()
            if not value or _looks_like_placeholder(value):
                continue
            findings.append(f"{path}:{idx} hardcoded secret-like assignment detected.")

        if JWT_LIKE_PATTERN.search(line):
            findings.append(f"{path}:{idx} JWT-like token literal detected.")

    return findings


def main() -> int:
    findings: list[str] = []
    for path in _tracked_files():
        if _is_blocked_tracked_path(path):
            findings.append(f"{path} is tracked but must be local-only/ignored.")
        findings.extend(_scan_file(path))

    if findings:
        print("Tracked secret policy violations detected:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print("Tracked secret policy checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
