"""Tests for draft extraction."""

from __future__ import annotations

import pytest

from x_jev_gate.extract import extract_text


def test_raw() -> None:
    assert extract_text("  hello\n") == "hello"


def test_vault_md_fenced() -> None:
    md = """# draft
## メタデータ
- **日付**: 2026-09-25
## 投稿文
```
16GBで測った結果を書く。
```
## ネタメモ
ignored
"""
    assert extract_text(md, format="vault-md") == "16GBで測った結果を書く。"


def test_vault_md_missing_section() -> None:
    with pytest.raises(ValueError, match="投稿文"):
        extract_text("# no section\n", format="vault-md")
