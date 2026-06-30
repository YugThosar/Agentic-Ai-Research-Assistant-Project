from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from backend.config import settings

class VectorStore(ABC):
    """Abstract Base Class for Vector DB operations."""
    
    @abstractmethod
    def add_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """
        Add chunks with their embeddings to the vector database.
        Each chunk is a dict: {
            "id": str,
            "doc_id": str,
            "content": str,
            "embedding": List[float],
            "metadata": Dict[str, Any]
        }
        """
        pass
        
    @abstractmethod
    def search(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for top_k most similar chunks.
        Returns list of chunks with similarity scores: {
            "id": str,
            "doc_id": str,
            "content": str,
            "score": float,
            "metadata": Dict[str, Any]
        }
        """
        pass
        
    @abstractmethod
    def delete_document(self, doc_id: str) -> None:
        """Deletes all chunks associated with a document."""
        pass
        
    @abstractmethod
    def clear_all(self) -> None:
        """Clear all entries in the vector store."""
        pass

def get_vector_store() -> VectorStore:
    """Factory function to get vector store based on configuration."""
    if settings.STORAGE_MODE == "production":
        try:
            from backend.vector_db.qdrant_client import QdrantVectorStore
            return QdrantVectorStore()
        except Exception as e:
            import logging
            logging.getLogger("apks.vector").error(f"Failed to load Qdrant client: {e}. Falling back to LocalVectorStore.")
            
    from backend.vector_db.local_client import LocalVectorStore
    return LocalVectorStore()
