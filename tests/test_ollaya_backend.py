"""Unit tests for Ollaya local backend wiring (no live Ollaya)."""

from __future__ import annotations

from typing import Any

import pytest

from x_jev_gate.cli import main
from x_jev_gate.judge import JudgeUnavailable, make_client


def test_make_client_ollaya_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAYA_HOST", raising=False)
    monkeypatch.delenv("TYPESAFE_DEFAULT_MODEL", raising=False)

    captured: dict[str, Any] = {}

    class FakeTypeSafeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("x_jev_gate.judge.TypeSafeClient", FakeTypeSafeClient)
    make_client(backend="ollaya")
    assert captured["api_key"] == "local"
    assert captured["base_url"] == "http://127.0.0.1:11435"
    assert captured["model"] == "laya"


def test_make_client_ollaya_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "custom-local-key")
    monkeypatch.setenv("TYPESAFE_BASE_URL", "http://10.0.0.2:9999")
    monkeypatch.setenv("TYPESAFE_DEFAULT_MODEL", "other-model")
    monkeypatch.delenv("OLLAYA_HOST", raising=False)

    captured: dict[str, Any] = {}

    class FakeTypeSafeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("x_jev_gate.judge.TypeSafeClient", FakeTypeSafeClient)
    make_client(backend="ollaya")
    assert captured["api_key"] == "custom-local-key"
    assert captured["base_url"] == "http://10.0.0.2:9999"
    assert captured["model"] == "other-model"


def test_make_client_ollaya_host_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_BASE_URL", raising=False)
    monkeypatch.delenv("TYPESAFE_DEFAULT_MODEL", raising=False)
    monkeypatch.setenv("OLLAYA_HOST", "192.168.1.5:11435")

    captured: dict[str, Any] = {}

    class FakeTypeSafeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("x_jev_gate.judge.TypeSafeClient", FakeTypeSafeClient)
    make_client(backend="ollaya")
    assert captured["base_url"] == "http://192.168.1.5:11435"
    assert captured["api_key"] == "local"
    assert captured["model"] == "laya"


def test_make_client_ollaya_host_with_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_BASE_URL", raising=False)
    monkeypatch.setenv("OLLAYA_HOST", "https://ollaya.local:11435")

    captured: dict[str, Any] = {}

    class FakeTypeSafeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("x_jev_gate.judge.TypeSafeClient", FakeTypeSafeClient)
    make_client(backend="ollaya", model="laya")
    assert captured["base_url"] == "https://ollaya.local:11435"


def test_make_client_ollaya_explicit_args_win(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_BASE_URL", "http://env-url:1")
    monkeypatch.setenv("TYPESAFE_DEFAULT_MODEL", "env-model")
    monkeypatch.setenv("TYPESAFE_API_KEY", "env-key")

    captured: dict[str, Any] = {}

    class FakeTypeSafeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("x_jev_gate.judge.TypeSafeClient", FakeTypeSafeClient)
    make_client(
        backend="ollaya",
        model="arg-model",
        base_url="http://arg-url:2",
        env={"TYPESAFE_API_KEY": "env-key"},
    )
    assert captured["model"] == "arg-model"
    assert captured["base_url"] == "http://arg-url:2"
    assert captured["api_key"] == "env-key"


def test_make_client_typesafe_still_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(JudgeUnavailable, match="TYPESAFE_API_KEY"):
        make_client(backend="typesafe")


def test_cli_ollaya_backend_model_in_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "--dry-run-offline",
            "--backend",
            "ollaya",
            "--model",
            "laya",
            "--text",
            "smoke",
            "--json",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert '"backend": "ollaya"' in out
    assert '"model": "laya"' in out
    assert '"status": "pass"' in out
    assert '"offline": true' in out


def test_cli_ollaya_default_model_laya(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "--dry-run-offline",
            "--backend",
            "ollaya",
            "--text",
            "smoke",
            "--json",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert '"backend": "ollaya"' in out
    assert '"model": "laya"' in out


def test_cli_layer_a_includes_backend_model(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "--dry-run-offline",
            "--backend",
            "ollaya",
            "--model",
            "laya",
            "--text",
            "path is /Users/someone/secret/key.txt",
            "--json",
        ]
    )
    assert code == 1
    out = capsys.readouterr().out
    assert '"layer": "A"' in out
    assert '"backend": "ollaya"' in out
    assert '"model": "laya"' in out


def test_cli_ollaya_connection_refused_exit_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(**kwargs: Any) -> None:
        raise JudgeUnavailable("TypeSafe request failed: ConnectError")

    monkeypatch.setattr("x_jev_gate.cli.make_client", boom)
    code = main(
        [
            "--backend",
            "ollaya",
            "--model",
            "laya",
            "--text",
            "普通の投稿です。測定条件は16GBノート。",
        ]
    )
    assert code == 2
