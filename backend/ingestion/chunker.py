import re
from typing import List, Dict, Any, Callable
import numpy as np

class Chunker:
    """
    Implements multiple chunking strategies to split long text into
    contextual chunks for search and reasoning.
    """

    @staticmethod
    def fixed_chunk(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Splits text by fixed character sizes with a character overlap."""
        if not text:
            return []
        
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    @staticmethod
    def recursive_chunk(
        text: str, 
        chunk_size: int = 500, 
        overlap: int = 50, 
        separators: List[str] = ["\n\n", "\n", " ", ""]
    ) -> List[str]:
        """
        Recursively splits text using a list of separator characters.
        Aims to keep paragraphs, sentences, and words together.
        """
        if not text:
            return []
        
        # Simple implementation of recursive split
        def split_text(text: str, separators: List[str]) -> List[str]:
            if len(text) <= chunk_size or not separators:
                return [text]
            
            separator = separators[0]
            next_separators = separators[1:]
            
            # Split text by the separator
            if separator == "":
                # Fallback to splitting by characters
                return list(text)
            
            splits = text.split(separator)
            chunks = []
            current_chunk = ""
            
            for part in splits:
                if len(current_chunk) + len(part) + len(separator) <= chunk_size:
                    if current_chunk:
                        current_chunk += separator
                    current_chunk += part
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    
                    # If the single part exceeds chunk size, split it with next separator
                    if len(part) > chunk_size:
                        sub_parts = split_text(part, next_separators)
                        # Handle overlap for sub-parts if necessary
                        chunks.extend(sub_parts)
                        current_chunk = ""
                    else:
                        current_chunk = part
            
            if current_chunk:
                chunks.append(current_chunk)
                
            return chunks

        raw_chunks = split_text(text, separators)
        
        # Add overlap between chunks
        overlapped_chunks = []
        for i, chunk in enumerate(raw_chunks):
            if i == 0:
                overlapped_chunks.append(chunk)
            else:
                # Add previous chunk's suffix as overlap
                prev_chunk = raw_chunks[i-1]
                overlap_text = prev_chunk[-overlap:] if len(prev_chunk) > overlap else prev_chunk
                overlapped_chunks.append(overlap_text + chunk)
                
        return overlapped_chunks

    @staticmethod
    def semantic_chunk(
        text: str,
        embedding_fn: Callable[[List[str]], List[List[float]]],
        similarity_threshold_percentile: float = 85.0
    ) -> List[str]:
        """
        Semantic chunking:
        1. Splits text into sentences.
        2. Generates embeddings for each sentence.
        3. Measures cosine distances between adjacent sentences.
        4. Splits the text at distances higher than the threshold percentile.
        """
        if not text:
            return []

        # Split into sentences using a regex (handles .?! followed by space)
        sentences = re.split(r'(?<=[.?!])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= 1:
            return sentences

        # Compute embeddings for all sentences
        embeddings = np.array(embedding_fn(sentences))
        
        # Calculate cosine similarities between adjacent sentence embeddings
        similarities = []
        for i in range(len(embeddings) - 1):
            vec1 = embeddings[i]
            vec2 = embeddings[i + 1]
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            if norm1 > 0 and norm2 > 0:
                similarity = np.dot(vec1, vec2) / (norm1 * norm2)
            else:
                similarity = 0.0
            similarities.append(similarity)
            
        # Convert similarities to distances (1 - similarity)
        distances = [1.0 - sim for sim in similarities]
        
        # Determine the threshold for splitting
        if distances:
            threshold = np.percentile(distances, similarity_threshold_percentile)
        else:
            threshold = 0.5
            
        # Build chunks
        chunks = []
        current_chunk = sentences[0]
        
        for i, distance in enumerate(distances):
            next_sentence = sentences[i + 1]
            if distance > threshold:
                # Split boundary detected
                chunks.append(current_chunk)
                current_chunk = next_sentence
            else:
                current_chunk += " " + next_sentence
                
        chunks.append(current_chunk)
        return chunks
