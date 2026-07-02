# 🛡️ Data Compliance & Risk Dashboard

> An AI-powered document compliance platform that detects PII, evaluates regulatory risk, and enables secure RAG-based chat — all without exposing raw sensitive data to any external LLM.

---

## Table of Contents

1. [Setup Instructions](#-setup-instructions)
2. [Architecture Overview](#-architecture-overview)
3. [AI/ML Approach](#-aiml-approach)
4. [Challenges Faced](#-challenges-faced)
5. [Future Improvements](#-future-improvements)
6. [Deployment Link](#-working-prototype-deployment-link)

---

## 🔧 Setup Instructions

### Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10+ |
| pip | Latest |
| Google AI Studio API Key | [Get one here](https://aistudio.google.com/app/apikey) |

### 1. Clone the Repository

```bash
git clone https://github.com/snehashish27/compliance-assistant.git
cd compliance-assistant
```

### 2. Create and Activate a Virtual Environment

```bash
# Windows
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** First run will download the EasyOCR English model (~100 MB) automatically.

### 4. Download the spaCy NLP Model

```bash
python -m spacy download en_core_web_sm
```

### 5. Configure Environment Variables

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY="your_google_ai_studio_key_here"
KMP_DUPLICATE_LIB_OK=TRUE
```

> `KMP_DUPLICATE_LIB_OK=TRUE` suppresses a benign Windows OpenMP conflict between FAISS and NumPy.

### 6. Run the Server (Locally)

```bash
uvicorn main:app --reload
```

Open your browser at **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

### 7. Run with Docker (Alternative)

Build the Docker image:
```bash
docker build -t compliance-assistant .
```

Run the container (make sure your `.env` file is present):
```bash
docker run -p 8000:8000 --env-file .env compliance-assistant
```

Open your browser at **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

### Supported File Types

| Format | Parser Used |
|---|---|
| `.pdf` | PyMuPDF (text layer) + EasyOCR (image/scanned fallback) |
| `.txt` | Direct UTF-8 decode |
| `.csv` | Pandas → string layout |

---

## 🏗️ Architecture Overview

Proteccio follows a **privacy-first, layered pipeline** architecture. Raw sensitive data never reaches any external API.

```
┌──────────────────────────────────────────────────────────────────┐
│                        BROWSER (Frontend)                        │
│   Vanilla HTML · CSS · JavaScript · Chart.js                     │
│   Drag-drop upload → Progress UI → Results Dashboard → Chat      │
└────────────────────┬─────────────────────────────────────────────┘
                     │  HTTP (multipart/form-data, JSON)
                     ▼
┌──────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (main.py)                     │
│                                                                  │
│   POST /api/analyze          POST /api/generate-report           │
│   POST /api/chat                                                  │
│                                                                  │
│   In-memory session store (SESSIONS dict, keyed by UUID)         │
└────┬───────────────┬────────────────────┬────────────────────────┘
     │               │                    │
     ▼               ▼                    ▼
┌─────────┐   ┌──────────────┐   ┌────────────────────┐
│ Parser  │   │   Detector   │   │ Compliance Engine  │
│         │   │              │   │                    │
│PyMuPDF  │   │ Regex PII    │   │ Gemini 3.5 Flash   │
│EasyOCR  │   │ spaCy NER    │──▶│ (Report only)      │
│Pandas   │   │ (PERSON/ORG) │   │                    │
└─────────┘   └──────┬───────┘   └────────────────────┘
                     │ Masked Text
                     ▼
              ┌──────────────┐
              │  FAISS Index │  ◀── GeminiEmbeddings
              │  (local RAM) │      (REST v1beta,
              │              │       gemini-embedding-001)
              └──────┬───────┘
                     │ RAG Retrieval
                     ▼
              ┌──────────────┐
              │ Conversational│
              │ Retrieval     │  ◀── Gemini LLM
              │ Chain (Chat)  │      (anonymized context only)
              └──────────────┘
```

### Key Design Principle — Privacy-First

```
Raw Document
     │
     ▼  [Parser]
 Plain Text
     │
     ▼  [Detector]
Masked Text  ──────────────▶  FAISS Index  ──▶  LLM Chat
(PII replaced with           (local, RAM)        (sees only
 [REDACTED_...] tokens)                           masked text)
     │
     ▼
 Aggregate
  Metrics  ──────────────▶  Compliance Report LLM call
(counts only,               (never sees raw content —
 no raw PII)                 only entity counts + risk tier)
```

No raw PII is ever serialized to disk, sent over the network, or included in any LLM prompt.

---

## 🤖 AI/ML Approach

### 1. Document Parsing — Dual-Mode PDF Extraction

- **PyMuPDF** extracts the native text layer from PDF files (fast, lossless).
- **EasyOCR** (CRNN + LSTM OCR model, runs 100% locally, CPU-only) is triggered as a fallback when a page has no text layer (scanned documents, image-only PDFs). The page is rendered to a pixel array and passed through EasyOCR's pipeline.

### 2. PII Detection — Hybrid Regex + NLP

Detection runs in three stages:

#### Stage 1 — Regex Patterns (High Precision)
Deterministic detection of structured PII:

| Entity | Pattern |
|---|---|
| Aadhaar Number | 12-digit with optional spaces/dashes |
| PAN Number | `[A-Z]{5}[0-9]{4}[A-Z]` |
| Email Address | RFC-compliant email regex |
| Phone Number | Indian mobile format (`+91` prefix or 10-digit starting 6-9) |
| Credit Card | 13–16 digit sequence |
| IFSC Code | Bank IFSC format |
| API Key | OpenAI-style `sk-` prefix keys |

#### Stage 2 — Keyword Matching
Flags documents containing confidentiality markers: `confidential`, `proprietary`, `internal use only`, `trade secret`.

#### Stage 3 — spaCy NLP (`en_core_web_sm`) — Targeted
spaCy Named Entity Recognition is applied with strict filters to avoid false positives on technical documents:

- **PERSON entities:** Only redacted if multi-word (e.g., `John Smith`) — single-word "names" like `Dropout` or `NumPy` (which spaCy misclassifies) are ignored.
- **ORG entities:** Only redacted if the entity contains a **corporate suffix** (`Ltd`, `Inc`, `Pvt`, `Foundation`, `Corp`, `Holdings`, etc.) — this prevents project names, ML frameworks, academic institutions, and technical concepts from being flagged.
- A **technical whitelist** of 100+ ML libraries, frameworks, programming languages, and tools (`TensorFlow`, `NumPy`, `AdamW`, `FAISS`, etc.) is always excluded.

### 3. Risk Classification

Rule-based tier assignment from entity counts:

| Tier | Trigger |
|---|---|
| **High Risk** | Aadhaar, PAN, Credit Card, or API Key detected |
| **Medium Risk** | Email, Phone, IFSC, or Confidential keywords |
| **Low Risk** | Only named entities or nothing |

### 4. Vector Indexing — Local FAISS

- The **masked** text is chunked (1000 chars, 100 char overlap) using LangChain's `RecursiveCharacterTextSplitter`.
- Chunks are embedded using **`models/gemini-embedding-001`** via a custom `GeminiEmbeddings` class that calls the Google REST API directly (bypassing `langchain-google-genai`'s outdated v1beta endpoint).
- Embeddings are stored in a **local in-memory FAISS index** (no persistence, no external vector DB).

### 5. Conversational RAG Chat

- Uses LangChain's `ConversationalRetrievalChain` with top-3 chunk retrieval.
- `ConversationBufferMemory` maintains multi-turn context within a session.
- The LLM (**Gemini 3.5 Flash**) only ever sees the anonymized, masked text — raw PII is never in any prompt.

### 6. On-Demand Compliance Report

- Triggered manually via the "⚡ Generate Compliance Report" button (not auto-generated on upload).
- The LLM prompt contains **only aggregate metrics** (entity counts + risk tier) — never raw document content.
- The report is structured around India's **DPDP Act 2023** and **DPDP Rules 2025**, covering compliance observations, security risks, and remediation steps.
- Generated reports are cached per session and can be **downloaded as `.md`** files.

---

## 🧱 Challenges Faced

### 1. Embedding Model Deprecation
`models/embedding-001` was deprecated and removed from Google's API. `models/text-embedding-004` (the documented replacement) was unavailable on the v1beta endpoint used by `langchain-google-genai` v0.2.6 and `google-generativeai` v0.7.2. **Solution:** Wrote a custom `GeminiEmbeddings` class that calls the REST API directly, then used the `ModelService.ListModels` endpoint to discover which embedding model is actually accessible for the configured API key (`gemini-embedding-001`).

### 2. spaCy Over-Redaction on Technical Documents
`en_core_web_sm` aggressively misclassifies ML library names (`NumPy`, `AdamW`), technical concepts (`DSA`, `CNN`, `MLP`), GitHub links, and project names as `ORG` or `PERSON` entities. **Solution:** Replaced blanket NER masking with a three-layer filter: technical whitelist, URL detection, and a corporate-suffix requirement for ORG entities — reducing false positives by ~80% on resume/technical documents.

### 3. LangChain API Version Drift
`ConversationalRetrievalChain` moved from the deprecated `chain({"question": ...})` dict-call pattern to `chain.invoke(...)` in LangChain 0.1+. The old pattern returned a silent error rather than raising. **Solution:** Updated all chain invocations to `.invoke()` with a fallback between `"answer"` and `"result"` output keys.

### 4. OpenMP Runtime Conflict on Windows
FAISS and NumPy both bundle their own OpenMP runtime DLLs (`libomp140.x86_64.dll` vs `libiomp5md.dll`), causing a process-level conflict on Windows. **Solution:** Set `KMP_DUPLICATE_LIB_OK=TRUE` in `.env`, which is loaded at startup via `python-dotenv`.

### 5. EasyOCR Cold Start Latency
EasyOCR initializes a CRNN model on first import (~3–5 seconds), blocking server startup. **Solution:** Module-level initialization in `document_parser.py` so the cost is paid once at startup, not per-request.

---

## 🚀 Future Improvements

| Priority | Improvement | Description |
|---|---|---|
| 🔴 High | **Persistent Sessions** | Replace the in-memory `SESSIONS` dict with Redis or a lightweight SQLite store so sessions survive server restarts |
| 🔴 High | **Streaming Chat Responses** | Use Server-Sent Events (SSE) for token-by-token LLM streaming in the chat UI |
| 🟡 Medium | **Multi-language PII Detection** | Add Hindi/regional-language PII patterns (e.g., Aadhaar in Devanagari) and swap to `en_core_web_trf` (transformer-based spaCy) for better NER precision |
| 🟡 Medium | **DPDP Consent Mapper** | Automatically map detected PII categories to DPDP Act 2023 data principal consent requirements |
| 🟡 Medium | **Batch Processing & Queue** | Support large-volume document uploads via Celery/RabbitMQ async task queue |
| 🟢 Low | **PDF Report Export** | Add server-side report rendering to PDF (e.g., WeasyPrint) in addition to the current Markdown download |
| 🟢 Low | **Role-Based Access Control** | Add JWT-based auth so only authorized users can access session data |
| 🟢 Low | **Audit Trail Dashboard** | Surface the existing `audit.log` entries in a searchable UI panel |
| 🟢 Low | **Docker Compose Deployment** | Add a Compose file for multi-container deployment (e.g. adding Redis for sessions) |

---

## 🌐 Working Prototype Deployment Link

> **Local Development Server**
>
> This prototype runs locally. Start the server with:
> ```bash
> uvicorn main:app --reload
> ```
> Then open: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

> [!NOTE]
> A public deployment link will be added here once the application is hosted. The included `Dockerfile` can be used to deploy to any container platform (Railway, Render, Google Cloud Run, etc.).

---

## 📁 Project Structure

```
compliance-assistant/
├── main.py                 # FastAPI app — API routes & session management
├── document_parser.py      # PDF (PyMuPDF + EasyOCR), TXT, CSV extraction
├── detector.py             # Regex + spaCy PII detection & masking
├── compliance_engine.py    # FAISS RAG chain + Gemini report generation
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container build file
├── .env                    # API keys (not committed to git)
├── audit.log               # Auto-generated audit trail
└── static/
    ├── index.html          # Single-page dashboard UI
    ├── styles.css          # Dark-mode CSS design system
    └── script.js           # Frontend logic (upload, chat, download)
```

---

## 📜 Compliance Framework Reference

This tool's report generation is aligned with:

- **Digital Personal Data Protection (DPDP) Act, 2023** — India's primary data privacy legislation
- **DPDP Rules, 2025** — Implementing rules covering Data Fiduciary obligations, consent, and processing standards
- **ISO/IEC 27001** principles for information security management (referenced in remediation guidance)

---

*Built with FastAPI · spaCy · FAISS · LangChain · Google Gemini · PyMuPDF · EasyOCR*
