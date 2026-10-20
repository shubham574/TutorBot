"""Hybrid search retriever combining vector similarity, keyword matching, and RRF."""
import enum
import uuid
from typing import List, Optional, Tuple
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.logging_config import logger
from app.models.content import ContentChunk
from app.services.llm.embeddings import embedding_service, cosine_similarity
from app.services.llm.nvidia import llm_client
from app.security.injection import (
    injection_detector,
    sanitize_content,
    format_context_for_prompt,
    wrap_retrieved_content,
)


class AnswerMode(str, enum.Enum):
    """The 3 transparent answer modes required by TutorBot."""
    GROUNDED = "GROUNDED"
    GENERAL_KNOWLEDGE = "GENERAL_KNOWLEDGE"
    DECLINE_OR_CLARIFY = "DECLINE_OR_CLARIFY"


class RetrievedChunk(BaseModel):
    chunk_id: uuid.UUID
    content: str
    source_title: str
    page_number: int
    subject: str
    score: float
    doc_type: str
    injection_risk: float = 0.0  # Risk score for prompt injection


class RetrievalResult(BaseModel):
    mode: AnswerMode
    confidence: float
    rewritten_query: str
    chunks: List[RetrievedChunk]
    injection_warnings: List[str] = []  # Warnings about detected injection attempts


class HybridRetriever:
    """Executes query rewrite, metadata filtering, hybrid search, and RRF fusion."""

    async def rewrite_query(self, raw_query: str) -> str:
        """Removes conversational filler and reformulates the student's question into clear search keywords."""
        cleaned = raw_query.strip()
        # Fast path for concise queries
        if len(cleaned.split()) <= 4 and not any(k in cleaned.lower() for k in ["hey", "can you", "please"]):
            return cleaned

        try:
            prompt = (
                f"Rewrite this student query into a concise academic search query (max 6 words):\n"
                f"Student: '{cleaned}'\n"
                f"Output search keywords only:"
            )
            rewritten = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=25,
                temperature=0.0,
            )
            return rewritten.strip().replace('"', '') or cleaned
        except Exception:
            return cleaned

    async def retrieve(
        self,
        query: str,
        student_id: Optional[uuid.UUID],
        session: AsyncSession,
        subject_filter: Optional[str] = None,
        topic_id_filter: Optional[uuid.UUID] = None,
        top_k: int = 4,
    ) -> RetrievalResult:
        """
        Executes query rewrite, generates query embedding, queries content_chunks,
        runs RRF fusion, and computes confidence score.
        """
        rewritten = await self.rewrite_query(query)
        query_embedding = await embedding_service.get_embedding(rewritten)

        # 1. Fetch candidate chunks applying metadata filter:
        # Include either student's private uploads OR shared global corpus (student_id IS NULL)
        stmt = select(ContentChunk).where(
            or_(
                ContentChunk.student_id == student_id,
                ContentChunk.student_id.is_(None),
            )
        )
        if subject_filter:
            stmt = stmt.where(ContentChunk.subject.ilike(f"%{subject_filter}%"))
        if topic_id_filter:
            stmt = stmt.where(ContentChunk.topic_id == topic_id_filter)

        res = await session.execute(stmt)
        candidates = res.scalars().all()

        if not candidates:
            logger.info("No candidate chunks found in database", student_id=str(student_id))
            return RetrievalResult(
                mode=AnswerMode.DECLINE_OR_CLARIFY,
                confidence=0.0,
                rewritten_query=rewritten,
                chunks=[],
            )

        # 2. Score candidates
        query_terms = set(rewritten.lower().split())
        dense_scores: List[Tuple[ContentChunk, float]] = []
        sparse_scores: List[Tuple[ContentChunk, float]] = []

        for chunk in candidates:
            # Dense score: Cosine similarity
            if chunk.embedding:
                dense_sim = cosine_similarity(query_embedding, chunk.embedding)
            else:
                dense_sim = 0.0
            dense_scores.append((chunk, dense_sim))

            # Sparse score: Keyword frequency
            chunk_words = set(chunk.content.lower().split())
            overlap = len(query_terms.intersection(chunk_words))
            sparse_score = overlap / max(len(query_terms), 1)
            sparse_scores.append((chunk, sparse_score))

        # Sort for ranks
        dense_scores.sort(key=lambda x: x[1], reverse=True)
        sparse_scores.sort(key=lambda x: x[1], reverse=True)

        dense_rank = {chunk.id: idx for idx, (chunk, _) in enumerate(dense_scores)}
        sparse_rank = {chunk.id: idx for idx, (chunk, _) in enumerate(sparse_scores)}

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF = 1 / (60 + dense_rank) + 1 / (60 + sparse_rank)
        rrf_scores: List[Tuple[ContentChunk, float]] = []
        for chunk, dense_sim in dense_scores:
            d_rank = dense_rank[chunk.id]
            s_rank = sparse_rank[chunk.id]
            rrf_score = (1.0 / (60.0 + d_rank)) + (1.0 / (60.0 + s_rank))
            # Combine RRF with raw similarity
            composite_score = (rrf_score * 30.0) + (dense_sim * 0.5)
            rrf_scores.append((chunk, composite_score))

        rrf_scores.sort(key=lambda x: x[1], reverse=True)
        top_matches = rrf_scores[:top_k]

        # Top confidence normalized to [0.0, 1.0]
        top_score = top_matches[0][1] if top_matches else 0.0
        confidence = min(max(top_score, 0.0), 1.0)

        # 4. Gate Answer Mode based on objective confidence threshold
        if confidence >= 0.65:
            mode = AnswerMode.GROUNDED
        elif confidence >= 0.40:
            mode = AnswerMode.GENERAL_KNOWLEDGE
        else:
            mode = AnswerMode.DECLINE_OR_CLARIFY

        # 5. Process chunks with injection detection and sanitization
        retrieved_chunks = []
        injection_warnings = []

        for c, score in top_matches:
            # Check for injection patterns
            risk_score = injection_detector.get_risk_score(c.content)
            matches = injection_detector.scan(c.content)

            if matches:
                for pattern, matched_text in matches:
                    warning = f"Potential injection in {c.source_title} (p.{c.page_number}): '{matched_text[:50]}...' (pattern: {pattern})"
                    injection_warnings.append(warning)
                    logger.warning("Prompt injection detected in retrieved chunk", chunk_id=str(c.id), pattern=pattern)

            retrieved_chunks.append(
                RetrievedChunk(
                    chunk_id=c.id,
                    content=c.content,  # Original content preserved for reference
                    source_title=c.source_title,
                    page_number=c.page_number,
                    subject=c.subject,
                    score=round(score, 4),
                    doc_type=c.doc_type,
                    injection_risk=risk_score,
                )
            )

        logger.info(
            "Hybrid retrieval completed",
            query=rewritten,
            mode=mode.value,
            confidence=round(confidence, 3),
            chunks_found=len(retrieved_chunks),
            injection_warnings=len(injection_warnings),
        )

        return RetrievalResult(
            mode=mode,
            confidence=round(confidence, 3),
            rewritten_query=rewritten,
            chunks=retrieved_chunks,
            injection_warnings=injection_warnings,
        )

    def format_context_for_llm(self, retrieval_result: RetrievalResult) -> str:
        """
        Formats retrieved chunks into a safe context string for LLM consumption.
        Wraps content in delimiters with explicit safety instructions.
        """
        chunks_data = [
            {
                "content": chunk.content,
                "source_title": chunk.source_title,
                "page_number": chunk.page_number,
            }
            for chunk in retrieval_result.chunks
        ]
        return format_context_for_prompt(chunks_data)


retriever = HybridRetriever()