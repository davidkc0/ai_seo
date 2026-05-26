#!/usr/bin/env python3
"""Generate branded outreach PDFs from saved Illusion website audits."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import urlparse


sys.dont_write_bytecode = True

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        Image,
        KeepTogether,
        PageBreak,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError as exc:  # pragma: no cover
    raise SystemExit("reportlab is required to generate PDFs") from exc


ROOT = Path(__file__).resolve().parents[1]
GROWTH = ROOT / "growth"
RAW_JSONL = GROWTH / "ai-search-audit-results.jsonl"
RESEARCH_CSV = GROWTH / "ai-search-audit-research-template.csv"
DEFAULT_OUTPUT_DIR = GROWTH / "outreach-reports"
LOGO_PATH = ROOT / "frontend" / "public" / "illusion_logo.png"

BG = colors.HexColor("#050505")
SURFACE = colors.HexColor("#111111")
SURFACE_2 = colors.HexColor("#181818")
BORDER = colors.HexColor("#2a2a2a")
TEXT = colors.HexColor("#f5f5f5")
MUTED = colors.HexColor("#a1a1aa")
DIM = colors.HexColor("#6b7280")
PRIMARY = colors.HexColor("#10b981")
PRIMARY_LIGHT = colors.HexColor("#34d399")
WARNING = colors.HexColor("#f59e0b")
DANGER = colors.HexColor("#ef4444")
WHITE = colors.white


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate branded outreach audit reports.")
    parser.add_argument("--raw-jsonl", default=str(RAW_JSONL))
    parser.add_argument("--research-csv", default=str(RESEARCH_CSV))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--sample-id", default=None, help="Generate one report, e.g. SB-001.")
    parser.add_argument(
        "--mailing-address",
        default="TODO: add physical mailing address or registered mailbox before sending",
        help="Physical mailing address or registered mailbox to include in outreach emails.",
    )
    return parser.parse_args()


def ascii_text(value: object) -> str:
    text = "" if value is None else str(value)
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_only).strip()


def paragraph(text: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(ascii_text(text)), style)


def link_text(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    return domain.replace("www.", "")


def slugify(value: str) -> str:
    value = ascii_text(value).lower()
    value = re.sub(r"https?://", "", value)
    value = value.replace("www.", "")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "website"


def score_color(score: int) -> colors.Color:
    if score >= 85:
        return PRIMARY_LIGHT
    if score >= 70:
        return WARNING
    return DANGER


def severity_color(severity: str) -> colors.Color:
    severity = severity.lower()
    if severity == "high":
        return DANGER
    if severity == "medium":
        return WARNING
    return PRIMARY_LIGHT


def read_research_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return {row["sample_id"]: row for row in csv.DictReader(f)}


def read_raw_records(path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("status") == "completed":
            records[str(record["sample_id"])] = record
    return records


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "kicker": ParagraphStyle(
            "Kicker",
            parent=base["Normal"],
            fontName="Courier-Bold",
            fontSize=8.5,
            leading=11,
            textColor=PRIMARY_LIGHT,
            spaceAfter=8,
            alignment=TA_LEFT,
        ),
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=31,
            leading=34,
            textColor=TEXT,
            spaceAfter=10,
            alignment=TA_LEFT,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=TEXT,
            spaceBefore=8,
            spaceAfter=8,
        ),
        "h3": ParagraphStyle(
            "H3",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=TEXT,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.4,
            leading=13.5,
            textColor=MUTED,
            spaceAfter=6,
        ),
        "body_strong": ParagraphStyle(
            "BodyStrong",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=13.5,
            textColor=TEXT,
            spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Courier",
            fontSize=7.6,
            leading=10,
            textColor=DIM,
            spaceAfter=4,
        ),
        "metric": ParagraphStyle(
            "Metric",
            parent=base["BodyText"],
            fontName="Courier-Bold",
            fontSize=21,
            leading=23,
            textColor=TEXT,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=base["BodyText"],
            fontName="Courier",
            fontSize=7.3,
            leading=9,
            textColor=DIM,
            alignment=TA_CENTER,
        ),
        "right_small": ParagraphStyle(
            "RightSmall",
            parent=base["BodyText"],
            fontName="Courier",
            fontSize=7.5,
            leading=9,
            textColor=DIM,
            alignment=TA_RIGHT,
        ),
        "pill": ParagraphStyle(
            "Pill",
            parent=base["BodyText"],
            fontName="Courier-Bold",
            fontSize=7.5,
            leading=9,
            textColor=TEXT,
        ),
    }


class IllusionDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, logo_path: Path):
        self.logo_path = logo_path
        super().__init__(
            filename,
            pagesize=LETTER,
            leftMargin=0.54 * inch,
            rightMargin=0.54 * inch,
            topMargin=0.76 * inch,
            bottomMargin=0.62 * inch,
        )
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="normal",
            showBoundary=0,
        )
        self.addPageTemplates([PageTemplate(id="illusion", frames=[frame], onPage=self.draw_page)])

    def draw_page(self, canvas, doc):
        width, height = LETTER
        canvas.saveState()
        canvas.setFillColor(BG)
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#061711"))
        canvas.circle(width * 0.78, height * 0.98, 190, fill=1, stroke=0)
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(0.54 * inch, height - 0.58 * inch, width - 0.54 * inch, height - 0.58 * inch)
        if self.logo_path.exists():
            canvas.drawImage(
                str(self.logo_path),
                0.54 * inch,
                height - 0.47 * inch,
                width=1.18 * inch,
                height=0.35 * inch,
                mask="auto",
                preserveAspectRatio=True,
            )
        canvas.setFont("Courier", 7.5)
        canvas.setFillColor(DIM)
        canvas.drawRightString(width - 0.54 * inch, height - 0.31 * inch, "AI Website Audit")
        canvas.line(0.54 * inch, 0.42 * inch, width - 0.54 * inch, 0.42 * inch)
        canvas.drawString(0.54 * inch, 0.24 * inch, "illusion.ai/analyze")
        canvas.drawRightString(width - 0.54 * inch, 0.24 * inch, f"Page {doc.page}")
        canvas.restoreState()


def section_card(items: list, width: float, padding: int = 12) -> Table:
    table = Table([[items]], colWidths=[width])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), padding),
                ("RIGHTPADDING", (0, 0), (-1, -1), padding),
                ("TOPPADDING", (0, 0), (-1, -1), padding),
                ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
            ]
        )
    )
    return table


def score_table(scores: dict, styles: dict[str, ParagraphStyle], width: float) -> Table:
    labels = [
        ("Overall", "overall"),
        ("User Experience", "ux"),
        ("SEO / Local", "seo"),
        ("AI Search", "ai"),
    ]
    cells = []
    for label, key in labels:
        score = int(scores.get(key) or 0)
        metric_style = ParagraphStyle(
            f"Metric{key}",
            parent=styles["metric"],
            textColor=score_color(score),
        )
        cells.append([Paragraph(str(score), metric_style), Paragraph(label, styles["metric_label"])])
    table = Table([cells], colWidths=[width / 4] * 4)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def finding_card(finding: dict, styles: dict[str, ParagraphStyle], width: float, number: int) -> Table:
    severity = ascii_text(finding.get("severity", "medium")).upper()
    category = ascii_text(finding.get("category", "website")).replace("_", " ").upper()
    severity_style = ParagraphStyle(
        f"Severity{number}",
        parent=styles["pill"],
        textColor=severity_color(severity.lower()),
    )

    content = [
        Paragraph(f"{number}. {escape(ascii_text(finding.get('title', 'Website finding')))}", styles["h3"]),
        Paragraph(f"{severity} / {category}", severity_style),
        paragraph(f"Evidence: {finding.get('evidence', '')}", styles["body"]),
        paragraph(f"Fix: {finding.get('fix', '')}", styles["body_strong"]),
        paragraph(f"Expected impact: {finding.get('expected_impact', '')}", styles["body"]),
        paragraph(f"Effort: {finding.get('effort', 'medium')}", styles["small"]),
    ]
    table = section_card(content, width, padding=10)
    table.setStyle(
        TableStyle(
            [
                ("LINEBEFORE", (0, 0), (0, 0), 3, severity_color(severity.lower())),
            ]
        )
    )
    return table


def signal_rows(report: dict) -> list[tuple[str, str]]:
    signals = report.get("extracted_signals") or {}
    blocked = signals.get("blocked_ai_bots") or []
    data = [
        ("Crawlable email or phone", bool(signals.get("has_email")) or bool(signals.get("has_phone"))),
        ("Visible call to action", bool(signals.get("has_cta"))),
        ("Reviews or testimonials", bool(signals.get("has_reviews"))),
        ("FAQ / answer content", bool(signals.get("has_faq"))),
        ("Dedicated service pages", bool(signals.get("has_service_page"))),
        ("Location or audience signal", bool(signals.get("has_location_signal"))),
        ("Useful local/business schema", bool(signals.get("local_schema_found"))),
        ("Sitemap discovered", int(signals.get("sitemap_url_count") or 0) > 0),
        ("AI crawler blocks detected", bool(blocked)),
    ]
    rows = []
    for label, ok in data:
        if label == "AI crawler blocks detected":
            rows.append((label, "Found" if ok else "None detected"))
        else:
            rows.append((label, "Present" if ok else "Needs work"))
    return rows


def signals_table(report: dict, styles: dict[str, ParagraphStyle], width: float) -> Table:
    rows = [[paragraph("Signal", styles["small"]), paragraph("Status", styles["small"])]]
    for label, status in signal_rows(report):
        status_color = PRIMARY_LIGHT if status in ("Present", "None detected") else WARNING
        rows.append(
            [
                paragraph(label, styles["body"]),
                Paragraph(
                    escape(status),
                    ParagraphStyle("SignalStatus", parent=styles["body_strong"], textColor=status_color),
                ),
            ]
        )
    table = Table(rows, colWidths=[width * 0.66, width * 0.34])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BACKGROUND", (0, 0), (-1, 0), SURFACE_2),
                ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def crawled_pages_table(report: dict, styles: dict[str, ParagraphStyle], width: float) -> Table:
    rows = [[paragraph("Page", styles["small"]), paragraph("Signals", styles["small"])]]
    for page in (report.get("crawled_pages") or [])[:6]:
        title = ascii_text(page.get("title") or "(No title)")
        url = ascii_text(page.get("url") or "")
        page_summary = f"{title}<br/><font color='#6b7280'>{url}</font>"
        signals = (
            f"status {page.get('status_code')} / "
            f"{page.get('word_count', 0)} words / "
            f"{len(page.get('h1') or [])} H1 / "
            f"{len(page.get('schema_types') or [])} schema"
        )
        rows.append([Paragraph(page_summary, styles["body"]), paragraph(signals, styles["small"])])
    table = Table(rows, colWidths=[width * 0.7, width * 0.3])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BACKGROUND", (0, 0), (-1, 0), SURFACE_2),
                ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def top_fix_sentence(findings: list[dict]) -> str:
    titles = [ascii_text(finding.get("title")) for finding in findings[:3]]
    titles = [title for title in titles if title]
    if not titles:
        return "The audit did not find major obvious issues."
    if len(titles) == 1:
        return titles[0]
    return ", ".join(titles[:-1]) + f", and {titles[-1]}"


def personalized_actions(findings: list[dict], limit: int = 4) -> list[str]:
    actions = []
    for finding in findings[:limit]:
        title = ascii_text(finding.get("title"))
        fix = ascii_text(finding.get("fix"))
        evidence = ascii_text(finding.get("evidence"))
        if title and fix:
            action = f"{title}: {fix}"
            if evidence:
                action += f" Audit evidence: {evidence}"
            actions.append(action)
    return actions


def sentence_fragment(value: object) -> str:
    return ascii_text(value).rstrip(".;:")


def email_action_items(findings: list[dict], limit: int = 4) -> list[str]:
    items = []
    for finding in findings[:limit]:
        title = sentence_fragment(finding.get("title"))
        evidence = sentence_fragment(finding.get("evidence"))
        fix = sentence_fragment(finding.get("fix"))
        if not title:
            continue

        parts = [title]
        if evidence:
            parts.append(f"Found: {evidence}")
        if fix:
            parts.append(f"Suggested direction: {fix}")
        items.append(". ".join(parts))
    return items


def illusion_value_note() -> str:
    return (
        "Illusion helps small businesses answer a simple question: when potential customers "
        "ask Google or AI tools for recommendations, does your business show up - or do your "
        "competitors? The first step is making sure your website clearly explains what you do, "
        "who you help, why someone should trust you, and how to contact you."
    )


def why_it_matters_note() -> str:
    return (
        "Customers are starting to search differently. Instead of only typing keywords into "
        "Google, many now ask AI tools direct questions like 'who should I hire?' or 'what "
        "company can help me with this?' To show up in those answers, your website needs to "
        "make your business easy to understand: clear services, location or audience signals, "
        "trust proof, structured content, and obvious next steps."
    )


def email_why_it_matters(domain: str) -> str:
    return (
        "The reason this matters is simple: more customers are starting their search by asking "
        "questions like 'who is a good provider near me?' or 'what company should I hire for "
        "this?' Google and AI tools need clear signals from your website before they can "
        "confidently understand, summarize, or recommend your business."
    )


def email_issue_impact_note() -> str:
    return (
        "These are not cosmetic SEO issues. They affect whether search engines and AI tools "
        "can clearly tell what your business does, who it helps, whether it looks trustworthy, "
        "and what a potential customer should do next."
    )


def generate_pdf(record: dict, research_row: dict[str, str], output_path: Path) -> None:
    report = record["report"]
    styles = make_styles()
    doc = IllusionDocTemplate(str(output_path), LOGO_PATH)
    width = doc.width
    story = []

    url = report.get("normalized_url") or record.get("url_private_do_not_publish") or ""
    domain = link_text(url)
    scores = report.get("scores") or {}
    findings = report.get("findings") or []
    report_date = ascii_text(record.get("completed_at") or date.today().isoformat())[:10]

    story.append(paragraph("AI WEBSITE AUDIT / SMALL BUSINESS READINESS", styles["kicker"]))
    story.append(paragraph("Your AI search readiness report", styles["title"]))
    story.append(paragraph(domain, styles["body_strong"]))
    story.append(paragraph(f"Prepared by Illusion on {report_date}", styles["small"]))
    story.append(Spacer(1, 12))
    story.append(score_table(scores, styles, width))
    story.append(Spacer(1, 13))
    story.append(
        section_card(
            [
                paragraph("Executive summary", styles["h2"]),
                paragraph(report.get("executive_summary", ""), styles["body"]),
                paragraph(
                    "The fastest wins are usually clarity, trust, crawlability, structured data, and answer-style content - not expensive enterprise theater.",
                    styles["body"],
                ),
            ],
            width,
        )
    )
    story.append(Spacer(1, 12))
    story.append(
        section_card(
            [
                paragraph("Why this audit matters", styles["h2"]),
                paragraph(why_it_matters_note(), styles["body"]),
                paragraph(
                    "This audit checks whether your site gives Google and AI tools enough information to confidently understand and recommend your business.",
                    styles["body_strong"],
                ),
            ],
            width,
        )
    )
    story.append(Spacer(1, 12))

    priority_items = []
    for idx, finding in enumerate(findings[:3], start=1):
        priority_items.append(
            paragraph(
                f"{idx}. {finding.get('title', '')}: {finding.get('fix', '')}",
                styles["body"],
            )
        )
    story.append(section_card([paragraph("Top fixes to prioritize", styles["h2"]), *priority_items], width))
    story.append(Spacer(1, 12))

    story.append(
        section_card(
            [
                paragraph("What Illusion checks", styles["h2"]),
                paragraph(
                    "Service clarity, location or audience clarity, trust signals, crawlability, structured data, FAQ answerability, CTA clarity, content depth, and AI crawler access. This PDF does not include Lighthouse or Core Web Vitals testing.",
                    styles["body"],
                ),
            ],
            width,
        )
    )
    story.append(Spacer(1, 12))
    story.append(
        section_card(
            [
                paragraph("How Illusion helps after the audit", styles["h2"]),
                paragraph(illusion_value_note(), styles["body"]),
                paragraph(
                    "Once the basic website fixes are live, Illusion can track whether AI answer engines actually mention the business for the questions customers ask.",
                    styles["body_strong"],
                ),
            ],
            width,
        )
    )

    story.append(PageBreak())
    story.append(paragraph("Detailed Findings", styles["title"]))
    for idx, finding in enumerate(findings[:9], start=1):
        story.append(KeepTogether([finding_card(finding, styles, width, idx), Spacer(1, 8)]))

    story.append(PageBreak())
    story.append(paragraph("Signals And Pages", styles["title"]))
    story.append(paragraph("Business signals", styles["h2"]))
    story.append(signals_table(report, styles, width))
    story.append(Spacer(1, 12))
    story.append(paragraph("Pages crawled", styles["h2"]))
    story.append(crawled_pages_table(report, styles, width))
    story.append(Spacer(1, 12))
    story.append(
        section_card(
            [
                paragraph("Suggested next step", styles["h2"]),
                paragraph(
                    "Fix the top 2-3 issues first, then rerun the audit. The goal is to make the site easier for customers, Google, and AI answer engines to understand before investing in heavier SEO or AI visibility work.",
                    styles["body"],
                ),
                paragraph(
                    "Run a fresh audit: https://www.illusion.ai/analyze",
                    styles["body_strong"],
                ),
            ],
            width,
        )
    )

    doc.build(story)


def generate_markdown(record: dict, research_row: dict[str, str], output_path: Path) -> None:
    report = record["report"]
    url = report.get("normalized_url") or record.get("url_private_do_not_publish") or ""
    domain = link_text(url)
    scores = report.get("scores") or {}
    findings = report.get("findings") or []
    lines = [
        f"# Illusion AI Website Audit: {domain}",
        "",
        f"URL: {url}",
        f"Contact email: {research_row.get('contact_email_public', '')}",
        f"Completed: {ascii_text(record.get('completed_at', ''))}",
        "",
        "## Scores",
        "",
        f"- Overall: {scores.get('overall')}",
        f"- User experience: {scores.get('ux')}",
        f"- SEO / local SEO: {scores.get('seo')}",
        f"- AI search readiness: {scores.get('ai')}",
        "",
        "## Executive Summary",
        "",
        ascii_text(report.get("executive_summary", "")),
        "",
        "## Top Findings",
        "",
    ]
    for idx, finding in enumerate(findings, start=1):
        lines.extend(
            [
                f"### {idx}. {ascii_text(finding.get('title', 'Finding'))}",
                "",
                f"- Severity: {ascii_text(finding.get('severity', ''))}",
                f"- Category: {ascii_text(finding.get('category', ''))}",
                f"- Evidence: {ascii_text(finding.get('evidence', ''))}",
                f"- Fix: {ascii_text(finding.get('fix', ''))}",
                f"- Expected impact: {ascii_text(finding.get('expected_impact', ''))}",
                f"- Effort: {ascii_text(finding.get('effort', ''))}",
                "",
            ]
        )
    lines.extend(
        [
            "## Personalized Action Plan",
            "",
        ]
    )
    for action in personalized_actions(findings):
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "## How Illusion Helps Beyond This Audit",
            "",
            ascii_text(why_it_matters_note()),
            "",
            ascii_text(illusion_value_note()),
            "",
            "After the website foundation is fixed, Illusion can monitor whether AI answer engines mention this business for customer questions, which competitors appear instead, and what to improve next.",
            "",
            "## Rerun",
            "",
            "Run a fresh audit at https://www.illusion.ai/analyze",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def outreach_row(
    record: dict,
    research_row: dict[str, str],
    pdf_path: Path,
    md_path: Path,
    mailing_address: str,
) -> dict[str, str]:
    report = record["report"]
    url = report.get("normalized_url") or record.get("url_private_do_not_publish") or ""
    domain = link_text(url)
    scores = report.get("scores") or {}
    findings = report.get("findings") or []
    top_titles = [ascii_text(finding.get("title")) for finding in findings[:3]]
    top_titles = [title for title in top_titles if title]
    actions = personalized_actions(findings, limit=4)
    action_block = "\n".join(f"- {action}" for action in actions)
    email_actions = email_action_items(findings, limit=4)
    email_action_block = "\n".join(f"- {action}" for action in email_actions)
    subject = f"Quick AI-readiness notes for {domain}"
    opener = (
        f"I ran a quick AI-readiness audit for {domain}. "
        f"The site scored {scores.get('overall')}/100, and the biggest fixes were "
        f"{top_fix_sentence(findings).lower()}."
    )
    send_ready = (
        "YES"
        if not mailing_address.startswith("TODO:")
        else "NO - add physical mailing address or registered mailbox before sending"
    )
    body = "\n\n".join(
        [
            "Hi,",
            (
                "I'm putting together a research piece on what small business websites get "
                "wrong before they are easy for Google and AI tools like ChatGPT, Claude, "
                "Gemini, and Perplexity to understand."
            ),
            (
                f"I ran a quick AI-readiness audit for {domain} and made you a short report. "
                f"Your site scored {scores.get('overall')}/100 overall."
            ),
            email_why_it_matters(domain),
            f"The biggest things I found:\n\n{email_action_block}",
            email_issue_impact_note(),
            (
                "I attached the short report. I made it practical and kept it focused on the "
                "main fixes."
            ),
            (
                "I will not name your business in the public research post unless you give "
                "permission; I'm using anonymized examples for the study."
            ),
            "You can rerun the free audit here:\nhttps://www.illusion.ai/analyze",
            illusion_value_note(),
            (
                "Disclosure: I'm the founder of Illusion, which offers AI search tracking and "
                "website cleanup services. I also offer a flat-fee website cleanup if you would "
                "rather have someone handle the fixes."
            ),
            "Let me know if you have any questions or want help fixing the issues.",
            "\n".join(
                [
                    "Best,",
                    "David C",
                    "Founder, Illusion",
                    "https://www.illusion.ai",
                    mailing_address,
                ]
            ),
        ]
    )

    return {
        "sample_id": record["sample_id"],
        "domain": domain,
        "url": url,
        "contact_email": research_row.get("contact_email_public", ""),
        "contact_email_source": research_row.get("contact_email_source", ""),
        "overall_score": str(scores.get("overall", "")),
        "subject": subject,
        "opener": opener,
        "personalized_actions": action_block,
        "illusion_value_note": illusion_value_note(),
        "mailing_address": mailing_address,
        "send_ready": send_ready,
        "email_body": body,
        "pdf_path": str(pdf_path),
        "markdown_path": str(md_path),
    }


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    pdf_dir = output_dir / "pdf"
    md_dir = output_dir / "markdown"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)

    research = read_research_rows(Path(args.research_csv))
    records = read_raw_records(Path(args.raw_jsonl))
    selected_ids = [args.sample_id] if args.sample_id else sorted(records)
    manifest_rows = []

    for sample_id in selected_ids:
        record = records.get(sample_id)
        if not record:
            raise SystemExit(f"No completed audit found for {sample_id}")
        row = research.get(sample_id, {})
        report = record["report"]
        url = report.get("normalized_url") or record.get("url_private_do_not_publish") or sample_id
        slug = f"{sample_id}-{slugify(url)}"
        pdf_path = pdf_dir / f"{slug}-ai-website-audit.pdf"
        md_path = md_dir / f"{slug}-ai-website-audit.md"
        generate_pdf(record, row, pdf_path)
        generate_markdown(record, row, md_path)
        manifest_rows.append(outreach_row(record, row, pdf_path, md_path, args.mailing_address))
        print(f"Generated {pdf_path}")

    manifest_path = output_dir / "outreach-manifest.csv"
    fieldnames = [
        "sample_id",
        "domain",
        "url",
        "contact_email",
        "contact_email_source",
        "overall_score",
        "subject",
        "opener",
        "personalized_actions",
        "illusion_value_note",
        "mailing_address",
        "send_ready",
        "email_body",
        "pdf_path",
        "markdown_path",
    ]
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
