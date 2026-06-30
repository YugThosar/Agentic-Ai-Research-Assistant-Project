# Agentic Personal Knowledge System (APKS)

> A research-grade, production-quality multi-agent RAG system with iterative self-refinement, knowledge graph integration, and streaming UI.

[![Python](https://img.shields.io/badge/python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61dafb)](https://reactjs.org)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **Multi-Agent Pipeline** | Planner → Retriever → Reasoner → Critic → Refiner → Memory |
| 🔍 **Hybrid Retrieval** | Dense vector search + BM25 keyword search with configurable α-weighting |
| 🧠 **Self-Refinement Loop** | Automatically refines low-confidence answers up to N iterations |
| 📌 **Citation Engine** | Every answer cites exact source document, page number, and chunk |
| 🕸️ **Knowledge Graph** | LLM-extracted entity-relationship triples visualized interactively |
| 💾 **Triple Memory** | Episodic, Semantic, and Working memory persisted across sessions |
| 📊 **Auto-Evaluation** | Faithfulness, Groundedness, and Relevance scored for every answer |
| 🌊 **SSE Streaming** | Live agent steps and answer token streaming in the UI |
| 🐳 **Docker Ready** | One-command production deployment with all services |

---

## 🏗️ Architecture

```
User Query
  ↓
Planner Agent      → classify query type, generate subqueries
  ↓
Retriever Agent    → hybrid vector + BM25 search, rerank
  ↓
Reasoning Agent    → chain-of-thought synthesis with citations
  ↓
Critic Agent       → hallucination check, confidence score
  ↓ (if confidence < threshold)
Refinement Agent   → re-retrieve, re-reason, re-critique (loop)
  ↓
Memory Agent       → persist conversation, update semantic memory
  ↓
Response Generator → stream final answer + citations to UI
```

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 18+
- (Optional) A Gemini or OpenAI API key

### 1. Clone & configure
```bash
git clone <repo>
cd agentic-pks
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY or OPENAI_API_KEY
```

### 2. Install backend dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the backend
```bash
uvicorn backend.main:app --reload --port 8000
```

### 4. Install & run the frontend
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## 🐳 Production Deployment (Docker)

```bash
docker-compose up --build
```

This starts:
- **FastAPI** on port 8000
- **React UI** on port 80
- **PostgreSQL** on port 5432
- **Qdrant** on port 6333
- **Neo4j** on ports 7474 / 7687

Set `STORAGE_MODE=production` in your `.env` to use production backends.

---

## 📁 Project Structure

```
agentic-pks/
├── backend/
│   ├── agents/          # 6 agents: planner, retriever, reasoning, critic, refinement, memory
│   ├── ingestion/       # parser, chunker (fixed/recursive/semantic), embedder
│   ├── vector_db/       # FAISS (local) + Qdrant (production)
│   ├── knowledge_graph/ # NetworkX (local) + Neo4j (production)
│   ├── evaluation/      # Faithfulness, groundedness, relevance metrics
│   ├── utils/           # LLM client wrapper (Gemini/OpenAI/Ollama)
│   ├── config.py        # Pydantic settings
│   ├── database.py      # SQLAlchemy models
│   ├── schemas.py       # Pydantic API schemas
│   └── main.py          # FastAPI endpoints
├── frontend/
│   └── src/
│       ├── components/  # ChatPage, DocumentsPage, DashboardPage, GraphPage, MemoryPage, EvalPage
│       ├── App.jsx      # Root layout with sidebar navigation
│       └── index.css    # Premium dark design system
├── tests/
│   └── test_api.py      # Integration + unit tests
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
├── requirements.txt
└── .env.example
```

---

## 🤖 Supported LLM Providers

| Provider | Models | Notes |
|---|---|---|
| **Google Gemini** | `gemini-2.5-flash`, `gemini-2.5-pro` | Recommended. Set `GEMINI_API_KEY` |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini` | Set `OPENAI_API_KEY` |
| **Ollama (local)** | `llama3`, `mistral`, `qwen` | No API key needed. Install Ollama locally |

Automatic fallback: Gemini → OpenAI → Ollama → Error

---

## 📄 Supported Document Types

| Format | Extension |
|---|---|
| PDF | `.pdf` |
| Word | `.docx`, `.doc` |
| PowerPoint | `.pptx`, `.ppt` |
| Excel | `.xlsx`, `.xls` |
| CSV | `.csv` |
| Text | `.txt` |
| Markdown | `.md`, `.markdown` |

---

## 🔬 Chunking Strategies

| Strategy | Description |
|---|---|
| `fixed` | Split by character count with overlap |
| `recursive` | Recursively split by `\n\n`, `\n`, space — preserves structure |
| `semantic` | Embedding-based boundary detection using cosine distance drops |

---

## 📊 Evaluation Metrics

| Metric | Method |
|---|---|
| **Faithfulness** | Avg cosine similarity of answer sentences vs. evidence chunks |
| **Groundedness** | Proxy: same as faithfulness (evidence-grounding check) |
| **Relevance** | Cosine similarity between query embedding and answer embedding |
| **Recall@K** | Available via `/api/evaluation/reports` |

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## 📝 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/documents/upload` | POST | Upload document |
| `/api/documents` | GET | List documents |
| `/api/documents/{id}` | DELETE | Delete document |
| `/api/chat` | POST | Chat (SSE stream) |
| `/api/conversations` | GET | List conversations |
| `/api/memory` | GET | View agent memory |
| `/api/memory/update` | POST | Update memory |
| `/api/graph` | GET | Knowledge graph data |
| `/api/graph/search` | GET | Search entities |
| `/api/evaluation/reports` | GET | Evaluation metrics |
| `/api/evaluation/feedback` | POST | Submit user feedback |
| `/api/dashboard/stats` | GET | Dashboard statistics |

Full interactive docs at: **http://localhost:8000/docs**

---

## 🏆 Performance vs Basic RAG

| Capability | Basic RAG | APKS |
|---|---|---|
| Multi-hop reasoning | ❌ | ✅ |
| Self-critique | ❌ | ✅ |
| Iterative refinement | ❌ | ✅ |
| Knowledge graph | ❌ | ✅ |
| Persistent memory | ❌ | ✅ |
| Citation quality | Poor | Rich (doc + page) |
| Hallucination guard | None | Critic Agent |

---

## 📜 License

MIT License — use freely for research and commercial projects.
"# Agentic AI-Research Assistant Project" 
