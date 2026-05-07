"""
Pure function — builds a .docx proposal document from a validated ProposalDocument.
No AI calls. Returns the output_path on success.
"""
from __future__ import annotations

from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from ..schemas import ProposalDocument


def build_proposal_docx(doc_model: ProposalDocument, output_path: str) -> str:
    doc = Document()
    _set_styles(doc)

    # ── Cover page ────────────────────────────────────────────────────────────
    _add_cover(doc, doc_model)
    doc.add_page_break()

    # ── Section 1: Executive Summary ─────────────────────────────────────────
    _add_prose_section(doc, 1, doc_model.executive_summary)

    # ── Section 2: Understanding ──────────────────────────────────────────────
    _add_prose_section(doc, 2, doc_model.understanding)

    # ── Section 3: Approach ───────────────────────────────────────────────────
    _add_prose_section(doc, 3, doc_model.approach)

    # ── Section 4: Phases & Timeline ─────────────────────────────────────────
    _add_phases_section(doc, doc_model)

    # ── Section 5: Pricing Approach ───────────────────────────────────────────
    _add_prose_section(doc, 5, doc_model.pricing_approach)

    # ── Section 6: Open Questions (optional) ─────────────────────────────────
    if doc_model.open_questions:
        _add_open_questions_section(doc, doc_model)

    doc.save(output_path)
    return output_path


# ── Style helpers ─────────────────────────────────────────────────────────────

def _set_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    for h_name, pt_size in [("Heading 1", 14), ("Heading 2", 12)]:
        style = doc.styles[h_name]
        style.font.name = "Calibri"
        style.font.size = Pt(pt_size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)


# ── Cover ─────────────────────────────────────────────────────────────────────

def _add_cover(doc: Document, doc_model: ProposalDocument) -> None:
    for _ in range(4):
        doc.add_paragraph("")

    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_para.add_run("Consulting Engagement Proposal")
    run.bold = True
    run.font.size = Pt(22)
    run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

    if doc_model.client_name:
        client_para = doc.add_paragraph()
        client_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        c_run = client_para.add_run(f"Prepared for: {doc_model.client_name}")
        c_run.font.size = Pt(14)
        c_run.font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    meta_lines = []
    if doc_model.engagement_type:
        meta_lines.append(f"Engagement type: {doc_model.engagement_type}")
    if doc_model.total_duration_estimate:
        meta_lines.append(f"Estimated duration: {doc_model.total_duration_estimate}")

    if meta_lines:
        doc.add_paragraph("")
        for line in meta_lines:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(line)
            r.font.size = Pt(11)
            r.font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    d_run = date_para.add_run(date.today().strftime("%B %d, %Y"))
    d_run.font.size = Pt(11)
    d_run.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)


# ── Prose section ─────────────────────────────────────────────────────────────

def _add_prose_section(doc: Document, number: int, section) -> None:  # noqa: ANN001
    doc.add_heading(f"{number}. {section.title}", level=1)

    for para_text in section.body.split("\n\n"):
        para_text = para_text.strip()
        if para_text:
            doc.add_paragraph(para_text)

    for bullet in section.bullets:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(bullet)


# ── Phases section ────────────────────────────────────────────────────────────

def _add_phases_section(doc: Document, doc_model: ProposalDocument) -> None:
    doc.add_heading("4. Phases & Timeline", level=1)

    for phase in doc_model.phases_timeline:
        doc.add_heading(f"Phase {phase.phase_number}: {phase.phase_name}", level=2)

        dur_para = doc.add_paragraph()
        dur_run = dur_para.add_run(f"Duration: {phase.duration}")
        dur_run.bold = True
        dur_run.font.color.rgb = RGBColor(0x63, 0x66, 0xF1)

        if phase.description:
            doc.add_paragraph(phase.description)

        for deliverable in phase.deliverables:
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(deliverable)


# ── Open questions section ────────────────────────────────────────────────────

def _add_open_questions_section(doc: Document, doc_model: ProposalDocument) -> None:
    section_num = 6
    doc.add_heading(f"{section_num}. Open Questions", level=1)

    intro = doc.add_paragraph(
        "The following questions must be clarified before the engagement can begin. "
        "They arise from areas of the client analysis where information was ambiguous or contradictory."
    )

    for i, oq in enumerate(doc_model.open_questions, 1):
        q_para = doc.add_paragraph(style="List Number")
        q_run = q_para.add_run(oq.question)
        q_run.bold = True

        meta_para = doc.add_paragraph()
        meta_run = meta_para.add_run(
            f"Source ({oq.dimension} · {oq.confidence} confidence): {oq.source_statement}"
        )
        meta_run.italic = True
        meta_run.font.size = Pt(9)
        meta_run.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)
