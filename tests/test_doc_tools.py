"""Protected acceptance tests for Story S1-01 (F-01: Document Ingestion & Section Readers)."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.tools.doc_tools import (
    MAX_CHUNK_CHARS,
    MAX_SECTION_READS,
    ingest_document,
    list_doc_sections,
    read_doc_section,
)


@dataclass
class FakeToolContext:
    """Minimal stand-in for ADK ToolContext exposing mutable session state."""

    state: dict[str, Any] = field(default_factory=dict)


def _write_minimal_docx(path: Path) -> None:
    """Create a valid minimal OOXML .docx archive containing headings, body text, and a table."""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
      <w:r><w:t>1. Business Objectives</w:t></w:r>
    </w:p>
    <w:p>
      <w:r><w:t>Cut checkout latency below 2 seconds across all EU regions.</w:t></w:r>
    </w:p>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading2"/></w:pPr>
      <w:r><w:t>1.1 SLA Matrix</w:t></w:r>
    </w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Metric</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Target</w:t></w:r></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:p><w:r><w:t>p95 Latency</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>1.8s</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
      <w:r><w:t>2. Security Constraints</w:t></w:r>
    </w:p>
    <w:p>
      <w:r><w:t>All customer data must remain inside EU datacenters.</w:t></w:r>
    </w:p>
  </w:body>
</w:document>"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)


class TestDocTools(unittest.TestCase):
    """Acceptance tests for Option A document ingestion and bounded section reading."""

    def test_ingest_pasted_markdown_and_list_sections(self) -> None:
        ctx = FakeToolContext()
        md_text = (
            "# Checkout PRD\n"
            "Intro summary.\n\n"
            "## 1. Functional Requirements\n"
            "REQ-001: Support instant refunds under $500.\n\n"
            "## 2. Non-Functional Requirements\n"
            "Latency p95 <= 2.0s and EU data residency.\n"
        )
        res = ingest_document(doc_role="prd", raw_text=md_text, tool_context=ctx)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["doc_role"], "prd")
        self.assertEqual(res["section_count"], 3)
        self.assertIn("ingested_docs", ctx.state)
        self.assertIn("prd", ctx.state["ingested_docs"])

        toc = list_doc_sections(doc_role="prd", tool_context=ctx)
        self.assertEqual(toc["status"], "success")
        headings = [item["heading"] for item in toc["sections"]]
        self.assertEqual(
            headings,
            [
                "Checkout PRD",
                "1. Functional Requirements",
                "2. Non-Functional Requirements",
            ],
        )
        self.assertTrue(all(item["word_count"] > 0 for item in toc["sections"]))

    def test_ingest_pasted_plain_text_without_markdown_hashes(self) -> None:
        ctx = FakeToolContext()
        plain_text = (
            "1. Executive Summary\n"
            "We need to align design reviews across 30 squads.\n\n"
            "2. Key Constraints\n"
            "Zero PII leakage in logs.\n"
        )
        res = ingest_document(
            doc_role="business_goals", raw_text=plain_text, tool_context=ctx
        )
        self.assertEqual(res["status"], "success")
        toc = list_doc_sections(doc_role="business_goals", tool_context=ctx)
        headings = [item["heading"] for item in toc["sections"]]
        self.assertIn("1. Executive Summary", headings)
        self.assertIn("2. Key Constraints", headings)

    def test_ingest_unstructured_plain_text_falls_back_to_single_section(self) -> None:
        ctx = FakeToolContext()
        res = ingest_document(
            doc_role="business_goals",
            raw_text="Reduce manual review prep time by 60% in Q4.",
            tool_context=ctx,
        )
        self.assertEqual(res["status"], "success")
        toc = list_doc_sections(doc_role="business_goals", tool_context=ctx)
        self.assertEqual(len(toc["sections"]), 1)
        sec = read_doc_section(
            doc_role="business_goals",
            section_heading=toc["sections"][0]["heading"],
            tool_context=ctx,
        )
        self.assertIn("60%", sec["content"])

    def test_ingest_docx_file_extracts_headings_paragraphs_and_tables(self) -> None:
        ctx = FakeToolContext()
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample_prd.docx"
            _write_minimal_docx(docx_path)

            res = ingest_document(
                doc_role="prd", file_path=str(docx_path), tool_context=ctx
            )
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["source_format"], "docx")

            toc = list_doc_sections(doc_role="prd", tool_context=ctx)
            headings = [item["heading"] for item in toc["sections"]]
            self.assertIn("1. Business Objectives", headings)
            self.assertIn("1.1 SLA Matrix", headings)
            self.assertIn("2. Security Constraints", headings)

            sla_sec = read_doc_section(
                doc_role="prd", section_heading="1.1 SLA Matrix", tool_context=ctx
            )
            self.assertEqual(sla_sec["status"], "success")
            self.assertIn("p95 Latency", sla_sec["content"])
            self.assertIn("1.8s", sla_sec["content"])

    def test_ingest_local_md_and_txt_files(self) -> None:
        ctx = FakeToolContext()
        with tempfile.TemporaryDirectory() as tmpdir:
            md_file = Path(tmpdir) / "tdd.md"
            md_file.write_text(
                "# Architecture\nUses Firestore in us-central1.\n", encoding="utf-8"
            )
            txt_file = Path(tmpdir) / "goals.txt"
            txt_file.write_text(
                "Goal: Keep costs under $500/month.\n", encoding="utf-8"
            )

            r_md = ingest_document(
                doc_role="tdd", file_path=str(md_file), tool_context=ctx
            )
            r_txt = ingest_document(
                doc_role="business_goals", file_path=str(txt_file), tool_context=ctx
            )
            self.assertEqual(r_md["status"], "success")
            self.assertEqual(r_txt["status"], "success")

    def test_guided_error_recovery_never_raises_raw_tracebacks(self) -> None:
        ctx = FakeToolContext()

        bad_role = ingest_document(
            doc_role="invoice", raw_text="hello", tool_context=ctx
        )
        self.assertEqual(bad_role["status"], "error")
        self.assertEqual(bad_role["error_code"], "INVALID_DOC_ROLE")
        self.assertIn("recovery_guidance", bad_role)

        no_input = ingest_document(doc_role="prd", tool_context=ctx)
        self.assertEqual(no_input["status"], "error")
        self.assertEqual(no_input["error_code"], "INVALID_INPUT")
        self.assertIn("recovery_guidance", no_input)

        missing_file = ingest_document(
            doc_role="tdd", file_path="/nonexistent/path/tdd.md", tool_context=ctx
        )
        self.assertEqual(missing_file["status"], "error")
        self.assertEqual(missing_file["error_code"], "FILE_NOT_FOUND")
        self.assertIn("recovery_guidance", missing_file)

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_file = Path(tmpdir) / "spec.pdf"
            pdf_file.write_bytes(b"%PDF-1.4 fake")
            bad_ext = ingest_document(
                doc_role="prd", file_path=str(pdf_file), tool_context=ctx
            )
            self.assertEqual(bad_ext["status"], "error")
            self.assertEqual(bad_ext["error_code"], "UNSUPPORTED_FORMAT")
            self.assertIn(".docx", bad_ext["recovery_guidance"])

        empty_doc = ingest_document(
            doc_role="prd", raw_text="   \n\t  ", tool_context=ctx
        )
        self.assertEqual(empty_doc["status"], "error")
        self.assertEqual(empty_doc["error_code"], "EMPTY_DOCUMENT")

        missing_toc = list_doc_sections(doc_role="tdd", tool_context=ctx)
        self.assertEqual(missing_toc["status"], "missing_doc")
        self.assertEqual(missing_toc["error_code"], "MISSING_REQUIRED_DOCUMENT")
        self.assertIn("recovery_guidance", missing_toc)

    def test_read_section_fuzzy_suggestions_and_case_insensitive_match(self) -> None:
        ctx = FakeToolContext()
        ingest_document(
            doc_role="tdd",
            raw_text="## Security & IAM\nUses specalign-agent-sa.\n\n## Trade-Offs\nAsync queue.\n",
            tool_context=ctx,
        )

        ok = read_doc_section(
            doc_role="tdd", section_heading="security & iam", tool_context=ctx
        )
        self.assertEqual(ok["status"], "success")
        self.assertIn("specalign-agent-sa", ok["content"])

        miss = read_doc_section(
            doc_role="tdd", section_heading="Securty IAM", tool_context=ctx
        )
        self.assertEqual(miss["status"], "error")
        self.assertEqual(miss["error_code"], "SECTION_NOT_FOUND")
        self.assertIn("Security & IAM", miss["recovery_guidance"])

    def test_read_section_chunk_truncation_and_max_read_loop_cap(self) -> None:
        ctx = FakeToolContext()
        long_body = "A" * (MAX_CHUNK_CHARS + 1200)
        ingest_document(
            doc_role="prd",
            raw_text=f"## Huge Section\n{long_body}\n",
            tool_context=ctx,
        )

        first = read_doc_section(
            doc_role="prd", section_heading="Huge Section", tool_context=ctx
        )
        self.assertEqual(first["status"], "success")
        self.assertTrue(first["truncated"])
        self.assertLessEqual(len(first["content"]), MAX_CHUNK_CHARS)

        for _ in range(MAX_SECTION_READS - 1):
            r = read_doc_section(
                doc_role="prd", section_heading="Huge Section", tool_context=ctx
            )
            self.assertEqual(r["status"], "success")

        blocked = read_doc_section(
            doc_role="prd", section_heading="Huge Section", tool_context=ctx
        )
        self.assertEqual(blocked["status"], "error")
        self.assertEqual(blocked["error_code"], "READ_LIMIT_EXCEEDED")
        self.assertEqual(ctx.state["section_read_counts"]["prd"], MAX_SECTION_READS)

        ingest_document(
            doc_role="prd", raw_text="## v2 Scope\nUpdated.\n", tool_context=ctx
        )
        after_reset = read_doc_section(
            doc_role="prd", section_heading="v2 Scope", tool_context=ctx
        )
        self.assertEqual(after_reset["status"], "success")
        self.assertEqual(ctx.state["section_read_counts"]["prd"], 1)

    def test_dogfood_real_specalign_prd_and_tdd_ingestion(self) -> None:
        """Smoke-test ingesting our own SpecAlign docs/PRD.md and docs/TDD.md."""
        repo_root = Path(__file__).resolve().parent.parent
        prd_path = repo_root / "docs" / "PRD.md"
        tdd_path = repo_root / "docs" / "TDD.md"
        self.assertTrue(prd_path.is_file())
        self.assertTrue(tdd_path.is_file())

        ctx = FakeToolContext()
        r_prd = ingest_document(
            doc_role="prd", file_path=str(prd_path), tool_context=ctx
        )
        r_tdd = ingest_document(
            doc_role="tdd", file_path=str(tdd_path), tool_context=ctx
        )
        self.assertEqual(r_prd["status"], "success")
        self.assertEqual(r_tdd["status"], "success")
        self.assertGreaterEqual(r_prd["section_count"], 8)
        self.assertGreaterEqual(r_tdd["section_count"], 8)


if __name__ == "__main__":
    unittest.main()
