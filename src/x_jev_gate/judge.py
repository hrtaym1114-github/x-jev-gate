"""Layer B: System One judgment using cloud TypeSafe or local Ollaya."""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from typesafe_sdk import RetryPolicy, TypeSafeClient, TypeSafeError

REQUEST_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 2


class JudgeUnavailable(Exception):
    """TypeSafe could not answer (missing key or API error). Fail closed by default."""


class SystemOneClient(Protocol):
    def system_one(self, state: Any, questions: Mapping[str, Any]) -> Any: ...


@dataclass(frozen=True)
class JudgeResult:
    nouls: dict[str, float]
    input_tokens: int
    output_tokens: int
    latency_ms: float
    request_id: str | None


def make_client(
    *,
    backend: str = "typesafe",
    model: str | None = None,
    base_url: str | None = None,
    env: Mapping[str, str] | None = None,
) -> TypeSafeClient:
    """Build the SDK client for the selected backend.

    Never reads vault secret files. Never logs the key.
    """
    if backend not in {"typesafe", "ollaya"}:
        raise ValueError(f"unsupported backend: {backend}")
    source = os.environ if env is None else env
    api_key = (source.get("TYPESAFE_API_KEY") or "").strip()
    if model is None:
        model = source.get("TYPESAFE_DEFAULT_MODEL") or None
    if base_url is None:
        base_url = source.get("TYPESAFE_BASE_URL") or None
    if backend == "ollaya":
        api_key = api_key or "local"
        if model is None:
            model = "laya"
        if base_url is None:
            host = source.get("OLLAYA_HOST") or "127.0.0.1:11435"
            base_url = host if "://" in host else f"http://{host}"
    elif not api_key:
        raise JudgeUnavailable(
            "TYPESAFE_API_KEY is not set (export it in the environment; "
            "this tool never reads vault secret files)"
        )
    options: dict[str, Any] = {}
    if model is not None:
        options["model"] = model
    if base_url is not None:
        options["base_url"] = base_url
    return TypeSafeClient(
        api_key=api_key,
        retry=RetryPolicy(max_retries=MAX_RETRIES),
        timeout=REQUEST_TIMEOUT_SECONDS,
        **options,
    )


def run_judgment(
    client: SystemOneClient,
    state: Any,
    questions: Mapping[str, Any],
) -> JudgeResult:
    started = time.perf_counter()
    try:
        response = client.system_one(state, questions)
    except TypeSafeError as exc:
        # Do not include response bodies that might echo secrets.
        raise JudgeUnavailable(
            f"TypeSafe request failed: {type(exc).__name__}"
        ) from exc
    except Exception as exc:  # network / unexpected SDK errors
        raise JudgeUnavailable(
            f"TypeSafe request failed: {type(exc).__name__}"
        ) from exc
    latency_ms = (time.perf_counter() - started) * 1000

    usage = getattr(response, "usage", None)
    return JudgeResult(
        nouls={key: float(answer.noul) for key, answer in response.nouls.items()},
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        latency_ms=latency_ms,
        request_id=getattr(response, "request_id", None),
    )


def offline_fixture_scores(
    question_ids: tuple[str, ...] | list[str],
    *,
    pass_all: bool = True,
) -> dict[str, float]:
    """Synthetic Noul scores for --dry-run-offline (no network)."""
    if pass_all:
        return {qid: 0.85 for qid in question_ids}
    # Fail reader_value and safe_to_publish for a predictable miss.
    scores = {qid: 0.85 for qid in question_ids}
    if "reader_value" in scores:
        scores["reader_value"] = 0.40
    if "safe_to_publish" in scores:
        scores["safe_to_publish"] = 0.40
    return scores
