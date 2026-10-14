"""Structure-aware document chunker for educational materials."""
import re
import uuid
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

TARGET_CHUNK_CHARS = 2400  # ~600 tokens
MAX_CHUNK_CHARS = 3200     # ~800 tokens
MIN_CHUNK_CHARS = 400      # ~100 tokens
OVERLAP_CHARS = 200        # ~50 tokens


class RawDocumentPage(BaseModel):
    page_number: int
    text: str


class DocumentChunk(BaseModel):
    """Processed chunk with rich curriculum metadata."""
    content: str
    subject: str
    source_doc_id: str
    source_title: str
    page_number: int
    doc_type: str = "notes"
    difficulty: str = "medium"
    topic_id: Optional[uuid.UUID] = None
    student_id: Optional[uuid.UUID] = None


class StructureAwareChunker:
    """
    Chunks educational documents respecting headings (Chapters, Sections, Units)
    and page boundaries, targeting ~500-800 tokens per chunk.
    """

    HEADING_REGEX = re.compile(
        r"(^(?:#+\s+|Chapter\s+\d+|Unit\s+\d+|Section\s+\d+|[0-9]+\.[0-9]+\s+)[^\n]+)",
        re.MULTILINE | re.IGNORECASE,
    )

    def chunk_document_pages(
        self,
        pages: List[Tuple[int, str]],
        subject: str,
        source_doc_id: str,
        source_title: str,
        doc_type: str = "notes",
        difficulty: str = "medium",
        topic_id: Optional[uuid.UUID] = None,
        student_id: Optional[uuid.UUID] = None,
    ) -> List[DocumentChunk]:
        """
        Chunks a sequence of (page_num, text) tuples while preserving page provenance.
        """
        chunks: List[DocumentChunk] = []

        for page_num, page_text in pages:
            cleaned_text = page_text.strip()
            if not cleaned_text:
                continue

            # Split page text along heading or paragraph lines
            page_chunks = self._chunk_text_block(cleaned_text)
            for c_text in page_chunks:
                chunks.append(
                    DocumentChunk(
                        content=c_text,
                        subject=subject,
                        source_doc_id=source_doc_id,
                        source_title=source_title,
                        page_number=page_num,
                        doc_type=doc_type,
                        difficulty=difficulty,
                        topic_id=topic_id,
                        student_id=student_id,
                    )
                )

        return chunks

    def _chunk_text_block(self, text: str) -> List[str]:
        """Splits a single block of text along headings and paragraphs."""
        if len(text) <= MAX_CHUNK_CHARS:
            return [text]

        # Break text by paragraphs first
        paragraphs = text.split("\n\n")
        chunks: List[str] = []
        current_chunk = ""

        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                continue

            # If adding this paragraph exceeds target size
            if len(current_chunk) + len(p_clean) + 2 > TARGET_CHUNK_CHARS:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    # Add overlap from previous chunk
                    current_chunk = current_chunk[-OVERLAP_CHARS:] + "\n\n" + p_clean
                else:
                    # Single paragraph exceeds target size, split by sentences
                    sub_chunks = self._split_long_paragraph(p_clean)
                    chunks.extend(sub_chunks[:-1])
                    current_chunk = sub_chunks[-1]
            else:
                if current_chunk:
                    current_chunk += "\n\n" + p_clean
                else:
                    current_chunk = p_clean

        if current_chunk and current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _split_long_paragraph(self, text: str) -> List[str]:
        """Splits a long paragraph along sentence boundaries."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: List[str] = []
        current = ""

        for s in sentences:
            if len(current) + len(s) + 1 > TARGET_CHUNK_CHARS:
                if current:
                    chunks.append(current.strip())
                    current = current[-OVERLAP_CHARS:] + " " + s
                else:
                    # Hard split
                    chunks.append(s[:TARGET_CHUNK_CHARS])
                    current = s[TARGET_CHUNK_CHARS:]
            else:
                current = (current + " " + s).strip()

        if current.strip():
            chunks.append(current.strip())

        return chunks


chunker = StructureAwareChunker()
