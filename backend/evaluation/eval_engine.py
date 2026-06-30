"""
Evaluation Engine:
Computes automated metrics:
  - Faithfulness: fraction of answer sentences grounded in evidence
  - Groundedness: proportion of claims traceable to specific chunks
  - Relevance: similarity of answer to query
  - Recall@K, Precision@K for retrieval
"""
import logging
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.database import EvaluationDB, MessageDB
from backend.ingestion.embedder import Embedder
import numpy as np

logger = logging.getLogger("apks.eval")


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    a, b = np.array(v1), np.array(v2)
    n1, n2 = np.linalg.norm(a), np.linalg.norm(b)
    if n1 == 0 or n2 == 0:
        return 0.0
    return float(np.dot(a, b) / (n1 * n2))


def compute_faithfulness(answer: str, evidence_chunks: List[Dict]) -> float:
    """
    Estimate faithfulness by measuring average cosine similarity of each
    answer sentence against the closest evidence chunk embedding.
    """
    sentences = re.split(r'(?<=[.?!])\s+', answer)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    if not sentences or not evidence_chunks:
        return 0.5  # neutral when unable to compute

    evidence_texts = [c["content"] for c in evidence_chunks]
    evidence_embeddings = Embedder.get_embeddings(evidence_texts)
    sentence_embeddings = Embedder.get_embeddings(sentences)

    scores = []
    for sent_emb in sentence_embeddings:
        max_sim = max(cosine_similarity(sent_emb, ev_emb) for ev_emb in evidence_embeddings)
        scores.append(max_sim)

    return float(np.mean(scores)) if scores else 0.5


def compute_relevance(query: str, answer: str) -> float:
    """Relevance: cosine similarity between query and answer embeddings."""
    query_emb = Embedder.get_embedding(query)
    answer_emb = Embedder.get_embedding(answer)
    return cosine_similarity(query_emb, answer_emb)


def compute_retrieval_metrics(
    retrieved_ids: List[str],
    relevant_ids: List[str],
    k: int = 5,
) -> Dict[str, float]:
    """Compute Recall@K and Precision@K given sets of IDs."""
    if not relevant_ids:
        return {"recall_at_k": 0.0, "precision_at_k": 0.0, "mrr": 0.0}

    retrieved_k = retrieved_ids[:k]
    hits = set(retrieved_k) & set(relevant_ids)

    precision = len(hits) / k if k > 0 else 0.0
    recall = len(hits) / len(relevant_ids) if relevant_ids else 0.0

    # MRR
    mrr = 0.0
    for rank, rid in enumerate(retrieved_k, start=1):
        if rid in relevant_ids:
            mrr = 1.0 / rank
            break

    return {"recall_at_k": recall, "precision_at_k": precision, "mrr": mrr}


def auto_evaluate_and_save(
    db: Session,
    message_id: str,
    query: str,
    answer: str,
    retrieved_chunks: List[Dict],
    planning_accuracy: Optional[float] = None,
    critique_accuracy: Optional[float] = None,
) -> Dict[str, float]:
    """Compute metrics and persist them in the evaluations table."""
    faithfulness = compute_faithfulness(answer, retrieved_chunks)
    relevance = compute_relevance(query, answer)
    groundedness = faithfulness  # for simplicity, use faithfulness as proxy

    eval_record = EvaluationDB(
        message_id=message_id,
        faithfulness=faithfulness,
        groundedness=groundedness,
        relevance=relevance,
        planning_accuracy=planning_accuracy,
        critique_accuracy=critique_accuracy,
    )
    db.add(eval_record)
    db.commit()

    metrics = {
        "faithfulness": faithfulness,
        "groundedness": groundedness,
        "relevance": relevance,
    }
    logger.info(f"Evaluation saved for message {message_id}: {metrics}")
    return metrics
