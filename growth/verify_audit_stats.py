#!/usr/bin/env python3
"""Verify publishable audit stats against raw private audit reports."""

from __future__ import annotations

import csv
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
GROWTH = ROOT / "growth"
if str(GROWTH) not in sys.path:
    sys.path.insert(0, str(GROWTH))

import run_audit_batch  # noqa: E402


RESEARCH_CSV = GROWTH / "ai-search-audit-research-template.csv"
RAW_JSONL = GROWTH / "ai-search-audit-results.jsonl"
VERIFICATION_CSV = GROWTH / "publishable-stat-verification.csv"

BINARY_STATS = {
    "STAT-006": "missing_faq",
    "STAT-007": "missing_local_schema",
    "STAT-008": "weak_or_missing_cta",
    "STAT-009": "weak_location_signals",
    "STAT-010": "missing_reviews_or_testimonials",
    "STAT-011": "missing_contact_info",
    "STAT-012": "poor_image_alt_coverage",
    "STAT-013": "ai_crawler_block_detected",
    "STAT-014": "missing_sitemap",
    "STAT-016": "missing_service_pages",
    "STAT-017": "missing_meta_description",
    "STAT-018": "missing_clear_h1",
}

SCORE_STATS = {
    "STAT-001": "overall_score",
    "STAT-002": "ux_score",
    "STAT-003": "seo_score",
    "STAT-004": "ai_score",
}


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_raw_reports(path: Path) -> dict[str, dict]:
    reports: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("status") == "completed":
            reports[str(record["sample_id"])] = record["report"]
    return reports


def score_bucket(score: int) -> str:
    if score < 50:
        return "0-49"
    if score < 70:
        return "50-69"
    if score < 85:
        return "70-84"
    return "85+"


def verify_rows(rows: list[dict[str, str]], raw_reports: dict[str, dict]) -> None:
    mismatches: list[str] = []

    for row in rows:
        sample_id = row["sample_id"]
        report = raw_reports.get(sample_id)
        if not report:
            mismatches.append(f"{sample_id}: missing raw completed report")
            continue

        scores = report.get("scores") or {}
        for score_key in ("overall", "ux", "seo", "ai"):
            csv_key = f"{score_key}_score"
            if row.get(csv_key) != str(scores.get(score_key) or ""):
                mismatches.append(f"{sample_id}: {csv_key} mismatch")

        expected_flags = run_audit_batch.issue_flags(report)
        for field, expected in expected_flags.items():
            if row.get(field) != expected:
                mismatches.append(f"{sample_id}: {field} expected {expected}, got {row.get(field)}")

        row["spot_check_status"] = row.get("spot_check_status") or "raw_report_verified"
        row["spot_check_notes"] = row.get("spot_check_notes") or (
            "Scores and issue flags reconciled against the private raw audit report. "
            "Mobile/performance was not measured."
        )
        row["include_in_publishable_stats"] = "TRUE"

    if mismatches:
        raise SystemExit("Verification failed:\n" + "\n".join(mismatches))


def update_verification_log(rows: list[dict[str, str]]) -> None:
    verification_rows, verification_fields = read_csv(VERIFICATION_CSV)
    by_stat = {row["stat_id"]: row for row in verification_rows}
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sample_ids = [row["sample_id"] for row in rows]
    all_samples = ",".join(sample_ids)

    for stat_id, column in SCORE_STATS.items():
        values = [int(row[column]) for row in rows if row.get(column)]
        if len(values) != len(rows):
            raise SystemExit(f"{stat_id}: expected {len(rows)} score values, got {len(values)}")
        stat = by_stat[stat_id]
        stat["numerator"] = f"avg={sum(values) / len(values):.1f}; median={statistics.median(values):.0f}"
        stat["denominator"] = str(len(values))
        stat["sample_ids_counted"] = all_samples
        stat["sample_ids_spot_checked"] = all_samples
        stat["checked_by"] = "Codex"
        stat["checked_at"] = checked_at
        stat["status"] = "verified"
        stat["notes"] = "All rows had nonblank scores and matched the raw completed audit reports."

    buckets = {"0-49": [], "50-69": [], "70-84": [], "85+": []}
    for row in rows:
        buckets[score_bucket(int(row["overall_score"]))].append(row["sample_id"])
    stat = by_stat["STAT-005"]
    stat["numerator"] = "; ".join(f"{bucket}={len(ids)}" for bucket, ids in buckets.items())
    stat["denominator"] = str(len(rows))
    stat["sample_ids_counted"] = all_samples
    stat["sample_ids_spot_checked"] = all_samples
    stat["checked_by"] = "Codex"
    stat["checked_at"] = checked_at
    stat["status"] = "verified"
    stat["notes"] = "; ".join(f"{bucket}: {','.join(ids)}" for bucket, ids in buckets.items())

    for stat_id, column in BINARY_STATS.items():
        counted = [row["sample_id"] for row in rows if row.get(column) == "TRUE"]
        stat = by_stat[stat_id]
        stat["numerator"] = str(len(counted))
        stat["denominator"] = str(len(rows))
        stat["sample_ids_counted"] = ",".join(counted)
        stat["sample_ids_spot_checked"] = ",".join(counted)
        stat["checked_by"] = "Codex"
        stat["checked_at"] = checked_at
        stat["status"] = "verified"
        stat["notes"] = (
            "Every TRUE row was reconciled against deterministic fields in the raw audit report. "
            "Phrase as 'Illusion detected' and 'in this sample.'"
        )

    stat = by_stat["STAT-015"]
    stat["numerator"] = "not measured"
    stat["denominator"] = str(len(rows))
    stat["sample_ids_counted"] = ""
    stat["sample_ids_spot_checked"] = ""
    stat["checked_by"] = "Codex"
    stat["checked_at"] = checked_at
    stat["status"] = "deferred_not_measured"
    stat["notes"] = (
        "Do not publish a mobile/performance statistic from this dataset. "
        "The current analyzer does not run Lighthouse, Core Web Vitals, or visual mobile QA."
    )

    write_csv(VERIFICATION_CSV, verification_rows, verification_fields)


def print_summary(rows: list[dict[str, str]]) -> None:
    score_columns = ("overall_score", "ux_score", "seo_score", "ai_score")
    for column in score_columns:
        values = [int(row[column]) for row in rows]
        print(f"{column}: avg={sum(values) / len(values):.1f}, median={statistics.median(values):.0f}")

    buckets = {"0-49": 0, "50-69": 0, "70-84": 0, "85+": 0}
    for row in rows:
        buckets[score_bucket(int(row["overall_score"]))] += 1
    print("overall_score buckets:", buckets)

    for stat_id, column in BINARY_STATS.items():
        count = sum(1 for row in rows if row.get(column) == "TRUE")
        print(f"{stat_id} {column}: {count}/{len(rows)} ({count / len(rows):.0%})")


def main() -> int:
    rows, research_fields = read_csv(RESEARCH_CSV)
    raw_reports = read_raw_reports(RAW_JSONL)

    if len(rows) != 25:
        raise SystemExit(f"Expected 25 research rows, found {len(rows)}")
    if len(raw_reports) != 25:
        raise SystemExit(f"Expected 25 raw reports, found {len(raw_reports)}")

    verify_rows(rows, raw_reports)
    write_csv(RESEARCH_CSV, rows, research_fields)
    update_verification_log(rows)
    print_summary(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
