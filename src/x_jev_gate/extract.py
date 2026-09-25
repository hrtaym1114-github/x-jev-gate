"""Extract draft text from raw input or vault markdown."""

from __future__ import annotations

import re
from pathlib import Path

_POST_SECTION = re.compile(
    r"^##\s+(?:📝\s*)?(投稿文|引用コメント|記事本文)\s*\n(.*?)(?=^##\s|\Z)",
    re.M | re.S,
)
_FENCED = re.compile(r"^```[^\n]*\n(.*?)\n```", re.S)


def extract_text(raw: str, *, format: str = "raw") -> str:
    """Return the draft body.

    format:
      - raw: use the whole string (stripped)
      - vault-md: pull the fenced block under ``## 投稿文`` (or quote/article)
    """
    if format == "raw":
        return raw.strip()
    if format == "vault-md":
        return _extract_vault_md(raw)
    raise ValueError(f"unknown format {format!r}; expected 'raw' or 'vault-md'")


def extract_from_file(path: Path, *, format: str = "raw") -> str:
    return extract_text(path.read_text(encoding="utf-8"), format=format)


def _extract_vault_md(text: str) -> str:
    match = _POST_SECTION.search(text)
    if not match:
        raise ValueError("vault-md: no ## 投稿文 (or 引用コメント/記事本文) section")
    body = match.group(2).strip()
    fenced = _FENCED.match(body)
    if fenced:
        body = fenced.group(1).strip()
    if not body:
        raise ValueError("vault-md: post section is empty")
    return body
