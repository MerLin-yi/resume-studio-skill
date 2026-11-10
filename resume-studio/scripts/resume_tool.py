#!/usr/bin/env python3
"""Portable resume workspace, audit, and render helpers."""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote


SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ASSETS = SKILL_ROOT / "assets" / "workspace"
STYLESHEET = SKILL_ROOT / "assets" / "resume.css"

PLACEHOLDER_RE = re.compile(
    r"\{\{[^}]+\}\}|\bTODO\b|\[TODO|replace-with|Candidate Name|"
    r"Target role|example\.com|please fill|待填写|请填写|xxx+",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?"
    r"(?:1[3-9]\d{9}|(?:\(\d{2,4}\)|\d{2,4})[\s-]\d{3,4}[\s-]\d{4})(?!\d)"
)
NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(\s*%)?")
HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
UL_RE = re.compile(r"^\s*[-*+]\s+(.+)$")
OL_RE = re.compile(r"^\s*\d+[.)]\s+(.+)$")
STRONG_CLAIMS = (
    "精通",
    "主导",
    "独立负责",
    "从0到1",
    "首创",
    "行业领先",
    "显著提升",
    "大幅提升",
    "唯一",
    "全国第一",
    "owned",
    "led ",
    "production-grade",
    "state-of-the-art",
)


class ResumeToolError(RuntimeError):
    """User-correctable resume tool error."""


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ResumeToolError(f"File not found: {path}") from exc
    except UnicodeDecodeError as exc:
        raise ResumeToolError(f"File is not valid UTF-8: {path}") from exc


def _without_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    return text[end + 5 :] if end >= 0 else text


def _normalize_for_match(text: str) -> str:
    return re.sub(r"[\s\-()（）]+", "", text).lower()


def _numbers(text: str) -> set[str]:
    return {match.group(1) for match in NUMBER_RE.finditer(text)}


