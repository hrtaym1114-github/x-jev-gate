"""x-jev-gate CLI — TypeSafe Jev gate for X drafts.

Exit codes (SPEC):
  0  pass (or --shadow)
  1  hard block or Jev threshold miss
  2  JudgeUnavailable (missing key / API error); fail closed by default
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, TextIO

from x_jev_gate.extract import extract_from_file, extract_text
from x_jev_gate.hard_rules import check_hard_rules
from x_jev_gate.judge import (
    JudgeUnavailable,
    make_client,
    offline_fixture_scores,
    run_judgment,
)
from x_jev_gate.profiles import (
    QUESTION_LABELS,
    apply_threshold_file,
    evaluate_scores,
    list_profiles,
    load_profile,
)


def _read_input(args: argparse.Namespace) -> str:
    sources = sum(
        [
            bool(args.file),
            args.text is not None,
            bool(args.stdin),
        ]
    )
    if sources != 1:
        raise SystemExit("provide exactly one of FILE, --text, or --stdin")

    fmt = args.format
    if args.text is not None:
        return extract_text(args.text, format=fmt)
    if args.stdin:
        return extract_text(sys.stdin.read(), format=fmt)
    assert args.file is not None
    return extract_from_file(Path(args.file), format=fmt)


def _human_summary(result: Mapping[str, Any]) -> str:
    status = str(result.get("status", "block")).upper()
    scores = result.get("scores") or {}
    parts = []
    for key, value in scores.items():
        label = QUESTION_LABELS.get(key, key)
        parts.append(f"{label} {float(value):.2f}")
    score_line = " / ".join(parts) if parts else "(no scores)"
    lines = [f"{status} | {score_line}"]
    failures = result.get("failures") or []
    if failures:
        lines.append("failures:")
        for item in failures:
            lines.append(f"  - {item}")
    layer = result.get("layer")
    if layer:
        lines.append(f"layer: {layer}")
    if result.get("shadow"):
        lines.append("shadow: exit forced to 0")
    if result.get("offline"):
        lines.append("mode: dry-run-offline")
    return "\n".join(lines)


def _emit(result: dict[str, Any], *, as_json: bool, stream: TextIO | None = None) -> None:
    out = sys.stdout if stream is None else stream
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2), file=out)
    else:
        print(_human_summary(result), file=out)


def run_gate(args: argparse.Namespace) -> int:
    try:
        body = _read_input(args)
    except (OSError, ValueError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 1

    profile = load_profile(args.profile)
    if args.threshold_file:
        try:
            profile = apply_threshold_file(profile, Path(args.threshold_file))
        except (OSError, ValueError) as exc:
            print(f"threshold-file error: {exc}", file=sys.stderr)
            return 1

    # Layer A — hard rules (never call Jev on hit)
    hard = check_hard_rules(body)
    if hard:
        result = {
            "status": "block",
            "layer": "A",
            "profile": profile.name,
            "scores": {},
            "failures": hard,
            "shadow": bool(args.shadow),
            "offline": False,
        }
        _emit(result, as_json=args.json)
        return 0 if args.shadow else 1

    # Layer B — Jev or offline fixture
    scores: dict[str, float]
    meta: dict[str, Any] = {}
    offline = bool(args.dry_run_offline)

    if offline:
        # Default fixture passes; --offline-fail forces a threshold miss for tests.
        scores = offline_fixture_scores(
            profile.question_ids,
            pass_all=not getattr(args, "offline_fail", False),
        )
        meta = {"request_id": "dry-run-offline", "latency_ms": 0.0}
    else:
        try:
            client = make_client()
            judgment = run_judgment(
                client,
                profile.build_state(body),
                profile.build_questions(),
            )
        except JudgeUnavailable as exc:
            print(f"JEV unavailable: {exc}", file=sys.stderr)
            if args.allow_offline_soft:
                soft = {
                    "status": "unavailable",
                    "layer": "B",
                    "profile": profile.name,
                    "scores": {},
                    "failures": [str(exc)],
                    "shadow": bool(args.shadow),
                    "offline": False,
                }
                _emit(soft, as_json=args.json)
                return 0
            return 2
        scores = {
            key: round(float(judgment.nouls.get(key, 0.0)), 3)
            for key in profile.question_ids
        }
        # Include any extra keys the API returned.
        for key, value in judgment.nouls.items():
            scores.setdefault(key, round(float(value), 3))
        meta = {
            "request_id": judgment.request_id,
            "latency_ms": round(judgment.latency_ms, 1),
            "input_tokens": judgment.input_tokens,
            "output_tokens": judgment.output_tokens,
        }

    failures = evaluate_scores(scores, profile, strict=args.strict)
    passed = not failures
    result = {
        "status": "pass" if passed else "block",
        "layer": "B",
        "profile": profile.name,
        "scores": scores,
        "failures": failures,
        "shadow": bool(args.shadow),
        "offline": offline,
        **meta,
    }
    _emit(result, as_json=args.json)

    if args.shadow:
        return 0
    return 0 if passed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="x-jev-gate",
        description=(
            "TypeSafe Jev (System One) gate for X drafts. "
            "Layer A hard-blocks secrets locally; Layer B scores Noul questions."
        ),
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="path to draft text (or vault markdown with --format vault-md)",
    )
    parser.add_argument("--text", help="draft text as a CLI argument")
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="read draft text from stdin",
    )
    parser.add_argument(
        "--format",
        choices=("raw", "vault-md"),
        default="raw",
        help="input format (default: raw)",
    )
    parser.add_argument(
        "--profile",
        default="manufacturing-it",
        choices=list_profiles(),
        help="persona + question set (default: manufacturing-it)",
    )
    parser.add_argument(
        "--threshold-file",
        help="YAML file overriding question thresholds",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=True,
        help="require every question to meet its threshold (default; OR mode not offered)",
    )
    parser.add_argument(
        "--shadow",
        action="store_true",
        help="print scores but always exit 0 (measurement period)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON",
    )
    parser.add_argument(
        "--dry-run-offline",
        action="store_true",
        help="no network; use synthetic fixture scores (CI smoke)",
    )
    parser.add_argument(
        "--offline-fail",
        action="store_true",
        help=argparse.SUPPRESS,  # test helper: fixture scores that miss thresholds
    )
    parser.add_argument(
        "--allow-offline-soft",
        action="store_true",
        help="on JudgeUnavailable, warn and exit 0 instead of fail-closed exit 2",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_gate(args)


if __name__ == "__main__":
    raise SystemExit(main())
