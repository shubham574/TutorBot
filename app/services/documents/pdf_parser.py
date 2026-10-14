"""PDF parser service for extracting text and structure."""
import io
from typing import List, Tuple
import pypdf
from app.config.logging_config import logger


class PDFParserError(Exception):
    """Raised when PDF parsing fails."""
    pass


def extract_text_from_pdf(pdf_bytes: bytes) -> Tuple[str, List[Tuple[int, str]]]:
    """
    Extracts text from raw PDF bytes.

    Args:
        pdf_bytes: Raw bytes of the uploaded PDF file.

    Returns:
        Tuple containing:
        - combined_text: Full extracted string across all pages.
        - pages: List of tuples (page_number_1_indexed, page_text).

    Raises:
        PDFParserError: If the PDF cannot be opened or is password encrypted.
    """
    if not pdf_bytes:
        raise PDFParserError("Empty PDF file bytes provided.")

    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    except Exception as e:
        logger.error("Failed to read PDF file", error=str(e))
        raise PDFParserError(f"Could not read PDF file: {str(e)}") from e

    if reader.is_encrypted:
        raise PDFParserError("The uploaded PDF file is password protected.")

    pages_data: List[Tuple[int, str]] = []
    combined_parts: List[str] = []

    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        page_text = page.extract_text() or ""
        cleaned_text = page_text.strip()
        pages_data.append((page_num, cleaned_text))
        if cleaned_text:
            combined_parts.append(f"--- Page {page_num} ---\n{cleaned_text}")

    full_text = "\n\n".join(combined_parts)
    logger.info(
        "Extracted text from PDF",
        total_pages=len(reader.pages),
        total_characters=len(full_text),
    )
    return full_text, pages_data
