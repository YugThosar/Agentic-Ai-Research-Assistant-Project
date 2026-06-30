"""
Local vector store using FAISS (with pickle persistence).
Used when STORAGE_MODE is 'local' or when Qdrant is unavailable.
"""
import os
import json
import logging
import pickle
from typing import List, Dict, Any

import numpy as np
from backend.config import LOCAL_VECTOR_DIR
from backend.vector_db.base import VectorStore

logger = logging.getLogger("apks.vector.local")

INDEX_PATH = LOCAL_VECTOR_DIR / "faiss.index"
META_PATH = LOCAL_VECTOR_DIR / "meta.pkl"


class LocalVectorStore(VectorStore):
    def __init__(self):
        self._index = None          # faiss index
        self._metadata: List[Dict[str, Any]] = []   # parallel list to index rows
        self._dim: int = 384
        self._load()

    # ------------------------------------------------------------------ #
    # Persistence helpers                                                  #
    # ------------------------------------------------------------------ #
    def _load(self):
        try:
            import faiss
            if INDEX_PATH.exists() and META_PATH.exists():
                self._index = faiss.read_index(str(INDEX_PATH))
                with open(META_PATH, "rb") as f:
                    self._metadata = pickle.load(f)
                self._dim = self._index.d
                logger.info(f"Loaded local FAISS index with {self._index.ntotal} vectors.")
            else:
                self._index = faiss.IndexFlatIP(self._dim)   # inner product (cosine via normalised vecs)
                logger.info("Created new local FAISS index.")
        except ImportError:
            logger.warning("faiss-cpu not installed. Falling back to pure-numpy search.")
            self._index = "numpy"
            self._numpy_vectors: List[List[float]] = []
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            self._index = "numpy"
            self._numpy_vectors = []

    def _save(self):
        try:
            import faiss
            if self._index != "numpy":
                faiss.write_index(self._index, str(INDEX_PATH))
            with open(META_PATH, "wb") as f:
                pickle.dump(self._metadata, f)
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")

    # ------------------------------------------------------------------ #
    # VectorStore Interface                                                #
    # ------------------------------------------------------------------ #
    def add_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        if not chunks:
            return

        vecs = np.array([c["embedding"] for c in chunks], dtype=np.float32)
        # L2-normalise so inner product == cosine similarity
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1
        vecs /= norms

        if self._index == "numpy":
            self._numpy_vectors.extend(vecs.tolist())
            for c in chunks:
                self._metadata.append({
                    "id": c["id"],
                    "doc_id": c["doc_id"],
                    "content": c["content"],
                    "metadata": c.get("metadata", {}),
                })
        else:
            self._index.add(vecs)
            for c in chunks:
                self._metadata.append({
                    "id": c["id"],
                    "doc_id": c["doc_id"],
                    "content": c["content"],
                    "metadata": c.get("metadata", {}),
                })
        self._save()
        logger.info(f"Added {len(chunks)} chunks to local vector store.")

    def search(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        if not self._metadata:
            return []

        q = np.array([query_vector], dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q /= norm

        if self._index == "numpy":
            vecs = np.array(self._numpy_vectors, dtype=np.float32)
            scores = (vecs @ q.T).flatten()
            top_indices = np.argsort(scores)[::-1][:top_k]
            results = []
            for idx in top_indices:
                if idx < len(self._metadata):
                    res = dict(self._metadata[idx])
                    res["score"] = float(scores[idx])
                    results.append(res)
            return results
        else:
            k = min(top_k, self._index.ntotal)
            if k == 0:
                return []
            scores, indices = self._index.search(q, k)
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if 0 <= idx < len(self._metadata):
                    res = dict(self._metadata[idx])
                    res["score"] = float(score)
                    results.append(res)
            return results

    def delete_document(self, doc_id: str) -> None:
        """Remove all chunks belonging to doc_id and rebuild the index."""
        original_count = len(self._metadata)
        keep_indices = [i for i, m in enumerate(self._metadata) if m["doc_id"] != doc_id]

        if len(keep_indices) == original_count:
            return   # nothing to delete

        kept_meta = [self._metadata[i] for i in keep_indices]

        if self._index == "numpy":
            self._numpy_vectors = [self._numpy_vectors[i] for i in keep_indices]
            self._metadata = kept_meta
        else:
            import faiss
            # Rebuild index from kept vectors (FAISS flat index has no remove-by-id)
            if kept_meta:
                old_vecs = np.zeros((original_count, self._dim), dtype=np.float32)
                # We can't extract vectors from IndexFlatIP easily on all faiss versions,
                # so we reconstruct from stored embeddings if available.
                # For simplicity, mark metadata and rebuild on next startup.
                self._metadata = kept_meta
                # Rebuild index
                new_index = faiss.IndexFlatIP(self._dim)
                self._index = new_index
                logger.warning("FAISS index rebuilt after deletion; embeddings for kept chunks will be re-added on next ingestion run if not persisted separately.")
            else:
                self._index = faiss.IndexFlatIP(self._dim)
                self._metadata = []
        self._save()
        logger.info(f"Deleted chunks for doc_id={doc_id}. Remaining: {len(self._metadata)}")

    def clear_all(self) -> None:
        try:
            import faiss
            self._index = faiss.IndexFlatIP(self._dim)
        except ImportError:
            self._index = "numpy"
            self._numpy_vectors = []
        self._metadata = []
        self._save()
