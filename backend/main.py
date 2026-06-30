"""
APKS FastAPI Backend — main.py
All API endpoints:
  - Document upload & management
  - Chat with streaming SSE (multi-agent pipeline)
  - Memory read/write
  - Knowledge Graph
  - Evaluation & Feedback
  - Dashboard stats
"""
import asyncio
import json
import os
import shutil
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.config import settings, UPLOAD_DIR
from backend.database import (
    init_db, get_db, DocumentDB, ChunkDB, ConversationDB, MessageDB,
    MemoryDB, EvaluationDB
)
from backend.schemas import (
    DocumentResponse, ChunkResponse, ConversationResponse, MessageResponse,
    ChatRequest, MemoryResponse, MemoryUpdateRequest, GraphResponse,
    FeedbackRequest, EvaluationResponse,
)
from backend.agents.planner import PlannerAgent
from backend.agents.retriever import RetrieverAgent
from backend.agents.reasoning import ReasoningAgent
from backend.agents.critic import CriticAgent
from backend.agents.refinement import RefinementAgent
from backend.agents.memory import MemoryAgent
from backend.agents.base import AgentState
from backend.ingestion.pipeline import run_ingestion_pipeline, SUPPORTED_EXTENSIONS
from backend.knowledge_graph.graph_client import get_graph_client
from backend.evaluation.eval_engine import auto_evaluate_and_save
from backend.utils.llm import llm_generate_stream

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("apks")

