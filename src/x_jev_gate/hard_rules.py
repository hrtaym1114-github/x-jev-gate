"""Layer A: minimal hard fail-closed rules (local, free, no Jev).

Only mechanical leak patterns that must never be judged probabilistically.
Employer / politics / tone checks belong in Jev (Layer B), not here.
"""

from __future__ import annotations

import re

# Patterns inspired by the vault x-post-safety-gate SECRET_PATTERNS, narrowed
# to API-key-like, credential assignments, and /Users/ path leaks only.
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(sk-|xai-|ghp_|gho_|github_pat_)"
            r"(?=[A-Za-z0-9_\-]{20,})(?=[^\s]*\d)[A-Za-z0-9_\-]{20,}"
        ),
        "APIキー様の文字列",
    ),
    (
        re.compile(
            r"(?i)(api[_-]?key|password|passwd|secret|token)\s*[:=]\s*\S{6,}"
        ),
        "認証情報の代入形",
    ),
    (
        re.compile(r"/Users/[a-zA-Z0-9._-]+/"),
        "ローカル絶対パス（ユーザー名が露出する）",
    ),
]


def check_hard_rules(text: str) -> list[str]:
    """Return human-readable failure strings for Layer A hits (empty = clean)."""
    failures: list[str] = []
    if not text or not text.strip():
        failures.append("本文が空")
        return failures
    for pattern, detail in _SECRET_PATTERNS:
        if pattern.search(text):
            failures.append(detail)
    return failures
