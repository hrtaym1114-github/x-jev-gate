"""Layer B: TypeSafe Jev System One judgment (env key only)."""

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


def make_client(env: Mapping[str, str] | None = None) -> TypeSafeClient:
    """Build a TypeSafe client from TYPESAFE_API_KEY only.

    Never reads vault secret files. Never logs the key.
    """
    source = os.environ if env is None else env
    api_key = (source.get("TYPESAFE_API_KEY") or "").strip()
    if not api_key:
        raise JudgeUnavailable(
            "TYPESAFE_API_KEY is not set (export it in the environment; "
            "this tool never reads vault secret files)"
        )
    return TypeSafeClient(
        api_key=api_key,
        retry=RetryPolicy(max_retries=MAX_RETRIES),
        timeout=REQUEST_TIMEOUT_SECONDS,
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
