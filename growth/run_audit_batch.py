#!/usr/bin/env python3
"""Run Illusion website audits from the terminal and fill the research CSV.

This intentionally imports the backend audit function directly instead of
clicking through /analyze or hitting the public, rate-limited API.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import website_audits  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run website audits into the research CSV.")
    parser.add_argument(
        "--input",
        default=str(ROOT / "growth" / "ai-search-audit-research-template.csv"),
        help="CSV to read and update in place unless --output is provided.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output CSV. Defaults to updating --input.",
    )
    parser.add_argument(
        "--results-jsonl",
        default=str(ROOT / "growth" / "ai-search-audit-results.jsonl"),
        help="Raw private report backup. Keep this out of published content.",
    )
    parser.add_argument("--start-at", default=None, help="Sample id to start at, e.g. SB-006.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of audits to run.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Rerun rows that already have an overall_score.",
    )
    parser.add_argument(
        "--deterministic-only",
        action="store_true",
        help="Skip Anthropic polish and use deterministic checks only.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=2.0,
        help="Pause between audits so we do not hammer small sites.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the rows that would run without crawling anything.",
    )
    return parser.parse_args()


def severity_counts(findings: list[dict]) -> dict[str, int]:
    counts = {"high": 0, "medium": 0, "low": 0}
    for finding in findings:
        severity = (finding.get("severity") or "").lower()
        if severity in counts:
            counts[severity] += 1
    return counts


def bool_text(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def finding_titles(findings: list[dict]) -> set[str]:
    return {str(finding.get("title") or "").strip().lower() for finding in findings}


def issue_flags(report: dict) -> dict[str, str]:
    """Map raw audit signals into publishable issue columns.

    These flags should stay close to deterministic audit facts. Using broad
    keyword matching across finding fixes can create false positives, e.g. a
    meta-description recommendation saying "how to contact you" is not evidence
    that contact info is missing.
    """

    findings = report.get("findings") or []
    titles = finding_titles(findings)
    signals = report.get("extracted_signals") or {}
    pages = report.get("crawled_pages") or []
    homepage = pages[0] if pages else {}

    blocked_ai_bots = signals.get("blocked_ai_bots") or []
    sitemap_url_count = int(signals.get("sitemap_url_count") or 0)
    image_alt_rate = float(signals.get("image_alt_rate") or 0)
    homepage_h1 = homepage.get("h1") or []
    homepage_meta = str(homepage.get("meta_description") or "").strip()

    return {
        "missing_clear_h1": bool_text(
            "add one plain-language h1" in titles or not homepage_h1
        ),
        "missing_meta_description": bool_text(
            "add a meta description" in titles or not homepage_meta
        ),
        "weak_or_missing_cta": bool_text(not bool(signals.get("has_cta"))),
        "missing_contact_info": bool_text(
            not (bool(signals.get("has_email")) or bool(signals.get("has_phone")))
        ),
        "missing_local_schema": bool_text(not bool(signals.get("local_schema_found"))),
        "missing_service_pages": bool_text(not bool(signals.get("has_service_page"))),
        "weak_location_signals": bool_text(not bool(signals.get("has_location_signal"))),
        "missing_reviews_or_testimonials": bool_text(not bool(signals.get("has_reviews"))),
        "missing_faq": bool_text(not bool(signals.get("has_faq"))),
        "poor_image_alt_coverage": bool_text(image_alt_rate < 0.75),
        "ai_crawler_block_detected": bool_text(bool(blocked_ai_bots)),
        "missing_sitemap": bool_text(sitemap_url_count == 0),
    }


def fill_row(row: dict[str, str], report: dict) -> dict[str, str]:
    findings = report.get("findings") or []
    scores = report.get("scores") or {}
    counts = severity_counts(findings)
    top_titles = [str(f.get("title") or "").strip() for f in findings[:3]]

    row["date_audited"] = row.get("date_audited") or date.today().isoformat()
    row["overall_score"] = str(scores.get("overall") or "")
    row["ux_score"] = str(scores.get("ux") or "")
    row["seo_score"] = str(scores.get("seo") or "")
    row["ai_score"] = str(scores.get("ai") or "")
    row["pages_crawled"] = str(len(report.get("crawled_pages") or []))
    row["high_findings_count"] = str(counts["high"])
    row["medium_findings_count"] = str(counts["medium"])
    row["low_findings_count"] = str(counts["low"])
    row["top_finding_1"] = top_titles[0] if len(top_titles) > 0 else ""
    row["top_finding_2"] = top_titles[1] if len(top_titles) > 1 else ""
    row["top_finding_3"] = top_titles[2] if len(top_titles) > 2 else ""

    for field, value in issue_flags(report).items():
        row[field] = value

    if findings and not row.get("recommended_fix_note"):
        row["recommended_fix_note"] = str(findings[0].get("fix") or "").strip()

    return row


def should_run(row: dict[str, str], start_seen: bool, args: argparse.Namespace) -> bool:
    if not start_seen:
        return False
    if not row.get("url_private_do_not_publish"):
        return False
    if row.get("overall_score") and not args.overwrite:
        return False
    return True


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path
    results_path = Path(args.results_jsonl)

    if args.deterministic_only:
        website_audits.settings.anthropic_api_key = ""

    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    start_seen = args.start_at is None
    ran = 0

    for row in rows:
        if row.get("sample_id") == args.start_at:
            start_seen = True
        if not should_run(row, start_seen, args):
            continue
        if args.limit is not None and ran >= args.limit:
            break

        sample_id = row.get("sample_id") or "(unknown)"
        url = row["url_private_do_not_publish"]
        print(f"[{sample_id}] auditing {url}")

        if args.dry_run:
            ran += 1
            continue

        started_at = datetime.now(timezone.utc).isoformat()
        try:
            report = website_audits.run_website_audit(url)
            row = fill_row(row, report)
            raw_record = {
                "sample_id": sample_id,
                "url_private_do_not_publish": url,
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
                "report": report,
            }
            print(
                f"[{sample_id}] done overall={row['overall_score']} "
                f"ux={row['ux_score']} seo={row['seo_score']} ai={row['ai_score']}"
            )
        except Exception as exc:
            raw_record = {
                "sample_id": sample_id,
                "url_private_do_not_publish": url,
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }
            print(f"[{sample_id}] failed: {raw_record['error']}", file=sys.stderr)

        results_path.parent.mkdir(parents=True, exist_ok=True)
        with results_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(raw_record, ensure_ascii=True) + "\n")

        ran += 1
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    if not args.dry_run:
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print(f"Audits queued/run: {ran}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
