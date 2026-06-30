"""
Ingestion Pipeline Orchestrator:
Coordinates the full document processing pipeline:
  parse → clean → chunk → embed → store (vector + relational + knowledge graph)
"""
import os
import uuid
import logging
from typing import Optional
from sqlalchemy.orm import Session

from backend.config import settings, UPLOAD_DIR
from backend.database import DocumentDB, ChunkDB
from backend.ingestion.parser import DocumentParser
from backend.ingestion.chunker import Chunker
from backend.ingestion.embedder import Embedder
from backend.vector_db.base import get_vector_store
from backend.knowledge_graph.graph_client import get_graph_client
from backend.utils.llm import llm_generate

logger = logging.getLogger("apks.ingestion")

SUPPORTED_EXTENSIONS = {"pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls", "csv", "txt", "md", "markdown"}


def extract_triples_from_text(text: str, doc_id: str, filename: str) -> list:
    """Use LLM to extract entity-relationship triples from a text chunk."""
    prompt = f"""Extract the most important entity-relationship triples from the following text.
Return a JSON array of objects, each with "head", "relation", and "tail" string fields.
Extract at most 10 triples. Focus on factual, domain-relevant relationships.
If no meaningful triples can be found, return an empty array [].

Text:
{text[:1500]}

Return only the JSON array, nothing else."""

    try:
        raw = llm_generate(prompt=prompt, json_mode=True)
        import json
        triples = json.loads(raw)
        if isinstance(triples, list):
            for t in triples:
                t["doc_id"] = doc_id
            return triples
    except Exception as e:
        logger.warning(f"Triple extraction failed for {filename}: {e}")
    return []


def run_ingestion_pipeline(
    file_path: str,
    filename: str,
    file_type: str,
    doc_id: str,
    db: Session,
    chunking_strategy: str = "recursive",
):
    """
    Full ingestion pipeline for a single document.
    Updates the document status in the database as it progresses.
    """
    doc_record = db.query(DocumentDB).filter(DocumentDB.id == doc_id).first()

    def update_status(status: str, error: Optional[str] = None):
        if doc_record:
            doc_record.status = status
            if error:
                doc_record.error_message = error
            db.commit()

    try:
        # Step 1: Parse document
        update_status("parsing")
        logger.info(f"[{doc_id}] Parsing {filename} as {file_type}")
        pages = DocumentParser.parse(file_path, file_type)

        if not pages:
            raise ValueError(f"Parser returned no content for {filename}")

        # Step 2: Chunk pages
        update_status("chunking")
        all_chunks_text = []  # (text, page_number)
        for page in pages:
            page_text = page["text"]
            page_num = page["page_number"]
            if not page_text.strip():
                continue

            if chunking_strategy == "fixed":
                chunk_texts = Chunker.fixed_chunk(page_text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
            elif chunking_strategy == "semantic":
                chunk_texts = Chunker.semantic_chunk(page_text, Embedder.get_embeddings)
            else:  # default: recursive
                chunk_texts = Chunker.recursive_chunk(page_text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)

            for ct in chunk_texts:
                if ct.strip():
                    all_chunks_text.append((ct.strip(), page_num))

        logger.info(f"[{doc_id}] Created {len(all_chunks_text)} chunks.")

        # Step 3: Embed chunks
        update_status("embedding")
        texts_only = [c[0] for c in all_chunks_text]
        embeddings = Embedder.get_embeddings(texts_only)

        # Step 4: Store chunks in relational DB and vector store
        update_status("storing")
        vector_store = get_vector_store()
        graph_client = get_graph_client()
        vector_chunks = []
        all_text_for_graph = []

        for idx, ((text, page_num), embedding) in enumerate(zip(all_chunks_text, embeddings)):
            chunk_id = str(uuid.uuid4())

            # Relational DB
            chunk_record = ChunkDB(
                id=chunk_id,
                doc_id=doc_id,
                chunk_index=idx,
                content=text,
                page_number=page_num,
            )
            db.add(chunk_record)

            # Vector store batch
            vector_chunks.append({
                "id": chunk_id,
                "doc_id": doc_id,
                "content": text,
                "embedding": embedding,
                "metadata": {"source": filename, "page_number": page_num},
            })

            # Collect representative chunks for KG extraction (every 5th to limit LLM calls)
            if idx % 5 == 0:
                all_text_for_graph.append(text)

        db.commit()
        vector_store.add_chunks(vector_chunks)

        # Step 5: Knowledge graph extraction (async-like, best-effort)
        update_status("building_graph")
        combined_text_for_graph = "\n\n".join(all_text_for_graph[:10])  # limit tokens
        triples = extract_triples_from_text(combined_text_for_graph, doc_id, filename)
        if triples:
            graph_client.add_triples(triples)
            logger.info(f"[{doc_id}] Added {len(triples)} triples to knowledge graph.")

        update_status("completed")
        logger.info(f"[{doc_id}] Ingestion complete for {filename}.")

    except Exception as e:
        logger.error(f"[{doc_id}] Ingestion failed for {filename}: {e}")
        update_status("error", str(e))
        raise
