"""Unit tests for Layer A hard rules."""

from __future__ import annotations

from x_jev_gate.hard_rules import check_hard_rules


def test_clean_text_passes() -> None:
    text = (
        "16GBノートで Qwen2.5-7B Q4_K_M を Ollama で動かした。"
        "暖機後 18 tok/s。次は同じ条件で cold start を測る。"
    )
    assert check_hard_rules(text) == []


def test_empty_fails() -> None:
    assert "本文が空" in check_hard_rules("")
    assert "本文が空" in check_hard_rules("   \n")


def test_api_key_like() -> None:
    # Must look like a real key: long alphanumeric with at least one digit.
    text = "export KEY=sk-abcdefghijklmnopqrstuvwxyz0123456789"
    failures = check_hard_rules(text)
    assert any("APIキー" in f for f in failures)


def test_github_pat_like() -> None:
    text = "token ghp_abcdefghijklmnopqrstuvwxyz0123456789ABCD"
    failures = check_hard_rules(text)
    assert any("APIキー" in f for f in failures)


def test_password_assignment() -> None:
    text = "password = hunter2secret"
    failures = check_hard_rules(text)
    assert any("認証情報" in f for f in failures)


def test_api_key_assignment() -> None:
    text = "api_key: abcdefghijklmnop"
    failures = check_hard_rules(text)
    assert any("認証情報" in f for f in failures)


def test_users_path() -> None:
    text = "設定は /Users/ayumu/projects/secret/config.yaml にある"
    failures = check_hard_rules(text)
    assert any("ローカル絶対パス" in f for f in failures)


def test_no_employer_keyword_block() -> None:
    """Employer wording is Jev's job, not Layer A."""
    text = "うちの会社のIT部門で16GBノートを支給された話。"
    assert check_hard_rules(text) == []


def test_short_sk_false_positive_avoided() -> None:
    """'sk-img-comparison' style short tokens must not trip the key rule."""
    text = "モデル比較は sk-img-comparison というラベルで整理した。"
    assert check_hard_rules(text) == []
