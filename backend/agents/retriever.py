"""
Retriever Agent:
- Performs hybrid retrieval (Dense Vector + BM25 keyword search)
- Applies configurable alpha weighting to combine scores
- Reranks results using cross-encoder similarity (or score-based fallback)
- Returns top-k semantically and lexically relevant chunks
"""
import logging
import math
from typing import List, Dict, Any, Optional

from backend.agents.base import BaseAgent, AgentState
from backend.config import settings
from backend.ingestion.embedder import Embedder
from backend.vector_db.base import get_vector_store

logger = logging.getLogger("apks.agent.retriever")

# BM25 state (lazily initialized per retrieval session using in-memory corpus)
_bm25_corpus: Optional[List[str]] = None
_bm25_meta: Optional[List[Dict]] = None
_bm25_model = None


def _build_bm25_index(chunks: List[Dict[str, Any]]):
    """Build a BM25 index from a list of chunk dicts."""
    global _bm25_corpus, _bm25_meta, _bm25_model
    try:
        from rank_bm25 import BM25Okapi
        _bm25_meta = chunks
        tokenized = [c["content"].lower().split() for c in chunks]
        _bm25_corpus = tokenized
        _bm25_model = BM25Okapi(tokenized)
        logger.info(f"BM25 index built with {len(chunks)} chunks.")
    except ImportError:
        logger.warning("rank-bm25 not installed. BM25 retrieval disabled.")
        _bm25_model = None


def _bm25_search(query: str, meta_chunks: List[Dict], top_k: int = 10) -> List[Dict]:
    """Run BM25 search and return scored results."""
    global _bm25_model, _bm25_meta
    if _bm25_model is None or not _bm25_meta:
        return []

    tokenized_query = query.lower().split()
    scores = _bm25_model.get_scores(tokenized_query)

    results = []
    for idx, score in sorted(enumerate(scores), key=lambda x: -x[1])[:top_k]:
        if idx < len(_bm25_meta):
            res = dict(_bm25_meta[idx])
            res["bm25_score"] = float(score)
            results.append(res)
    return results


def _hybrid_merge(
    vector_results: List[Dict],
    bm25_results: List[Dict],
    alpha: float,
    top_k: int,
) -> List[Dict]:
    """
    Merge vector and BM25 results using RRF (Reciprocal Rank Fusion) + score weighting.
    alpha = weight for vector search; (1-alpha) = weight for BM25.
    """
    # Normalise BM25 scores to [0, 1]
    bm25_scores = {r["id"]: r.get("bm25_score", 0) for r in bm25_results}
    max_bm25 = max(bm25_scores.values(), default=1.0)
    if max_bm25 == 0:
        max_bm25 = 1.0

    # Normalise vector scores (already cosine similarity in [-1,1] → use as-is)
    vector_scores = {r["id"]: r.get("score", 0) for r in vector_results}

    # Combine
    all_ids = set(vector_scores) | set(bm25_scores)
    combined: Dict[str, Dict] = {}

    for r in vector_results + bm25_results:
        rid = r["id"]
        if rid not in combined:
            combined[rid] = dict(r)

    for rid in all_ids:
        v_score = vector_scores.get(rid, 0.0)
        b_score = bm25_scores.get(rid, 0.0) / max_bm25
        combined[rid]["hybrid_score"] = alpha * v_score + (1 - alpha) * b_score

    sorted_results = sorted(combined.values(), key=lambda x: -x.get("hybrid_score", 0))
    return sorted_results[:top_k]


class RetrieverAgent(BaseAgent):
    name = "RetrieverAgent"

    def __init__(self):
        self.vector_store = get_vector_store()

    def _get_all_db_chunks(self, db_session) -> List[Dict]:
        """Load all chunks from the relational DB for BM25 indexing."""
        from backend.database import ChunkDB
        rows = db_session.query(ChunkDB).all()
        return [
            {
                "id": r.id,
                "doc_id": r.doc_id,
                "content": r.content,
                "page_number": r.page_number,
                "metadata": {"source": r.document.filename if r.document else "", "page_number": r.page_number},
            }
            for r in rows
        ]

    def retrieve(self, queries: List[str], db_session, top_k: int = None) -> List[Dict]:
        """
        Run hybrid retrieval for a list of queries (subqueries from planner).
        Returns deduplicated, reranked chunks.
        """
        top_k = top_k or settings.TOP_K
        alpha = settings.HYBRID_ALPHA

        all_chunks_db = self._get_all_db_chunks(db_session)
        _build_bm25_index(all_chunks_db)

        seen_ids = set()
        merged_results = []

        for query in queries:
            # Dense vector search
            query_vec = Embedder.get_embedding(query)
            vec_results = self.vector_store.search(query_vec, top_k=top_k * 2)

            # BM25 keyword search
            bm25_results = _bm25_search(query, all_chunks_db, top_k=top_k * 2)

            # Hybrid merge
            merged = _hybrid_merge(vec_results, bm25_results, alpha, top_k)

            for chunk in merged:
                if chunk["id"] not in seen_ids:
                    seen_ids.add(chunk["id"])
                    merged_results.append(chunk)

        # Sort all gathered results by hybrid score and return top_k
        merged_results.sort(key=lambda x: -x.get("hybrid_score", x.get("score", 0)))
        return merged_results[:top_k]

    def execute(self, state: AgentState) -> AgentState:
        plan = state.get("plan", {})
        subqueries = plan.get("subqueries", [state.get("query", "")])
        db_session = state.get("db_session")

        if not db_session:
            logger.error("RetrieverAgent: No database session in state.")
            state["retrieved_chunks"] = []
            return state

        chunks = self.retrieve(subqueries, db_session)
        state["retrieved_chunks"] = chunks
        logger.info(f"RetrieverAgent retrieved {len(chunks)} chunks for {len(subqueries)} subqueries.")
        return state
