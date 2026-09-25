"""Offline / mock client tests for pass/fail thresholds and dry-run path."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from x_jev_gate.cli import main
from x_jev_gate.judge import (
    JudgeUnavailable,
    make_client,
    offline_fixture_scores,
    run_judgment,
)
from x_jev_gate.profiles import evaluate_scores, load_profile


class FakeAnswer:
    def __init__(self, value: float) -> None:
        self.noul = value


class FakeResponse:
    def __init__(self, nouls: Mapping[str, float]) -> None:
        self.nouls = {k: FakeAnswer(v) for k, v in nouls.items()}
        self.usage = SimpleNamespace(input_tokens=10, output_tokens=2)
        self.request_id = "test-req"


class FakeClient:
    def __init__(self, nouls: Mapping[str, float], *, error: Exception | None = None) -> None:
        self._nouls = dict(nouls)
        self._error = error

    def system_one(self, state: Any, questions: Mapping[str, Any]) -> FakeResponse:
        if self._error is not None:
            raise self._error
        # Return only asked question ids.
        return FakeResponse({k: self._nouls.get(k, 0.0) for k in questions})


def test_make_client_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(JudgeUnavailable, match="TYPESAFE_API_KEY"):
        make_client()


def test_make_client_never_reads_files(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key-not-a-real-secret")
    client = make_client()
    assert client is not None


def test_mock_client_pass() -> None:
    profile = load_profile("manufacturing-it")
    scores = {qid: 0.90 for qid in profile.question_ids}
    client = FakeClient(scores)
    result = run_judgment(client, profile.build_state("body"), profile.build_questions())
    assert set(result.nouls) == set(profile.question_ids)
    assert evaluate_scores(result.nouls, profile) == []


def test_mock_client_fail_threshold() -> None:
    profile = load_profile("manufacturing-it")
    scores = {qid: 0.90 for qid in profile.question_ids}
    scores["reader_value"] = 0.20
    scores["safe_to_publish"] = 0.20
    client = FakeClient(scores)
    result = run_judgment(client, profile.build_state("body"), profile.build_questions())
    failures = evaluate_scores(result.nouls, profile)
    assert any("読者価値" in f for f in failures)
    assert any("公開安全性" in f for f in failures)


def test_offline_fixture_pass() -> None:
    profile = load_profile("generic-tech")
    scores = offline_fixture_scores(profile.question_ids, pass_all=True)
    assert evaluate_scores(scores, profile) == []


def test_offline_fixture_fail() -> None:
    profile = load_profile("generic-tech")
    scores = offline_fixture_scores(profile.question_ids, pass_all=False)
    failures = evaluate_scores(scores, profile)
    assert failures


def test_cli_dry_run_offline_pass(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "--dry-run-offline",
            "--text",
            "16GBノートで Qwen を測った。暖機 18 tok/s。次は cold を確認する。",
            "--json",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert '"status": "pass"' in out
    assert '"offline": true' in out


def test_cli_dry_run_offline_fail(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "--dry-run-offline",
            "--offline-fail",
            "--text",
            "何か投稿する。",
        ]
    )
    assert code == 1
    out = capsys.readouterr().out
    assert "BLOCK" in out


def test_cli_hard_rule_skips_jev(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "--dry-run-offline",
            "--text",
            "path is /Users/someone/secret/key.txt",
            "--json",
        ]
    )
    assert code == 1
    out = capsys.readouterr().out
    assert '"layer": "A"' in out
    assert "ローカル絶対パス" in out


def test_cli_shadow_exits_zero_on_fail(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "--dry-run-offline",
            "--offline-fail",
            "--shadow",
            "--text",
            "弱い投稿",
            "--json",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert '"status": "block"' in out
    assert '"shadow": true' in out


def test_cli_missing_key_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    code = main(["--text", "普通の投稿です。測定条件は16GBノート。"])
    assert code == 2


def test_safe_to_publish_in_profile_questions() -> None:
    profile = load_profile("manufacturing-it")
    assert "safe_to_publish" in profile.question_ids
    questions = profile.build_questions()
    assert "safe_to_publish" in questions
    assert len(questions) == 8
