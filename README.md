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
- MinIO (S3-compatible storage for documents)

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
docker compose up -d postgres redis minio
```

### 4. Run Tests & CI Evaluations
```bash
# Run full unit and integration test suite
pytest -v

# Run CI safety, groundedness, and question audit harness
python -m evals.runner
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
- **Continuous CI Evals**: Automated verification of should-decline safety sets, RAG groundedness with exact citations, and question-key verifier audits.
- **Data Deletion**: Complete student data removal via `/delete my data` command (database records, MinIO files, message logs).
- **Data Retention**: Configurable automatic purge of inactive students with warning notifications.
- **Tenant Isolation**: Repository-layer enforcement of student_id scoping prevents cross-student data access.
- **Prompt Injection Protection**: Retrieved content wrapped in safety delimiters, injection patterns detected and sanitized at ingestion.
- **Security Scanning**: CI includes pip-audit (vulnerabilities), bandit (static analysis), gitleaks (secrets), Dependabot (dependency updates).

---

## ⚖️ Legal & Compliance Notice

**IMPORTANT: Parental Consent for Minors Under India's DPDP Act**

> **This software does NOT provide a compliant "verifiable parental consent" mechanism under India's Digital Personal Data Protection Act, 2023 (DPDP Act).**
>
> A chat-based "I agree" button or `/opt-in` command is **not sufficient** for valid parental consent under DPDP Act Section 9, which requires:
> - Verifiable consent (considering available technology)
> - Notice to parent/guardian before processing child's data
> - Purpose limitation and data minimization
> - Right to withdraw consent
>
> **TODO for Legal Review** (must be completed before production use with minors):
> - [ ] Implement age-gating at onboarding (require date of birth)
> - [ ] Integrate verifiable parental consent flow (e.g., DigiLocker, Aadhaar e-KYC, or government-approved method)
> - [ ] Maintain consent audit logs with timestamps and verification method
> - [ ] Implement child-specific data processing agreements
> - [ ] Add Data Protection Impact Assessment (DPIA) for high-risk processing
> - [ ] Establish grievance redressal mechanism per DPDP Act
> - [ ] Review cross-border data transfer restrictions (MinIO/Redis/PostgreSQL hosting locations)
> - [ ] Document lawful basis for each data processing activity
> - [ ] Implement data retention schedule aligned with educational record requirements
> - [ ] Appoint Data Protection Officer if required by scale
>
> **Do not deploy to production with minor users until legal review is complete.**

---

## 📋 Roadmap & Phases
- [x] **Phase 1: Webhook + Queue + Echo Bot** (Signature verification, Redis & DB deduplication, ARQ worker, DRY_RUN mode, 28 tests passing).
- [x] **Phase 2: Syllabus Ingestion** (Parse PDF/image OCR -> LLM-extract structured topic tree in `syllabus_nodes`, WhatsApp interactive outline confirmation, 38 tests passing).
- [x] **Phase 3: Content Ingestion + RAG Tutor** (Structure-aware chunking, hybrid search, citations, 3 answer modes: Grounded, General Knowledge, Decline/Clarify, 51 tests passing).
- [x] **Phase 4: Quiz Agent** (Interactive WhatsApp reply buttons, autonomous dual-pass verifier, FSRS mastery engine, 60 tests passing).
- [x] **Phase 5: Sample Papers & Grading** (Exam blueprints, ReportLab PDF generator, SymPy symbolic math verifier, vision grading, 70 tests passing).
- [x] **Phase 6: Proactive Planner & Voice** (FSRS spaced-repetition nudges, quiet hours, audio notes, progress tracking, 85 tests passing).
- [x] **Phase 7: Evals in CI** (Should-decline safety set, RAG groundedness & citations, question-key audit, GitHub Actions CI workflow, 91 tests passing).
- [x] **Phase 8: Security Hardening (Phase 1)** (Credentials in .env, Redis password, tenant isolation, data deletion/retention, prompt injection protection, security scanning in CI, 117 tests passing).

---

## 📚 Documentation
- **Architecture Decisions**: See `DECISIONS.md` for ADR log
- **API Docs**: Available at `/docs` when running the FastAPI app
- **Evaluation Harness**: See `evals/` directory for safety and quality test suites

---

## 🤝 Contributing
See `CONTRIBUTING.md` for development guidelines, code style, and PR process.