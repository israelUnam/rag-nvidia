# Copyright 2024
# Directory: rag-openrouter/app/services/chunker.py

"""
Herramientas de segmentación de texto para el procesamiento de documentos mediante el método RAG.
Implementa una segmentación sencilla basada en palabras con solapamiento para una recuperación óptima.
"""

import logging
import re
from typing import List, Dict, Any
from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# El texto del proyecto en español, con números y etiquetas, tiene una longitud de aproximadamente 2,75 caracteres por token;
# 2,3 deja un margen para que ningún fragmento supere el límite de tokens del modelo de incrustación.
CHARS_PER_TOKEN = 2.3


class TextChunker:
    """Herramienta sencilla para dividir texto en fragmentos, con segmentación basada en palabras y solapamiento."""
    
    def __init__(self, chunk_size: int = None, overlap: int = None):
        """
        Initialize chunker with configuration.
        
        Args:
            chunk_size: Approximate tokens per chunk (default from settings)
            overlap: Overlap tokens between chunks (default from settings)
        """
        self.chunk_size = chunk_size or settings.chunk_size
        self.overlap = overlap or settings.chunk_overlap
        
        # Rough approximation: 1 token ≈ 0.75 words
        self.words_per_chunk = int(self.chunk_size * 0.75)
        self.overlap_words = int(self.overlap * 0.75)
        self.max_chars = int(settings.embed_max_tokens * CHARS_PER_TOKEN)
        
        logger.info(
            f"Initialized chunker: ~{self.words_per_chunk} words / {self.max_chars} chars per chunk, "
            f"{self.overlap_words} words overlap"
        )
    
    def chunk_text(self, text: str, source: str, base_chunk_id: str) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Text to chunk
            source: Source identifier (URL, filename, etc.)
            base_chunk_id: Base identifier for chunks (will append #1, #2, etc.)
            
        Returns:
            List of chunk dictionaries with chunk_id, source, and text
        """
        if not text or not text.strip():
            return []
        
        # A leading Markdown title is repeated in every chunk so later chunks keep their context
        first_line = text.strip().splitlines()[0]
        title = self._clean_text(first_line) if first_line.startswith("#") else ""
        
        # Clean and normalize text
        cleaned_text = self._clean_text(text)
        words = cleaned_text.split()
        
        if len(words) <= self.words_per_chunk and len(cleaned_text) <= self.max_chars:
            # Text is small enough to be a single chunk
            return [{
                'chunk_id': f"{base_chunk_id}#1",
                'source': source,
                'text': cleaned_text
            }]
        
        chunks = []
        start_idx = 0
        chunk_num = 1
        
        while start_idx < len(words):
            prefix = f"{title} " if title and chunk_num > 1 else ""
            
            # Take words until either the word or the character budget is used up
            end_idx = start_idx
            length = len(prefix)
            limit = min(start_idx + self.words_per_chunk, len(words))
            while end_idx < limit:
                extra = len(words[end_idx]) + (1 if end_idx > start_idx else 0)
                if end_idx > start_idx and length + extra > self.max_chars:
                    break
                length += extra
                end_idx += 1
            
            chunk_text = prefix + ' '.join(words[start_idx:end_idx])
            
            # Create chunk dictionary
            chunk = {
                'chunk_id': f"{base_chunk_id}#{chunk_num}",
                'source': source,
                'text': chunk_text
            }
            chunks.append(chunk)
            
            # Move start index for next chunk (with overlap)
            if end_idx >= len(words):
                break  # We've processed all words
            
            overlap = min(self.overlap_words, (end_idx - start_idx) // 2)
            start_idx = max(end_idx - overlap, start_idx + 1)
            chunk_num += 1
        
        logger.info(f"Chunked text into {len(chunks)} chunks (source: {source})")
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text for better chunking.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        return text
    
    def chunk_documents(self, documents: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Chunk multiple documents.
        
        Args:
            documents: List of documents with 'text', 'source', and 'chunk_id' keys
            
        Returns:
            List of all chunks from all documents
        """
        all_chunks = []
        
        for doc in documents:
            text = doc.get('text', '')
            source = doc.get('source', 'unknown')
            base_chunk_id = doc.get('chunk_id', 'doc')
            
            chunks = self.chunk_text(text, source, base_chunk_id)
            all_chunks.extend(chunks)
        
        logger.info(f"Processed {len(documents)} documents into {len(all_chunks)} total chunks")
        return all_chunks




# Global chunker instance
chunker = TextChunker()
