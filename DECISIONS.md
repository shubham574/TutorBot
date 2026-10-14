# Architecture Decision Records (DECISIONS.md)

This document tracks all significant architectural and engineering decisions for TutorBot.

---

## ADR 001: Technology Stack and Asynchronous Worker Architecture
- **Date**: 2026-10-14
- **Status**: Accepted
- **Context**:
  WhatsApp Cloud API mandates webhook endpoints to respond with `200 OK` within a few seconds (ideally <1-2s) to prevent automatic retries and webhook throttling. LLM agent workflows, syllabus parsing, and RAG lookups take significantly longer (several seconds).
- **Decision**:
  Adopt an asynchronous architecture:
  1. FastAPI handles incoming webhook `POST` requests.
  2. It validates the `X-Hub-Signature-256` HMAC signature.
  3. It verifies message uniqueness using WhatsApp Message ID (`wamid`) against Redis/DB.
  4. It enqueues the normalized message payload into Redis via `ARQ` (async Redis queue for Python).
  5. It returns HTTP `200 OK` immediately.
  6. ARQ workers dequeue messages and execute the LangGraph agent graph.
- **Consequences**:
  - Webhook SLAs are reliably met.
  - Retried webhooks from Meta are deduplicated safely.
  - Worker load can be scaled independently from API ingress.

---

## ADR 002: WhatsApp Operational Constraints & Guardrails
- **Date**: 2026-10-14
- **Status**: Accepted
- **Context**:
  Meta WhatsApp Cloud API enforces strict operational rules:
  - 4096-character limit per text message.
  - 24-hour customer service window: only approved template messages can be sent outside the 24-hour window from the student's last message.
  - Markdown limitations: WhatsApp does not support LaTeX math blocks (`$$...$$` or `\(...\)`).
- **Decision**:
  - Implement a dedicated outbound formatting service (`app/services/whatsapp/formatter.py`):
    - Automatically chunks messages exceeding 4096 characters along paragraph/sentence boundaries.
    - Strips or converts unsupported markdown syntax.
  - Enforce a 24-hour window check before sending proactive nudges or revisions.
  - Implement a `DRY_RUN` mode (`DRY_RUN=true`) that logs outbound WhatsApp messages without hitting Meta's API, enabling safe testing and development.
- **Consequences**:
  - Zero dropped messages due to payload length.
  - Compliance with Meta's messaging policies.

---

## ADR 003: Database Engine and Vector Storage
- **Date**: 2026-10-14
- **Status**: Accepted
- **Context**:
  We need relational data (students, syllabus tree, attempts, mastery), vector similarity search for RAG chunks, and full-text search (BM25/FTS) for hybrid search.
- **Decision**:
  Use **PostgreSQL 16** with the **pgvector** extension.
  - Hybrid search will combine PostgreSQL vector similarity (`<=>` cosine distance or `<#>` inner product) and `tsvector` / `websearch_to_tsquery` using Reciprocal Rank Fusion (RRF).
  - Keeps operational complexity minimal by avoiding separate vector databases (e.g., Pinecone, Qdrant) and search clusters.
- **Consequences**:
  - Single ACID datastore for transactions, agent checkpoints, and embeddings.
  - Simplified backups, migrations (via Alembic), and point-in-time recovery.

---

## ADR 004: Student Spaced Repetition Algorithm
- **Date**: 2026-10-14
- **Status**: Accepted
- **Context**:
  The bot needs an algorithm to schedule topic revisions and quiz repetitions.
- **Decision**:
  Use **FSRS (Free Spaced Repetition Scheduler)**.
  - FSRS is an open-source, modern spaced repetition algorithm shown to outperform legacy SM-2 by accurately modeling memory retention, stability, and difficulty.
- **Consequences**:
  - Mastery table will track `stability`, `difficulty`, `reps`, `lapses`, `state`, and `next_review`.

---

## ADR 005: Privacy and Data Isolation for Minors
- **Date**: 2026-10-14
- **Status**: Accepted
- **Context**:
  Students using the bot may be minors. Strict privacy, explicit consent, quiet hours, and compliance with data protection principles are required.
- **Decision**:
  - Explicit onboarding consent step before storing syllabus or learning data.
  - Support user data deletion via command (`/delete my data`).
  - No plain-text student phone numbers in application logs: all phone numbers are masked in logs (e.g. `+91*****1234`).
  - Per-student logical data isolation across all database queries via indexed `student_id`.
  - Respect student quiet hours (default 22:00 to 07:00) during proactive scheduling.
- **Consequences**:
  - Safer environment for students.
  - Compliance readiness for privacy audits.

---

## ADR 006: Proactive Nudge Compliance, Quiet Hours, and Meta 24-Hour WhatsApp Policy
- **Date**: 2026-10-15
- **Status**: Accepted
- **Context**:
  Proactive notifications (daily study goals, FSRS spaced-repetition revision prompts) must never disturb students during rest hours, spam them, or violate Meta's WhatsApp Business Messaging Policy.
- **Decision**:
  - **Adaptive Study Planner**: Distributes syllabus topics across available study days up to the target exam, automatically reserving the final 15% of the timeline as a consolidation and practice exam buffer.
  - **Deterministic Compliance Service**: Before dispatching any proactive notification, the bot enforces 4 strict gates:
    1. **Consent & Opt-Out**: Verified `student.is_active == True` (honoring student `/opt-out` and `/opt-in` commands).
    2. **Timezone Quiet Hours**: Verified outside `22:00` to `07:00` student local time using IANA timezones (`ZoneInfo` backed by `tzdata`).
    3. **Daily Frequency Cap**: Enforced maximum 1 proactive nudge per student per calendar day tracked via outbound message logs.
    4. **Meta 24-Hour Session Window**: If within 24 hours of student's last message, send rich interactive buttons; if outside 24 hours, fall back to approved business notification templates.
  - **Academic Progress Dashboard**: Computes real-time syllabus coverage, mastered topics (score >= 0.70), and quiz accuracy with Unicode progress bars (`[████████░░░░] 67%`).
- **Consequences**:
  - Deterministic safety against student fatigue and notification spam.
  - Zero account ban risk from Meta policy violations.