def _plain_text(markdown_text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", markdown_text)
    text = re.sub(r"!\[[^\]]*]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(r"[`*_>|#-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def init_workspace(
    destination: Path,
    *,
    name: str,
    force: bool = False,
) -> dict:
    if not WORKSPACE_ASSETS.is_dir():
        raise ResumeToolError(f"Workspace assets are missing: {WORKSPACE_ASSETS}")
    if destination.exists() and any(destination.iterdir()) and not force:
        raise ResumeToolError(
            f"Destination is not empty: {destination}. Choose another path or pass --force."
        )
    destination.mkdir(parents=True, exist_ok=True)
    for source in WORKSPACE_ASSETS.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(WORKSPACE_ASSETS)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        content = source.read_text(encoding="utf-8")
        target.write_text(content.replace("{{NAME}}", name), encoding="utf-8")
    return {
        "status": "ok",
        "workspace": str(destination.resolve()),
        "next": [
            "Fill profile.md and evidence.md with verified facts.",
            "Put each target JD in targets/<slug>/jd.md and update brief.json.",
            "Write the tailored resume.md, then run audit and render.",
        ],
    }


def audit_resume(
    resume_path: Path,
    *,
    source_paths: list[Path],
    brief_path: Path | None = None,
) -> dict:
    resume_text = _without_frontmatter(_text(resume_path))
    source_text = "\n\n".join(_without_frontmatter(_text(path)) for path in source_paths)
    if not resume_text.strip():
        raise ResumeToolError("Resume Markdown is empty")
    if not source_text.strip():
        raise ResumeToolError("At least one non-empty evidence source is required")

    brief: dict = {}
    if brief_path:
        try:
            parsed = json.loads(_text(brief_path))
        except json.JSONDecodeError as exc:
            raise ResumeToolError(f"Invalid brief JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ResumeToolError("brief.json must contain a JSON object")
        brief = parsed

    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    plain = _plain_text(resume_text)

    headings = [(len(match.group(1)), match.group(2).strip()) for match in map(HEADING_RE.match, resume_text.splitlines()) if match]
    h1_count = sum(1 for level, _ in headings if level == 1)
    h2_count = sum(1 for level, _ in headings if level == 2)
    if h1_count != 1:
        errors.append(f"Expected exactly one H1 name heading; found {h1_count}.")
    if h2_count < 2:
        errors.append(f"Expected at least two H2 sections; found {h2_count}.")

    placeholders = sorted(set(PLACEHOLDER_RE.findall(resume_text)))
    if placeholders:
        errors.append("Replace placeholders before delivery: " + ", ".join(placeholders))

    source_normalized = _normalize_for_match(source_text)
    for email in sorted(set(EMAIL_RE.findall(resume_text)), key=str.lower):
        if _normalize_for_match(email) not in source_normalized:
            errors.append(f"Email is not present in the evidence sources: {email}")
    for phone in sorted(set(PHONE_RE.findall(resume_text))):
        if _normalize_for_match(phone) not in source_normalized:
            errors.append(f"Phone number is not present in the evidence sources: {phone}")

    if brief.get("include_contact", True) and not EMAIL_RE.search(resume_text) and not PHONE_RE.search(resume_text):
        warnings.append("Contact output is enabled, but the resume contains no phone or email.")

    source_numbers = _numbers(source_text)
    unsupported_numbers: list[str] = []
    for match in NUMBER_RE.finditer(resume_text):
        value = match.group(1)
        percent_marker = match.group(2) or ""
        compact = value.replace(".", "")
        if value in source_numbers:
            continue
        if not percent_marker and len(compact) < 2:
            continue
        unsupported_numbers.append(f"{value}{percent_marker.strip()}" if percent_marker else value)
    if unsupported_numbers:
        warnings.append(
            "Check these numbers against the evidence sources: "
            + ", ".join(dict.fromkeys(unsupported_numbers))
        )

    source_lower = source_text.lower()
    risky_phrases = [
        phrase
        for phrase in STRONG_CLAIMS
        if phrase.lower() in resume_text.lower() and phrase.lower() not in source_lower
    ]
    if risky_phrases:
        warnings.append(
            "Strong ownership/impact language needs manual evidence review: "
            + ", ".join(risky_phrases)
        )

    keywords = brief.get("keywords") if isinstance(brief.get("keywords"), list) else []
    missing_keywords = [
        str(keyword).strip()
        for keyword in keywords
        if str(keyword).strip()
        and not PLACEHOLDER_RE.search(str(keyword))
        and str(keyword).strip().lower() not in resume_text.lower()
    ]
    if missing_keywords:
        warnings.append(
            "Target keywords not present (add only where supported): "
            + ", ".join(missing_keywords)
        )

    bullet_count = sum(
        1
        for line in resume_text.splitlines()
        if UL_RE.match(line) or OL_RE.match(line)
    )
    if bullet_count < 3:
        info.append("Fewer than three bullet points found; confirm the document has enough evidence.")

    page_target = int(brief.get("pages") or 1)
    rough_pages = max(1, math.ceil(len(plain) / 1800))
    if rough_pages > page_target:
        warnings.append(
            f"Rough text-length estimate is {rough_pages} pages against a {page_target}-page target; "
            "confirm with the rendered PDF."
        )

    info.append(f"Character count: {len(plain)}")
    info.append(f"Headings: {', '.join(title for _, title in headings)}")
    info.append(f"Bullet count: {bullet_count}")

    return {
        "status": "pass" if not errors else "fail",
        "resume": str(resume_path.resolve()),
        "sources": [str(path.resolve()) for path in source_paths],
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "characters": len(plain),
            "rough_pages": rough_pages,
        },
        "errors": errors,
        "warnings": warnings,
        "info": info,
    }


def _safe_url(url: str) -> str:
    lowered = url.strip().lower()
    if lowered.startswith(("https://", "http://", "mailto:")):
        return url.strip()
    return "#"


def _inline_markup(text: str) -> str:
    escaped = html.escape(text, quote=False)

    def link_replacement(match: re.Match[str]) -> str:
        label = match.group(1)
        url = _safe_url(match.group(2))
        return f'<a href="{html.escape(url, quote=True)}">{label}</a>'

    escaped = re.sub(r"\[([^\]]+)]\(([^)]+)\)", link_replacement, escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
    return escaped


def markdown_to_html(markdown_text: str) -> str:
    lines = _without_frontmatter(markdown_text).splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    list_tag: str | None = None
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            joined = "<br>\n".join(_inline_markup(line.strip()) for line in paragraph)
            output.append(f"<p>{joined}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            output.append(f"</{list_tag}>")
            list_tag = None

    while index < len(lines):
        line = lines[index].rstrip()
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            close_list()
            index += 1
            continue

        if stripped == "<!-- pagebreak -->":
            flush_paragraph()
            close_list()
            output.append('<div class="page-break"></div>')
            index += 1
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            flush_paragraph()
            close_list()
            level = len(heading_match.group(1))
            output.append(f"<h{level}>{_inline_markup(heading_match.group(2))}</h{level}>")
            index += 1
            continue

        if re.fullmatch(r"\s*(?:---+|\*\*\*+)\s*", line):
            flush_paragraph()
            close_list()
            output.append("<hr>")
            index += 1
            continue

        bullet_match = UL_RE.match(line)
        if bullet_match:
            flush_paragraph()
            if list_tag != "ul":
                close_list()
                output.append("<ul>")
                list_tag = "ul"
            output.append(f"<li>{_inline_markup(bullet_match.group(1))}</li>")
            index += 1
            continue

        ordered_match = OL_RE.match(line)
        if ordered_match:
            flush_paragraph()
            if list_tag != "ol":
                close_list()
                output.append("<ol>")
                list_tag = "ol"
            output.append(f"<li>{_inline_markup(ordered_match.group(1))}</li>")
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines):
            separator = lines[index + 1].strip()
            if re.fullmatch(r"\|?[\s:|-]+\|?", separator) and "-" in separator:
                flush_paragraph()
                close_list()
                rows = [stripped]
                index += 2
                while index < len(lines) and lines[index].strip().startswith("|"):
                    rows.append(lines[index].strip())
                    index += 1
                cells = [[cell.strip() for cell in row.strip("|").split("|")] for row in rows]
                output.append("<table><thead><tr>")
                output.extend(f"<th>{_inline_markup(cell)}</th>" for cell in cells[0])
                output.append("</tr></thead><tbody>")
                for row in cells[1:]:
                    output.append("<tr>")
                    output.extend(f"<td>{_inline_markup(cell)}</td>" for cell in row)
                    output.append("</tr>")
                output.append("</tbody></table>")
                continue

        close_list()
        paragraph.append(line)
        index += 1

    flush_paragraph()
    close_list()
    return "\n".join(output)


def _find_browser() -> Path | None:
    configured = os.environ.get("RESUME_BROWSER") or os.environ.get("BROWSER_BIN")
    if configured and Path(configured).is_file():
        return Path(configured)

    candidates: list[Path] = []
    if os.name == "nt":
        roots = [
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        relative_paths = [
            "Google/Chrome/Application/chrome.exe",
            "Microsoft/Edge/Application/msedge.exe",
            "Chromium/Application/chrome.exe",
            "BraveSoftware/Brave-Browser/Application/brave.exe",
        ]
        for root in roots:
            if root:
                candidates.extend(Path(root) / relative for relative in relative_paths)
    elif sys.platform == "darwin":
        candidates.extend(
            [
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
                Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
            ]
        )
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "brave-browser"):
            found = shutil.which(name)
            if found:
                candidates.append(Path(found))

    return next((path for path in candidates if path.is_file()), None)


def _pdf_page_count(path: Path) -> int | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return len(re.findall(rb"/Type\s*/Page\b", data)) or None


def _print_pdf(browser: Path, html_path: Path, pdf_path: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="resume-browser-") as profile:
        command = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={pdf_path.resolve()}",
            "--no-pdf-header-footer",
            html_path.resolve().as_uri(),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, str(exc)
    if not pdf_path.is_file() or pdf_path.stat().st_size < 1000:
        detail = (completed.stderr or completed.stdout or "").strip()
        return False, detail[-1000:] or f"Browser exited with code {completed.returncode}"
    if not pdf_path.read_bytes().startswith(b"%PDF"):
        return False, "Browser output is not a PDF"
    return True, ""


def render_resume(
    resume_path: Path,
    *,
    output_dir: Path,
    title: str,
    language: str,
) -> dict:
    if not STYLESHEET.is_file():
        raise ResumeToolError(f"Stylesheet is missing: {STYLESHEET}")
    markdown_text = _text(resume_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    body = markdown_to_html(markdown_text)
    css = STYLESHEET.read_text(encoding="utf-8")
    document = (
        "<!doctype html>\n"
        f'<html lang="{html.escape(language, quote=True)}">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>\n{css}\n</style>\n"
        "</head>\n"
        f"<body>\n{body}\n</body>\n"
        "</html>\n"
    )
    html_path = output_dir / "resume.html"
    html_path.write_text(document, encoding="utf-8")

    pdf_path = output_dir / "resume.pdf"
    pdf_path.unlink(missing_ok=True)
    browser = _find_browser()
    pdf_ready = False
    render_message = "PDF skipped."
    if browser:
        pdf_ready, render_message = _print_pdf(browser, html_path, pdf_path)
        if not pdf_ready:
            pdf_path.unlink(missing_ok=True)
    else:
        render_message = (
            "No Chrome, Edge, Chromium, or Brave browser found. "
            "Open resume.html and print to PDF manually."
        )

    return {
        "status": "ok" if pdf_ready else "html_only",
        "html": str(html_path.resolve()),
        "pdf": str(pdf_path.resolve()) if pdf_ready else "",
        "pdf_pages": _pdf_page_count(pdf_path) if pdf_ready else None,
        "browser": str(browser) if browser else "",
        "message": render_message,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a portable resume workspace.")
    init_parser.add_argument("workspace", type=Path)
    init_parser.add_argument("--name", required=True)
    init_parser.add_argument("--force", action="store_true")

    audit_parser = subparsers.add_parser("audit", help="Check evidence, placeholders, and structure.")
    audit_parser.add_argument("resume", type=Path)
    audit_parser.add_argument("--source", action="append", type=Path, required=True)
    audit_parser.add_argument("--brief", type=Path)
    audit_parser.add_argument("--json-out", type=Path)

    render_parser = subparsers.add_parser("render", help="Render Markdown to styled HTML and PDF.")
    render_parser.add_argument("resume", type=Path)
    render_parser.add_argument("--out-dir", type=Path)
    render_parser.add_argument("--title", default="Resume")
    render_parser.add_argument("--lang", default="zh-CN")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "init":
            result = init_workspace(args.workspace, name=args.name, force=args.force)
        elif args.command == "audit":
            result = audit_resume(
                args.resume,
                source_paths=args.source,
                brief_path=args.brief,
            )
            if args.json_out:
                args.json_out.parent.mkdir(parents=True, exist_ok=True)
                args.json_out.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
        else:
            out_dir = args.out_dir or args.resume.parent
            result = render_resume(
                args.resume,
                output_dir=out_dir,
                title=args.title,
                language=args.lang,
            )
    except ResumeToolError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("status") == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