app = FastAPI(
    title="Agentic Personal Knowledge System API",
    version="1.0.0",
    description="Multi-agent RAG system with iterative self-refinement and knowledge graph integration.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("APKS backend started. Database initialized.")


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────
@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ─────────────────────────────────────────────
# DOCUMENT MANAGEMENT
# ─────────────────────────────────────────────
@app.post("/api/documents/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    chunking_strategy: str = Form("recursive"),
    db: Session = Depends(get_db),
):
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: .{ext}. Supported: {SUPPORTED_EXTENSIONS}")

    doc_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{doc_id}_{file.filename}"

    # Save file to disk
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    file_size = os.path.getsize(save_path)

    # Create DB record
    doc = DocumentDB(
        id=doc_id,
        filename=file.filename,
        file_type=ext,
        file_size=file_size,
        status="queued",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Run ingestion in background
    background_tasks.add_task(
        run_ingestion_pipeline,
        str(save_path), file.filename, ext, doc_id, db, chunking_strategy
    )

    return doc


@app.get("/api/documents", response_model=List[DocumentResponse])
def list_documents(db: Session = Depends(get_db)):
    return db.query(DocumentDB).order_by(DocumentDB.upload_date.desc()).all()


@app.get("/api/documents/{doc_id}", response_model=DocumentResponse)
def get_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(DocumentDB).filter(DocumentDB.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@app.get("/api/documents/{doc_id}/chunks", response_model=List[ChunkResponse])
def get_document_chunks(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(DocumentDB).filter(DocumentDB.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    return db.query(ChunkDB).filter(ChunkDB.doc_id == doc_id).order_by(ChunkDB.chunk_index).all()


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(DocumentDB).filter(DocumentDB.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Remove from vector store
    from backend.vector_db.base import get_vector_store
    get_vector_store().delete_document(doc_id)

    # Remove from knowledge graph
    get_graph_client().delete_document_nodes(doc_id)

    # Remove from relational DB (cascades to chunks, citations)
    db.delete(doc)
    db.commit()

    # Remove file from disk
    for f in UPLOAD_DIR.iterdir():
        if f.name.startswith(doc_id):
            f.unlink(missing_ok=True)

    return {"message": f"Document {doc_id} deleted."}


# ─────────────────────────────────────────────
# CHAT & AGENT PIPELINE
# ─────────────────────────────────────────────
@app.post("/api/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Main chat endpoint. Returns a Server-Sent Events (SSE) stream of agent steps
    followed by the final answer tokens.
    """
    planner = PlannerAgent()
    retriever = RetrieverAgent()
    reasoner = ReasoningAgent()
    critic = CriticAgent()
    refiner = RefinementAgent()
    memory_agent = MemoryAgent()

    state = AgentState(
        query=request.query,
        conversation_id=request.conversation_id,
        model_provider=request.model_provider or settings.DEFAULT_LLM_PROVIDER,
        model_name=request.model_name or settings.DEFAULT_LLM_MODEL,
        db_session=db,
    )

    async def event_generator():
        try:
            # Step 0: Load memory context
            nonlocal state
            state = memory_agent.load_context(state)

            # Step 1: Planner
            yield _sse_event("status", {"step": "planner", "message": "Analyzing query and creating plan..."})
            state = await asyncio.to_thread(planner.execute, state)
            yield _sse_event("planner", {"plan": state.get("plan", {})})

            # Step 2: Retriever
            yield _sse_event("status", {"step": "retriever", "message": "Searching knowledge base..."})
            state = await asyncio.to_thread(retriever.execute, state)
            chunks_preview = [
                {
                    "id": c.get("id"),
                    "content": c.get("content", "")[:250],
                    "source": c.get("metadata", {}).get("source", ""),
                    "page": c.get("metadata", {}).get("page_number", 1),
                    "score": round(c.get("hybrid_score", c.get("score", 0)), 4),
                }
                for c in state.get("retrieved_chunks", [])
            ]
            yield _sse_event("retriever", {"chunks": chunks_preview, "count": len(chunks_preview)})

            # Step 3: Reasoning
            yield _sse_event("status", {"step": "reasoning", "message": "Synthesizing information..."})
            state = await asyncio.to_thread(reasoner.execute, state)
            yield _sse_event("reasoner", {
                "reasoning_steps": state.get("reasoning", {}).get("reasoning_steps", ""),
                "conflicts": state.get("reasoning", {}).get("conflicts_detected", []),
            })

            # Step 4: Critic
            yield _sse_event("status", {"step": "critic", "message": "Evaluating answer quality..."})
            state = await asyncio.to_thread(critic.execute, state)
            critique = state.get("critique", {})
            yield _sse_event("critic", {
                "confidence": critique.get("confidence", 0),
                "issues": critique.get("issues", []),
                "missing_context": critique.get("missing_context", []),
                "summary": critique.get("critique_summary", ""),
            })

            # Step 5: Refinement (if needed)
            confidence = critique.get("confidence", 1.0)
            if confidence < settings.CONFIDENCE_THRESHOLD:
                yield _sse_event("status", {"step": "refinement", "message": f"Confidence {confidence:.0%} — refining answer..."})
                state = await asyncio.to_thread(refiner.execute, state)
                yield _sse_event("refinement", {
                    "loops": state.get("refinement_loops", 0),
                    "final_confidence": state.get("critique", {}).get("confidence", 0),
                })

            # Step 6: Stream final answer
            yield _sse_event("status", {"step": "generating", "message": "Generating final answer..."})

            # Build final prompt with the draft answer as a guide for streaming
            final_draft = state.get("reasoning", {}).get("draft_answer", "")
            if final_draft:
                # Stream the final draft token-by-token from the stored reasoning
                for token in llm_generate_stream(
                    prompt=f"Present the following answer clearly and professionally:\n\n{final_draft}",
                    provider=state.get("model_provider"),
                    model_name=state.get("model_name"),
                ):
                    yield _sse_event("token", {"text": token})
            else:
                yield _sse_event("token", {"text": "No answer was generated. Please upload relevant documents."})

            # Step 7: Save to memory and evaluate
            state = await asyncio.to_thread(memory_agent.execute, state)

            final_answer = state.get("reasoning", {}).get("draft_answer", "")
            saved_message_id = state.get("saved_message_id")

            if saved_message_id and final_answer:
                await asyncio.to_thread(
                    auto_evaluate_and_save,
                    db,
                    saved_message_id,
                    request.query,
                    final_answer,
                    state.get("retrieved_chunks", []),
                    None,
                    critique.get("confidence"),
                )

            # Final metadata event
            citations = [
                {
                    "source": c.get("metadata", {}).get("source", ""),
                    "page": c.get("metadata", {}).get("page_number", 1),
                    "chunk_id": c.get("id", ""),
                    "content": c.get("content", "")[:200],
                }
                for c in state.get("retrieved_chunks", [])
                if c.get("id") in set(state.get("reasoning", {}).get("evidence_used", [c.get("id", "")]))
            ]

            yield _sse_event("metadata", {
                "conversation_id": state.get("conversation_id"),
                "message_id": saved_message_id,
                "confidence": state.get("critique", {}).get("confidence", 0),
                "refinement_loops": state.get("refinement_loops", 0),
                "citations": citations,
                "query_type": state.get("plan", {}).get("query_type", ""),
            })

            yield _sse_event("done", {"message": "Complete"})

        except Exception as e:
            logger.error(f"Chat pipeline error: {e}", exc_info=True)
            yield _sse_event("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event string."""
    payload = json.dumps({"type": event_type, "data": data})
    return f"data: {payload}\n\n"


# ─────────────────────────────────────────────
# CONVERSATIONS
# ─────────────────────────────────────────────
@app.get("/api/conversations", response_model=List[ConversationResponse])
def list_conversations(db: Session = Depends(get_db)):
    return db.query(ConversationDB).order_by(ConversationDB.created_at.desc()).all()


@app.get("/api/conversations/{conv_id}", response_model=ConversationResponse)
def get_conversation(conv_id: str, db: Session = Depends(get_db)):
    conv = db.query(ConversationDB).filter(ConversationDB.id == conv_id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: str, db: Session = Depends(get_db)):
    conv = db.query(ConversationDB).filter(ConversationDB.id == conv_id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    db.delete(conv)
    db.commit()
    return {"message": "Conversation deleted"}


# ─────────────────────────────────────────────
# MEMORY
# ─────────────────────────────────────────────
@app.get("/api/memory", response_model=List[MemoryResponse])
def get_memory(category: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(MemoryDB)
    if category:
        q = q.filter(MemoryDB.category == category)
    return q.order_by(MemoryDB.updated_at.desc()).all()


@app.post("/api/memory/update", response_model=MemoryResponse)
def update_memory(req: MemoryUpdateRequest, db: Session = Depends(get_db)):
    existing = db.query(MemoryDB).filter(
        MemoryDB.category == req.category,
        MemoryDB.key == req.key
    ).first()
    if existing:
        existing.value = req.value
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        mem = MemoryDB(category=req.category, key=req.key, value=req.value)
        db.add(mem)
        db.commit()
        db.refresh(mem)
        return mem


@app.delete("/api/memory/{memory_id}")
def delete_memory(memory_id: str, db: Session = Depends(get_db)):
    mem = db.query(MemoryDB).filter(MemoryDB.id == memory_id).first()
    if not mem:
        raise HTTPException(404, "Memory item not found")
    db.delete(mem)
    db.commit()
    return {"message": "Memory item deleted"}


# ─────────────────────────────────────────────
# KNOWLEDGE GRAPH
# ─────────────────────────────────────────────
@app.get("/api/graph", response_model=GraphResponse)
def get_knowledge_graph():
    graph_client = get_graph_client()
    return graph_client.to_dict()


@app.get("/api/graph/search")
def search_graph(query: str, limit: int = 20):
    graph_client = get_graph_client()
    return {"results": graph_client.search_entities(query, limit)}


# ─────────────────────────────────────────────
# EVALUATION & FEEDBACK
# ─────────────────────────────────────────────
@app.get("/api/evaluation/reports")
def get_evaluation_report(db: Session = Depends(get_db)):
    evals = db.query(EvaluationDB).all()
    if not evals:
        return {
            "total_evaluations": 0,
            "avg_faithfulness": 0,
            "avg_groundedness": 0,
            "avg_relevance": 0,
            "feedback_stats": {},
        }

    faithfulness = [e.faithfulness or 0 for e in evals]
    groundedness = [e.groundedness or 0 for e in evals]
    relevance = [e.relevance or 0 for e in evals]

    feedback_counts = {}
    for e in evals:
        if e.feedback:
            feedback_counts[e.feedback] = feedback_counts.get(e.feedback, 0) + 1

    return {
        "total_evaluations": len(evals),
        "avg_faithfulness": round(sum(faithfulness) / len(faithfulness), 3),
        "avg_groundedness": round(sum(groundedness) / len(groundedness), 3),
        "avg_relevance": round(sum(relevance) / len(relevance), 3),
        "feedback_stats": feedback_counts,
    }


@app.post("/api/evaluation/feedback")
def submit_feedback(req: FeedbackRequest, db: Session = Depends(get_db)):
    msg = db.query(MessageDB).filter(MessageDB.id == req.message_id).first()
    if not msg:
        raise HTTPException(404, "Message not found")

    # Find or create evaluation record
    eval_record = db.query(EvaluationDB).filter(EvaluationDB.message_id == req.message_id).first()
    if eval_record:
        eval_record.feedback = req.feedback
    else:
        eval_record = EvaluationDB(message_id=req.message_id, feedback=req.feedback)
        db.add(eval_record)
    db.commit()
    return {"message": "Feedback recorded", "feedback": req.feedback}


# ─────────────────────────────────────────────
# DASHBOARD STATS
# ─────────────────────────────────────────────
@app.get("/api/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    doc_count = db.query(DocumentDB).count()
    chunk_count = db.query(ChunkDB).count()
    conv_count = db.query(ConversationDB).count()
    msg_count = db.query(MessageDB).filter(MessageDB.role == "assistant").count()

    # Document status breakdown
    from sqlalchemy import func
    status_counts = dict(
        db.query(DocumentDB.status, func.count(DocumentDB.id))
        .group_by(DocumentDB.status)
        .all()
    )

    # Recent documents
    recent_docs = db.query(DocumentDB).order_by(DocumentDB.upload_date.desc()).limit(5).all()

    # Knowledge graph stats
    graph_client = get_graph_client()
    graph_data = graph_client.to_dict()

    return {
        "documents": {"total": doc_count, "by_status": status_counts, "recent": [{"id": d.id, "filename": d.filename, "status": d.status} for d in recent_docs]},
        "chunks": {"total": chunk_count},
        "conversations": {"total": conv_count, "total_answers": msg_count},
        "knowledge_graph": {"nodes": len(graph_data["nodes"]), "edges": len(graph_data["edges"])},
    }
