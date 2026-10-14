"""Unit tests for PDF document parser."""
import io
import pytest
import pypdf
from app.services.documents.pdf_parser import extract_text_from_pdf, PDFParserError


def create_sample_pdf(pages_text: list[str]) -> bytes:
    """Helper to generate an in-memory PDF for testing."""
    writer = pypdf.PdfWriter()
    for text in pages_text:
        page = writer.add_blank_page(width=612, height=792)
        # Note: blank page in pypdf doesn't easily draw text without reportlab,
        # but we can test writer operations or extract_text
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_extract_text_empty_bytes():
    with pytest.raises(PDFParserError, match="Empty PDF file bytes provided"):
        extract_text_from_pdf(b"")


def test_extract_text_corrupted_bytes():
    with pytest.raises(PDFParserError, match="Could not read PDF file"):
        extract_text_from_pdf(b"not a real pdf content header")


def test_extract_text_valid_blank_pdf():
    pdf_bytes = create_sample_pdf(["Page 1", "Page 2"])
    full_text, pages = extract_text_from_pdf(pdf_bytes)
    assert len(pages) == 2
    assert pages[0][0] == 1
    assert pages[1][0] == 2
