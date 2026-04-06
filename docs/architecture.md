# CyberRAG-IDS — System Architecture

## Overview

CyberRAG-IDS is a full-stack cybersecurity platform combining:
- **LSTM-based Intrusion Detection** (ML inference on network flows)
- **RAG-powered Cyber Advisor** (LangChain + ChromaDB + local LLM)
- **Real-time monitoring** (WebSocket live stream)
- **Batch analysis** (CSV/PCAP upload)

All inference runs **locally** — no data leaves your machine.

---

## Architecture Diagram
┌─────────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                                │
│                    Next.js 15 (port 3000)                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐     │
│  │Dashboard │  │ Upload   │  │  Chat    │  │    Reports       │     │
│  │ Charts   │  │ CSV/PCAP │  │   RAG    │  │  List/View/Del   │     │
│  │ Feed     │  │ Results  │  │Advisor   │  │                  │     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘     │
│       │             │             │                 │               │
│  WebSocket      REST API       REST API         REST API            │
└───────┼──────────────┼──────────────┼──────────────────┼────────────┘
        │              │              │                  │
        ▼              ▼              ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (port 8000)                      │
│                                                                     │
│  ┌────────────────┐   ┌────────────────┐   ┌───────────────────┐    │
│  │  /ws/live-     │   │  /predict      │   │  /chat            │    │
│  │  stream (WS)   │   │  /predict/batch│   │  (RAG Advisor)    │    │
│  │                │   │  /upload/csv   │   │                   │    │
│  │  Real-time     │   │  /upload/pcap  │   │  Input Sanitizer  │    │
│  │  LSTM inference│   │                │   │  Prompt Injection │    │
│  └───────┬────────┘   └───────┬────────┘   └─────────┬─────────┘    │
│          │                    │                      │              │
│          └──────────┬─────────┘                      │              │
│                     ▼                                ▼              │
│           ┌─────────────────┐            ┌──────────────────────┐   │
│           │  LSTM Service   │            │    RAG Service       │   │
│           │  (Singleton)    │            │                      │   │
│           │                 │            │  LangChain Chain     │   │
│           │ lstm_ids.pt     │            │  ┌────────────────┐  │   │
│           │ (PyTorch 2.5)   │            │  │  ChromaDB      │  │   │
│           │                 │            │  │  (87 vectors)  │  │   │
│           │ StandardScaler  │            │  │  nomic-embed   │  │   │
│           │ (115 features)  │            │  └───────┬────────┘  │   │
│           └─────────────────┘            │          ▼           │   │
│                                          │  Ollama LLM          │   │
│           ┌─────────────────┐            │  mistral-nemo        │   │
│           │ Security Layer  │            └──────────────────────┘   │
│           │ - Rate Limiting │                                       │
│           │ - Sec Headers   │            ┌──────────────────────┐   │
│           │ - CORS          │            │  Knowledge Base      │   │
│           │ - Size Limits   │            │  6 x .md documents   │   │
│           └─────────────────┘            │  (cybersecurity docs)│   │
│                                          └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                  │                              │
                  ▼                              ▼
         ┌──────────────────┐         ┌──────────────────────┐
         │  NSL-KDD Dataset │         │  Ollama (port 11434) │
         │  KDDTrain+.csv   │         │  - mistral-nemo (LLM)│
         │  KDDTest+.csv    │         │  - nomic-embed-text  │
         │  (125K samples)  │         │    (embeddings)      │
         └──────────────────┘         └──────────────────────┘

---

## Data Flow

### 1. Single Prediction Flow
User Input (features)
→ POST /predict
→ LSTMService.predict()
→ StandardScaler.transform()
→ LSTM.forward()
→ sigmoid() → probability
→ PredictionResult (label, severity, prob)
→ JSON Response

### 2. CSV Upload Flow
File Upload
→ POST /upload/csv
→ parse_csv() [pandas]
→ List[NetworkFlowFeatures]
→ LSTMService.predict_batch() [single forward pass]
→ List[PredictionResult]
→ _save_report() [JSON file]
→ UploadResponse

### 3. RAG Chat Flow
User Question
→ InputSanitizer.sanitize() [injection check]
→ POST /chat
→ RAGService.query()
→ OllamaEmbeddings.embed_query(question)
→ Chroma.similarity_search_with_scores(k=5)
→ _build_prompt(system + anomaly_ctx + history + context + question)
→ Ollama /api/generate (mistral-nemo, temp=0.3)
→ ChatResponse (answer, sources, response_ms)

### 4. Live Stream (WebSocket)
WS Connect → /ws/live-stream
→ Client sends: {"type": "predict", "features": {...}}
→ LSTMService.predict(features)
→ Server sends: {"event": "prediction", "payload": {...}}
→ Repeat per packet
→ Auto-reconnect if disconnected (3s delay)

---

## ML Model Details

| Property           | Value                           |
|--------------------|---------------------------------|
| Architecture       | 2-layer stacked LSTM            |
| Input features     | 115 (NSL-KDD one-hot encoded)   |
| Hidden size        | 128 → 64                        |
| FC head            | 128 → 64 → 32 → 1               |
| Parameters         | ~189,313                        |
| Training dataset   | NSL-KDD (125,973 samples)       |
| Class balancing    | SMOTE                           |
| Loss function      | BCEWithLogitsLoss + pos_weight  |
| Optimizer          | Adam (lr=0.001, decay=1e-5)     |
| Scheduler          | CosineAnnealingLR               |
| Test Accuracy      | ~98.5%                          |
| Test F1            | ~0.984                          |
| Test AUC-ROC       | ~0.994                          |

---

## Security Controls

| Control                  | Implementation                        |
|--------------------------|---------------------------------------|
| Prompt injection defence | InputSanitizer (12 regex patterns)    |
| Rate limiting            | SlowAPI (60 req/min default)          |
| CORS                     | Origin allowlist from .env            |
| Request size limit       | 105MB hard limit (middleware)         |
| File type validation     | Extension allowlist (.csv/.pcap only) |
| Security headers         | X-Frame-Options, X-Content-Type, etc. |
| Secret masking           | mask_sensitive() in logging           |
| No external API calls    | All LLM inference is 100% local       |

---

## Technology Stack

| Layer        | Technology                     | Version  |
|--------------|--------------------------------|----------|
| Frontend     | Next.js (App Router)           | 15.x     |
| UI           | Tailwind CSS + shadcn/ui       | latest   |
| Charts       | Recharts                       | 2.13     |
| Backend      | FastAPI                        | 0.115    |
| ML           | PyTorch                        | 2.5.1    |
| RAG          | LangChain + ChromaDB           | 0.3.9    |
| LLM          | Ollama (mistral-nemo)          | local    |
| Embeddings   | nomic-embed-text (Ollama)      | local    |
| Dataset      | NSL-KDD                        | 2009     |
| PCAP parsing | Scapy                          | 2.5.0    |
