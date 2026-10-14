"""PDF Question Paper generation using ReportLab."""
import io
from typing import Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from app.config.logging_config import logger
from app.services.exam.schemas import ExamBlueprint


class ExamPDFGenerator:
    """Generates formatted, printable examination question paper PDFs."""

    def generate_exam_pdf(self, blueprint: ExamBlueprint) -> bytes:
        """
        Renders an ExamBlueprint into a structured PDF document.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=45,
            leftMargin=45,
            topMargin=45,
            bottomMargin=45,
        )

        styles = getSampleStyleSheet()

        # Custom Styles
        title_style = ParagraphStyle(
            "ExamTitle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            alignment=1,  # Center
            textColor=colors.HexColor("#1A237E"),
            fontName="Helvetica-Bold",
        )
        subtitle_style = ParagraphStyle(
            "ExamSubtitle",
            parent=styles["Normal"],
            fontSize=11,
            leading=15,
            alignment=1,  # Center
            textColor=colors.HexColor("#37474F"),
            fontName="Helvetica-Bold",
        )
        meta_style = ParagraphStyle(
            "ExamMeta",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            fontName="Helvetica-Bold",
        )
        instruction_style = ParagraphStyle(
            "ExamInstruction",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#424242"),
        )
        section_style = ParagraphStyle(
            "ExamSection",
            parent=styles["Heading2"],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#0D47A1"),
            fontName="Helvetica-Bold",
        )
        question_style = ParagraphStyle(
            "ExamQuestion",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.black,
        )
        marks_style = ParagraphStyle(
            "ExamMarks",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=14,
            alignment=2,  # Right
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#B71C1C"),
        )

        elements = []

        # 1. Header & Title
        elements.append(Paragraph(blueprint.title.upper(), title_style))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(f"SUBJECT: {blueprint.subject.upper()} | {blueprint.target_exam.upper()}", subtitle_style))
        elements.append(Spacer(1, 10))

        # 2. Time & Max Marks Table
        meta_table_data = [
            [
                Paragraph(f"Time Allowed: {blueprint.duration_minutes // 60} Hours", meta_style),
                Paragraph(f"Maximum Marks: {int(blueprint.total_marks)}", ParagraphStyle("RightMeta", parent=meta_style, alignment=2)),
            ]
        ]
        meta_table = Table(meta_table_data, colWidths=[260, 260])
        meta_table.setStyle(TableStyle([
            ("LINEABOVE", (0, 0), (-1, -1), 1.5, colors.HexColor("#1A237E")),
            ("LINEBELOW", (0, 0), (-1, -1), 1.5, colors.HexColor("#1A237E")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 10))

        # 3. General Instructions
        elements.append(Paragraph("<b>General Instructions:</b>", ParagraphStyle("InstHeading", parent=instruction_style, fontName="Helvetica-Bold")))
        for idx, inst in enumerate(blueprint.instructions, 1):
            elements.append(Paragraph(f"{idx}. {inst}", instruction_style))
        elements.append(Spacer(1, 12))
        elements.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CFD8DC"), spaceAfter=12))

        # 4. Sections & Questions
        for section in blueprint.sections:
            elements.append(Paragraph(f"{section.section_name.upper()}", section_style))
            elements.append(Paragraph(f"<i>{section.instructions}</i>", instruction_style))
            elements.append(Spacer(1, 8))

            for q in section.questions:
                # Question Row with Text on left, Marks on right
                q_text = f"<b>Q{q.question_num}.</b> {q.question_text}"
                marks_text = f"[{int(q.marks) if q.marks.is_integer() else q.marks} Marks]"
                q_row_data = [
                    [Paragraph(q_text, question_style), Paragraph(marks_text, marks_style)]
                ]
                q_table = Table(q_row_data, colWidths=[440, 80])
                q_table.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                elements.append(q_table)

            elements.append(Spacer(1, 10))

        # Build PDF
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        logger.info(
            "Generated exam question paper PDF",
            title=blueprint.title,
            size_bytes=len(pdf_bytes),
            sections_count=len(blueprint.sections),
        )
        return pdf_bytes


exam_pdf_generator = ExamPDFGenerator()
