"""Image parser and OCR service using Vision LLMs."""
import io
from typing import Optional
from PIL import Image
from app.config.logging_config import logger
from app.services.llm.nvidia import llm_client

MAX_IMAGE_DIMENSION = 2048


class ImageParserError(Exception):
    """Raised when image processing or OCR fails."""
    pass


def validate_and_optimize_image(image_bytes: bytes) -> bytes:
    """Validates image integrity and resizes down if larger than MAX_IMAGE_DIMENSION."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
        # Re-open after verify()
        img = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise ImageParserError(f"Invalid or corrupted image: {str(e)}") from e

    # Check dimensions and resize if needed
    width, height = img.size
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        ratio = min(MAX_IMAGE_DIMENSION / width, MAX_IMAGE_DIMENSION / height)
        new_size = (int(width * ratio), int(height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        out_buf = io.BytesIO()
        img_format = img.format or "JPEG"
        img.save(out_buf, format=img_format, quality=85)
        return out_buf.getvalue()

    return image_bytes


async def extract_text_from_image_ocr(
    image_bytes: bytes,
    prompt: Optional[str] = None,
    mime_type: str = "image/jpeg",
) -> str:
    """
    Extracts syllabus text and structure from an uploaded photo of a syllabus or notes.
    """
    optimized_bytes = validate_and_optimize_image(image_bytes)

    default_prompt = (
        "Extract all readable syllabus text, units, topics, subtopics, exam marks, "
        "and dates from this image. Transcribe the hierarchy clearly."
    )

    extracted_text = await llm_client.extract_from_image(
        image_bytes=optimized_bytes,
        prompt=prompt or default_prompt,
        mime_type=mime_type,
    )
    logger.info("Extracted text from image via Vision LLM", char_count=len(extracted_text))
    return extracted_text
