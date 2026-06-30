"""
Qdrant vector store client – used in production mode.
"""
import logging
from typing import List, Dict, Any
from backend.config import settings
from backend.vector_db.base import VectorStore

logger = logging.getLogger("apks.vector.qdrant")
COLLECTION_NAME = "apks_chunks"


class QdrantVectorStore(VectorStore):
    def __init__(self):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY or None,
        )
        # Ensure collection exists
        existing = [c.name for c in self.client.get_collections().collections]
        if COLLECTION_NAME not in existing:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")
        else:
            logger.info(f"Using existing Qdrant collection: {COLLECTION_NAME}")

    def add_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        from qdrant_client.models import PointStruct
        import uuid

        points = []
        for chunk in chunks:
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=chunk["embedding"],
                payload={
                    "id": chunk["id"],
                    "doc_id": chunk["doc_id"],
                    "content": chunk["content"],
                    **chunk.get("metadata", {}),
                },
            ))
        self.client.upsert(collection_name=COLLECTION_NAME, points=points)
        logger.info(f"Upserted {len(points)} chunks to Qdrant.")

    def search(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        results = self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k,
        )
        return [
            {
                "id": r.payload.get("id", str(r.id)),
                "doc_id": r.payload.get("doc_id", ""),
                "content": r.payload.get("content", ""),
                "score": r.score,
                "metadata": {k: v for k, v in r.payload.items() if k not in ("id", "doc_id", "content")},
            }
            for r in results
        ]

    def delete_document(self, doc_id: str) -> None:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
        )
        logger.info(f"Deleted Qdrant entries for doc_id={doc_id}")

    def clear_all(self) -> None:
        self.client.delete_collection(COLLECTION_NAME)
        logger.info("Cleared all Qdrant data.")
