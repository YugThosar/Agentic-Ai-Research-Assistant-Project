import hashlib
import logging
from typing import List
import numpy as np
from backend.config import settings

logger = logging.getLogger("apks.embedder")

_model = None

def get_embedding_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Initializing SentenceTransformer model: {settings.EMBEDDING_MODEL_NAME}")
            _model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer model: {e}. Using fallback deterministic embedder.")
            _model = "fallback"
    return _model

class Embedder:
    """
    Handles generation of semantic embeddings for text chunks.
    """
    
    @staticmethod
    def get_embedding(text: str) -> List[float]:
        """Generates embedding for a single text string."""
        return Embedder.get_embeddings([text])[0]

    @staticmethod
    def get_embeddings(texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a list of text strings."""
        if not texts:
            return []
            
        model = get_embedding_model()
        
        if model == "fallback":
            return [Embedder._fallback_embed(text) for text in texts]
            
        try:
            embeddings = model.encode(texts, show_progress_bar=False)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error during SentenceTransformer encoding: {e}. Falling back...")
            return [Embedder._fallback_embed(text) for text in texts]

    @staticmethod
    def _fallback_embed(text: str, dimension: int = 384) -> List[float]:
        """
        Generates a deterministic vector based on MD5 hashing of the input text.
        Useful for running tests or running in low-resource environments without models.
        """
        hasher = hashlib.md5(text.encode("utf-8"))
        seed = int(hasher.hexdigest(), 16) % (2**32)
        
        np.random.seed(seed)
        vec = np.random.randn(dimension)
        vec /= np.linalg.norm(vec)
        return vec.tolist()
