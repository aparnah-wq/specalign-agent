"""Option A document ingestion and bounded section-reader tools for SpecAlign.

Supports pasted Google Doc text/Markdown plus `.docx`, `.md`, and `.txt` file
exports without requiring live Google Drive OAuth in Phase 1. All tool functions
return structured JSON-serializable dicts with actionable `recovery_guidance`
instead of raising raw Python tracebacks to the LLM.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from difflib import get_close_matches
from pathlib import Path
from typing import Any

from app.callbacks import redact_pii
from app.telemetry import trace_tool_call

try:
    from google.adk.tools import ToolContext
except ImportError:  # Allows offline unit testing without google-adk installed.
    ToolContext = Any  # type: ignore[misc, assignment]

VALID_DOC_ROLES: frozenset[str] = frozenset({"prd", "tdd", "business_goals"})
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".md", ".markdown", ".txt", ".docx"})
MAX_SECTION_READS: int = 15
MAX_CHUNK_CHARS: int = 4000

_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
_NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)+\.?|\d+\.)\s+([A-Z][^\n]{1,100})$")
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _error(error_code: str, message: str, recovery_guidance: str) -> dict[str, Any]:
    """Return a consistent structured error envelope with LLM recovery guidance."""
    return {
        "status": "error",
        "error_code": error_code,
        "message": message,
        "recovery_guidance": recovery_guidance,
    }


def _get_state(tool_context: ToolContext | None) -> dict[str, Any]:
    """Extract mutable state dict from ADK ToolContext or fallback dict."""
    if tool_context is None:
        return {}
    state = getattr(tool_context, "state", None)
    if state is None:
        return {}
    return state


def _extract_docx_with_stdlib(path: Path) -> str:
    """Parse headings, paragraphs, and tables from a .docx archive using stdlib XML."""
    with zipfile.ZipFile(path, "r") as archive:
        if "word/document.xml" not in archive.namelist():
            raise ValueError("Archive is missing word/document.xml.")
        xml_bytes = archive.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    body = root.find(f"{_W_NS}body")
    if body is None:
        return ""

    blocks: list[str] = []
    for child in body:
        if child.tag == f"{_W_NS}p":
            text = "".join(
                t.text for t in child.findall(f".//{_W_NS}t") if t.text
            ).strip()
            if not text:
                continue
            style_el = child.find(f"{_W_NS}pPr/{_W_NS}pStyle")
            style_val = (
                style_el.attrib.get(f"{_W_NS}val", "") if style_el is not None else ""
            )
            level_match = re.match(r"Heading(\d)", style_val, re.IGNORECASE)
            if level_match:
                level = min(int(level_match.group(1)), 6)
                blocks.append(f"{'#' * level} {text}")
            elif style_val.lower() == "title":
                blocks.append(f"# {text}")
            else:
                blocks.append(text)
        elif child.tag == f"{_W_NS}tbl":
            rows: list[list[str]] = []
            for tr in child.findall(f"{_W_NS}tr"):
                cells: list[str] = []
                for tc in tr.findall(f"{_W_NS}tc"):
                    cell_text = " ".join(
                        t.text.strip()
                        for t in tc.findall(f".//{_W_NS}t")
                        if t.text and t.text.strip()
                    )
                    cells.append(cell_text.replace("|", "\\|"))
                if cells:
                    rows.append(cells)
            if rows:
                header = rows[0]
                md_table = [
                    "| " + " | ".join(header) + " |",
                    "| " + " | ".join("---" for _ in header) + " |",
                ]
                for row in rows[1:]:
                    padded = row + [""] * max(0, len(header) - len(row))
                    md_table.append("| " + " | ".join(padded[: len(header)]) + " |")
                blocks.append("\n".join(md_table))

    return "\n\n".join(blocks)


def _extract_docx_text(path: Path) -> str:
    """Read a .docx document into normalized Markdown using python-docx or stdlib fallback."""
    try:
        import docx  # type: ignore[import-not-found]
    except ImportError:
        return _extract_docx_with_stdlib(path)

    document = docx.Document(str(path))
    blocks: list[str] = []
    para_map = {p._element: p for p in document.paragraphs}
    table_map = {t._element: t for t in document.tables}

    for child in document.element.body:
        if child in para_map:
            para = para_map[child]
            text = para.text.strip()
            if not text:
                continue
            style_name = para.style.name if para.style else ""
            p_style_el = para._element.find(f"{_W_NS}pPr/{_W_NS}pStyle")
            xml_style = (
                p_style_el.attrib.get(f"{_W_NS}val", "")
                if p_style_el is not None
                else ""
            )
            level_match = re.match(
                r"Heading\s*(\d)", style_name, re.IGNORECASE
            ) or re.match(r"Heading\s*(\d)", xml_style, re.IGNORECASE)
            if level_match:
                level = min(int(level_match.group(1)), 6)
                blocks.append(f"{'#' * level} {text}")
            elif style_name.lower() == "title" or xml_style.lower() == "title":
                blocks.append(f"# {text}")
            else:
                blocks.append(text)
        elif child in table_map:
            table = table_map[child]
            rows = [
                [
                    cell.text.strip().replace("\n", " ").replace("|", "\\|")
                    for cell in row.cells
                ]
                for row in table.rows
            ]
            if rows:
                header = rows[0]
                md_table = [
                    "| " + " | ".join(header) + " |",
                    "| " + " | ".join("---" for _ in header) + " |",
                ]
                for row in rows[1:]:
                    md_table.append("| " + " | ".join(row) + " |")
                blocks.append("\n".join(md_table))

    return "\n\n".join(blocks)


def _split_into_sections(normalized_text: str) -> dict[str, str]:
    """Split normalized Markdown or plain text into an ordered heading-to-body map."""
    sections: dict[str, str] = {}
    current_heading: str | None = None
    buffer: list[str] = []
    in_code_fence = False

    def _flush(heading: str | None, lines: list[str]) -> None:
        body = "\n".join(lines).strip()
        if heading is None and not body:
            return
        base_title = heading or "Document Overview"
        title = base_title
        suffix = 2
        while title in sections:
            title = f"{base_title} ({suffix})"
            suffix += 1
        sections[title] = body if body else base_title

    for raw_line in normalized_text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            buffer.append(raw_line)
            continue

        if not in_code_fence:
            md_match = _MD_HEADING_RE.match(stripped)
            if md_match:
                _flush(current_heading, buffer)
                current_heading = md_match.group(2).strip()
                buffer = []
                continue

            num_match = _NUMBERED_HEADING_RE.match(stripped)
            if num_match and not stripped.endswith("."):
                _flush(current_heading, buffer)
                current_heading = stripped
                buffer = []
                continue

        buffer.append(raw_line)

    _flush(current_heading, buffer)
    if not sections and normalized_text.strip():
        sections["Document Overview"] = normalized_text.strip()
    return sections


@trace_tool_call()
def ingest_document(
    doc_role: str,
    raw_text: str | None = None,
    file_path: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Ingest and section-index a PRD, TDD, or Business Goals document into session state.

    Accepts either pasted text/Markdown (`raw_text`) directly from chat or a
    local path (`file_path`) to a `.docx`, `.md`, or `.txt` export from Google Docs.

    Args:
        doc_role: Document category — must be one of `'prd'`, `'tdd'`, or
            `'business_goals'`.
        raw_text: Optional pasted UTF-8 text or Markdown content.
        file_path: Optional path to a `.docx`, `.md`, or `.txt` file.
        tool_context: ADK-injected context providing mutable `session.state`.

    Returns:
        Structured dictionary with `status`, `doc_role`, `source_format`,
        `section_count`, `total_words`, and `headings`, or a guided error dict
        with `recovery_guidance` on invalid input.
    """
    role = doc_role.strip().lower()
    if role not in VALID_DOC_ROLES:
        return _error(
            "INVALID_DOC_ROLE",
            f"Unsupported doc_role '{doc_role}'.",
            "Pass doc_role as one of: 'prd', 'tdd', or 'business_goals'.",
        )

    if not raw_text and not file_path:
        return _error(
            "INVALID_INPUT",
            "Neither raw_text nor file_path was provided.",
            "Paste the document text directly in chat or provide a .docx, .md, or .txt file path.",
        )

    source_format = "pasted_text"
    content_text = ""

    if file_path:
        path = Path(file_path).expanduser()
        if not path.is_file():
            return _error(
                "FILE_NOT_FOUND",
                f"File not found at '{file_path}'.",
                "Verify the file path exists, or paste the Google Doc text directly into chat.",
            )
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return _error(
                "UNSUPPORTED_FORMAT",
                f"Unsupported file extension '{ext}'.",
                "Export the Google Doc as .docx, .md, or .txt (File -> Download), or paste the text directly in chat.",
            )
        try:
            if ext == ".docx":
                source_format = "docx"
                content_text = _extract_docx_text(path)
            else:
                source_format = ext.lstrip(".")
                content_text = path.read_text(encoding="utf-8")
        except (
            OSError,
            UnicodeDecodeError,
            zipfile.BadZipFile,
            ET.ParseError,
            ValueError,
        ) as exc:
            return _error(
                "CORRUPT_DOCUMENT",
                f"Unable to read '{path.name}': {exc}",
                "Re-export the file as UTF-8 Markdown (.md) or Word (.docx), or paste the document text directly.",
            )
    else:
        content_text = raw_text or ""

    if not content_text.strip():
        return _error(
            "EMPTY_DOCUMENT",
            f"The supplied {role} document is empty.",
            f"Provide non-empty content for '{role}' before running alignment checks.",
        )

    # Scrub PII deterministically before indexing into session state.
    sanitized_text = redact_pii(content_text)
    sections = _split_into_sections(sanitized_text)
    state = _get_state(tool_context)
    ingested_docs = state.setdefault("ingested_docs", {})
    ingested_docs[role] = sections

    # Reset bounded read counter whenever a fresh revision is ingested.
    read_counts = state.setdefault("section_read_counts", {})
    read_counts[role] = 0

    total_words = sum(len(body.split()) for body in sections.values())
    return {
        "status": "success",
        "doc_role": role,
        "source_format": source_format,
        "section_count": len(sections),
        "total_words": total_words,
        "headings": list(sections.keys()),
    }


