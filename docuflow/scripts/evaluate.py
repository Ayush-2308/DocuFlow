"""Run sample documents through run_pipeline and write real metrics.

From docuflow/:  python scripts/evaluate.py

Does not invent numbers. Writes docs/EVALUATION.md from this run only.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.extraction_agent import GEMINI_MODEL  # noqa: E402
from config import settings  # noqa: E402
from graph import run_pipeline  # noqa: E402

SAMPLES = ROOT / "samples"
TRUTH_PATH = SAMPLES / "ground_truth.json"
OUT_PATH = REPO / "docs" / "EVALUATION.md"


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def field_matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        got = _as_number(actual)
        return got is not None and abs(got - float(expected)) <= 0.05
    expected_text = str(expected).strip().lower()
    actual_text = str(actual or "").strip().lower()
    return expected_text == actual_text


def percent(part: int, whole: int) -> str:
    if whole <= 0:
        return "n/a"
    return f"{(part / whole) * 100:.1f}%"


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return ordered[index]


def main() -> None:
    truth = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
    docs = truth["documents"]
    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    outcome_ok = 0
    fields_ok = 0
    fields_total = 0

    for item in docs:
        path = SAMPLES / item["file"]
        started = time.perf_counter()
        error = ""
        status = "error"
        extracted: dict[str, Any] = {}
        try:
            state = run_pipeline(str(path), item["doc_type"])
            status = state.status
            extracted = state.extracted_data or {}
        except Exception as exc:
            error = str(exc)
        latency = time.perf_counter() - started
        latencies.append(latency)

        expected_fields: dict[str, Any] = item.get("expected_fields") or {}
        matched = 0
        for key, expected in expected_fields.items():
            fields_total += 1
            if field_matches(expected, extracted.get(key)):
                matched += 1
                fields_ok += 1
        outcome_match = status == item["expected_outcome"]
        if outcome_match:
            outcome_ok += 1
        rows.append(
            {
                "file": item["file"],
                "doc_type": item["doc_type"],
                "expected": item["expected_outcome"],
                "actual": status,
                "outcome_ok": outcome_match,
                "fields": f"{matched}/{len(expected_fields)}",
                "latency_s": latency,
                "error": error,
            }
        )

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    avg = statistics.mean(latencies) if latencies else 0.0
    lines = [
        "# DocuFlow evaluation",
        "",
        f"Generated: {generated}",
        f"LLM provider: `{settings.llm_provider}`",
        f"Gemini model constant: `{GEMINI_MODEL}`",
        f"Sample count: {len(docs)}",
        "",
        "## Per document",
        "",
        "| File | Type | Expected | Actual | Outcome match | Fields | Latency (s) | Error |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        err = (row["error"] or "").replace("|", "\\|")[:80]
        lines.append(
            f"| `{row['file']}` | {row['doc_type']} | {row['expected']} | "
            f"{row['actual']} | {row['outcome_ok']} | {row['fields']} | "
            f"{row['latency_s']:.2f} | {err} |"
        )
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Outcome accuracy: {outcome_ok}/{len(docs)} ({percent(outcome_ok, len(docs))})",
            f"- Field accuracy: {fields_ok}/{fields_total} ({percent(fields_ok, fields_total)})",
            f"- Average latency: {avg:.2f}s",
            f"- p95 latency: {p95(latencies):.2f}s",
            "",
            "These numbers come from this script run only. They are not estimates.",
            "",
        ]
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
