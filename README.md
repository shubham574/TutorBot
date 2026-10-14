# TutorBot 🎓
> Agentic Personal-Tutor WhatsApp Bot for Students

TutorBot is a proactive, intelligent personal-tutor WhatsApp bot built with FastAPI, LangGraph, PostgreSQL (pgvector), Redis, and ARQ.

---

## 🏗️ Architecture

```text
Meta WhatsApp Cloud API
        │ (Webhook POST with HMAC-SHA256 signature)
        ▼
   FastAPI Webhook (/api/v1/webhook)
   ├── 1. Verify X-Hub-Signature-256 header (HMAC-SHA256)
   ├── 2. Fast O(1) deduplication by wamid (Redis)
   ├── 3. Respond with HTTP 200 OK (<200ms)
        │
        ▼ (Enqueue job)
    Redis Queue
        │
        ▼ (Dequeue job)
    ARQ Worker (process_whatsapp_message)
   ├── 1. Database-level deduplication (whatsapp_messages_log)
   ├── 2. Get or create student profile
   ├── 3. LangGraph Workflow (router -> syllabus / tutor / quiz / planner)
   └── 4. Outbound WhatsApp delivery (DRY_RUN mode supported)
```

---

## 🚀 Quickstart

### 1. Prerequisites
- Python 3.11+
- Redis (running locally or via Docker)
- PostgreSQL 16 with pgvector (via Docker or local install)

### 2. Setup Environment
```bash
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate   # On Windows
# source .venv/bin/activate # On Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### 3. Start Infrastructure (Docker)
```bash
docker compose up -d postgres redis
```

### 4. Run Tests
```bash
pytest -v
```

### 5. Run the FastAPI Application
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Run the ARQ Background Worker
```bash
arq app.workers.arq_worker.WorkerSettings
```

---

## 🔒 Security & Privacy
- **Signature Verification**: Every incoming webhook is checked against `WHATSAPP_APP_SECRET` using constant-time HMAC-SHA256 comparison.
- **PII Redaction**: Phone numbers are automatically masked in application logs (`+91*****3210`).
- **DRY_RUN Mode**: Outbound messages are logged to console without calling Meta API when `DRY_RUN=true`.
- **Formatting Guardrails**: Automatic 4096-character message splitting and LaTeX math conversion for clean WhatsApp rendering.

---

## 📋 Roadmap & Phases
- [x] **Phase 1: Webhook + Queue + Echo Bot** (Signature verification, Redis & DB deduplication, ARQ worker, DRY_RUN mode, 28 tests passing).
- [x] **Phase 2: Syllabus Ingestion** (Parse PDF/image OCR -> LLM-extract structured topic tree in `syllabus_nodes`, WhatsApp interactive outline confirmation, 38 tests passing).
- [x] **Phase 3: Content Ingestion + RAG Tutor** (Structure-aware chunking, hybrid search, citations, 3 answer modes: Grounded, General Knowledge, Decline/Clarify, 51 tests passing).
- [ ] **Phase 4: Quiz Agent** (Interactive WhatsApp reply buttons, MCQ verifier, FSRS mastery updates).
- [ ] **Phase 5: Sample Papers & Grading** (Exam blueprints, PDF export, handwritten vision grading, SymPy math solver).
- [ ] **Phase 6: Proactive Planner & Voice** (FSRS spaced-repetition nudges, quiet hours, audio notes, progress tracking).
- [ ] **Phase 7: Evals in CI** (Should-decline set, groundedness evals, question-key audit).