@trace_tool_call()
def list_doc_sections(
    doc_role: str,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """List the ordered table of contents (headings and word counts) for an ingested document.

    Use this before calling `read_doc_section` so you only inspect relevant
    sections without bloating the prompt context window.

    Args:
        doc_role: Target document role (`'prd'`, `'tdd'`, or `'business_goals'`).
        tool_context: ADK-injected context providing `session.state`.

    Returns:
        Dictionary containing `status` and `sections` (`heading`, `word_count`),
        or a guided `missing_doc` response instructing the agent what to ask for.
    """
    role = doc_role.strip().lower()
    if role not in VALID_DOC_ROLES:
        return _error(
            "INVALID_DOC_ROLE",
            f"Unsupported doc_role '{doc_role}'.",
            "Pass doc_role as one of: 'prd', 'tdd', or 'business_goals'.",
        )

    state = _get_state(tool_context)
    sections = state.get("ingested_docs", {}).get(role)
    if not sections:
        return {
            "status": "missing_doc",
            "error_code": "MISSING_REQUIRED_DOCUMENT",
            "doc_role": role,
            "message": f"No '{role}' document has been ingested in this session yet.",
            "recovery_guidance": (
                f"Ask the user to paste the {role.upper()} text or upload a .docx/.md/.txt export "
                "before proceeding with alignment analysis."
            ),
        }

    toc = [
        {"heading": heading, "word_count": len(body.split())}
        for heading, body in sections.items()
    ]
    return {
        "status": "success",
        "doc_role": role,
        "section_count": len(toc),
        "sections": toc,
    }


@trace_tool_call()
def read_doc_section(
    doc_role: str,
    section_heading: str,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Read a single heading's normalized text from an ingested document with loop and size caps.

    Enforces a maximum of `15` section reads per document and truncates content
    beyond `4,000` characters to prevent runaway loops and context overflow.

    Args:
        doc_role: Target document role (`'prd'`, `'tdd'`, or `'business_goals'`).
        section_heading: Heading title from `list_doc_sections` (case-insensitive).
        tool_context: ADK-injected context providing `session.state`.

    Returns:
        Dictionary containing `status`, `heading`, `content`, `truncated`, and
        `reads_remaining`, or a structured error envelope with fuzzy heading
        suggestions if not found.
    """
    role = doc_role.strip().lower()
    if role not in VALID_DOC_ROLES:
        return _error(
            "INVALID_DOC_ROLE",
            f"Unsupported doc_role '{doc_role}'.",
            "Pass doc_role as one of: 'prd', 'tdd', or 'business_goals'.",
        )

    state = _get_state(tool_context)
    sections: dict[str, str] | None = state.get("ingested_docs", {}).get(role)
    if not sections:
        return {
            "status": "missing_doc",
            "error_code": "MISSING_REQUIRED_DOCUMENT",
            "doc_role": role,
            "message": f"No '{role}' document has been ingested in this session yet.",
            "recovery_guidance": (
                f"Call ingest_document for '{role}' first, or ask the user to paste or upload it."
            ),
        }

    read_counts = state.setdefault("section_read_counts", {})
    used = int(read_counts.get(role, 0))
    if used >= MAX_SECTION_READS:
        return _error(
            "READ_LIMIT_EXCEEDED",
            f"Reached maximum of {MAX_SECTION_READS} section reads for '{role}'.",
            "Synthesize your findings from the sections already inspected rather than re-reading.",
        )

    # Resolve exact or case-insensitive heading match.
    matched_heading: str | None = None
    if section_heading in sections:
        matched_heading = section_heading
    else:
        lowered = section_heading.strip().lower()
        for candidate in sections:
            if candidate.strip().lower() == lowered:
                matched_heading = candidate
                break

    if matched_heading is None:
        suggestions = get_close_matches(
            section_heading, list(sections.keys()), n=3, cutoff=0.4
        )
        hint = (
            f"Did you mean one of: {suggestions}?"
            if suggestions
            else f"Call list_doc_sections(doc_role='{role}') to view valid headings."
        )
        return _error(
            "SECTION_NOT_FOUND",
            f"Heading '{section_heading}' was not found in '{role}'.",
            hint,
        )

    read_counts[role] = used + 1
    raw_content = sections[matched_heading]
    truncated = len(raw_content) > MAX_CHUNK_CHARS
    content = raw_content[:MAX_CHUNK_CHARS] if truncated else raw_content

    return {
        "status": "success",
        "doc_role": role,
        "heading": matched_heading,
        "content": content,
        "truncated": truncated,
        "reads_remaining": MAX_SECTION_READS - read_counts[role],
    }
