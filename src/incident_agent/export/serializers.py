"""Serializers for exporting final incident reports."""

from __future__ import annotations

import html
import json
from typing import Literal

from incident_agent.schemas.final_report import FinalIncidentReport

ExportFormat = Literal["json", "md", "html"]


def serialize_report(report: FinalIncidentReport, *, output_format: ExportFormat) -> str:
    """Serialize one report to the requested export format."""

    if output_format == "json":
        return serialize_report_as_json(report)
    if output_format == "md":
        return serialize_report_as_markdown(report)
    return serialize_report_as_html(report)


def serialize_report_as_json(report: FinalIncidentReport) -> str:
    """Render canonical JSON export."""

    return json.dumps(report.model_dump(mode="json"), indent=2)


def serialize_report_as_markdown(report: FinalIncidentReport) -> str:
    """Render Markdown export."""

    return (
        f"# Incident Report: {report.incident_id}\n\n"
        f"## Incident Summary\n{report.incident_summary}\n\n"
        f"## Root Cause Explanation\n{report.root_cause_explanation}\n\n"
        f"## Executive Summary\n{report.executive_summary}\n\n"
        f"## Engineering Handoff\n{report.engineering_handoff}\n\n"
        "## Remediation Suggestions\n"
        f"{_markdown_list(report.remediation_suggestions)}\n\n"
        "## Facts\n"
        f"{_markdown_list(report.facts)}\n\n"
        "## Inferences\n"
        f"{_markdown_list(report.inferences)}\n\n"
        "## Uncertainties\n"
        f"{_markdown_list(report.uncertainties)}\n"
    )


def serialize_report_as_html(report: FinalIncidentReport) -> str:
    """Render a presentable standalone HTML export."""

    title = html.escape(f"Incident Report: {report.incident_id}")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{title}</title>\n"
        "  <style>\n"
        "    :root {\n"
        "      --bg: #f3efe5;\n"
        "      --paper: #fffdf7;\n"
        "      --ink: #1f2933;\n"
        "      --muted: #52606d;\n"
        "      --accent: #c2410c;\n"
        "      --line: #e6dfcf;\n"
        "      --chip: #f7ede2;\n"
        "    }\n"
        "    * { box-sizing: border-box; }\n"
        "    body {\n"
        "      margin: 0;\n"
        "      background: radial-gradient(circle at top left, #fff6df, var(--bg));\n"
        "      color: var(--ink);\n"
        '      font-family: Georgia, "Times New Roman", serif;\n'
        "      line-height: 1.6;\n"
        "    }\n"
        "    main {\n"
        "      max-width: 980px;\n"
        "      margin: 0 auto;\n"
        "      padding: 48px 20px 72px;\n"
        "    }\n"
        "    .hero {\n"
        "      background: var(--paper);\n"
        "      border: 1px solid var(--line);\n"
        "      border-radius: 24px;\n"
        "      padding: 32px;\n"
        "      box-shadow: 0 20px 50px rgba(31, 41, 51, 0.08);\n"
        "    }\n"
        "    .eyebrow {\n"
        "      color: var(--accent);\n"
        "      font-size: 12px;\n"
        "      font-weight: 700;\n"
        "      letter-spacing: 0.2em;\n"
        "      text-transform: uppercase;\n"
        "      margin-bottom: 12px;\n"
        "    }\n"
        "    h1, h2 {\n"
        "      margin: 0 0 12px;\n"
        "      font-weight: 600;\n"
        "      line-height: 1.15;\n"
        "    }\n"
        "    h1 { font-size: clamp(2.2rem, 4vw, 4rem); }\n"
        "    h2 { font-size: 1.35rem; margin-top: 28px; }\n"
        "    p { margin: 0; }\n"
        "    .lede {\n"
        "      color: var(--muted);\n"
        "      font-size: 1.1rem;\n"
        "      margin-top: 10px;\n"
        "    }\n"
        "    .grid {\n"
        "      display: grid;\n"
        "      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));\n"
        "      gap: 18px;\n"
        "      margin-top: 28px;\n"
        "    }\n"
        "    .card {\n"
        "      background: rgba(255, 253, 247, 0.88);\n"
        "      border: 1px solid var(--line);\n"
        "      border-radius: 18px;\n"
        "      padding: 20px;\n"
        "    }\n"
        "    .list {\n"
        "      list-style: none;\n"
        "      margin: 14px 0 0;\n"
        "      padding: 0;\n"
        "    }\n"
        "    .list li {\n"
        "      background: var(--chip);\n"
        "      border-radius: 12px;\n"
        "      padding: 10px 12px;\n"
        "      margin-bottom: 10px;\n"
        "    }\n"
        "    .section {\n"
        "      margin-top: 22px;\n"
        "      padding-top: 22px;\n"
        "      border-top: 1px solid var(--line);\n"
        "    }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        '    <section class="hero">\n'
        '      <div class="eyebrow">AI Incident Analysis</div>\n'
        f"      <h1>{html.escape(report.incident_id)}</h1>\n"
        f'      <p class="lede">{html.escape(report.executive_summary)}</p>\n'
        '      <div class="grid">\n'
        f"{_html_card('Incident Summary', report.incident_summary)}\n"
        f"{_html_card('Root Cause Explanation', report.root_cause_explanation)}\n"
        f"{_html_card('Engineering Handoff', report.engineering_handoff)}\n"
        "      </div>\n"
        '      <div class="section">\n'
        f"        {_html_list_section('Remediation Suggestions', report.remediation_suggestions)}\n"
        f"        {_html_list_section('Facts', report.facts)}\n"
        f"        {_html_list_section('Inferences', report.inferences)}\n"
        f"        {_html_list_section('Uncertainties', report.uncertainties)}\n"
        "      </div>\n"
        "    </section>\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def _markdown_list(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def _html_card(title: str, content: str) -> str:
    return (
        '        <article class="card">\n'
        f"          <h2>{html.escape(title)}</h2>\n"
        f"          <p>{html.escape(content)}</p>\n"
        "        </article>"
    )


def _html_list_section(title: str, items: list[str]) -> str:
    rendered_items = items or ["none"]
    body = "".join(f"<li>{html.escape(item)}</li>" for item in rendered_items)
    return f'        <h2>{html.escape(title)}</h2>\n        <ul class="list">{body}</ul>\n'
