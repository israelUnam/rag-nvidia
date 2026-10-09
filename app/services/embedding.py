# Copyright 2024
# Directory: rag-openrouter/app/services/embedding.py

"""
Servicio de incrustación para generar incrustaciones de texto a través del Catálogo de API de NVIDIA.
Centrado exclusivamente en incrustaciones vectoriales para la recuperación RAG.
"""

import logging
from typing import List
from ..core.config import get_settings
from ..core.nvidia import create_nvidia_client

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingService:
    """Servicio para generar representaciones de texto mediante modelos alojados en NVIDIA."""
    
    def __init__(self):
        """Initialize the NVIDIA client for embeddings."""
        self.client = create_nvidia_client()
        self.embed_model = settings.nvidia_embed_model
        self.batch_size = settings.embed_batch_size
    
    async def embed_texts(self, texts: List[str], input_type: str = "passage") -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            input_type: "passage" for documents being indexed, "query" for search questions.
                NVIDIA retrieval models embed each kind differently.
            
        Returns:
            List of embedding vectors (settings.embedding_dimensions each)
        """
        embeddings: List[List[float]] = []
        try:
            for start in range(0, len(texts), self.batch_size):
                batch = texts[start:start + self.batch_size]
                response = self.client.embeddings.create(
                    model=self.embed_model,
                    input=batch,
                    encoding_format="float",
                    extra_body={"input_type": input_type, "truncate": "NONE"},
                )
                if not response.data:
                    raise RuntimeError(f"NVIDIA returned no embeddings for model {self.embed_model}")
                ordered = sorted(response.data, key=lambda item: item.index)
                embeddings.extend(item.embedding for item in ordered)
            
            if embeddings and len(embeddings[0]) != settings.embedding_dimensions:
                raise ValueError(
                    f"Embedding model {self.embed_model} returned {len(embeddings[0])} dimensions, "
                    f"but EMBEDDING_DIMENSIONS is {settings.embedding_dimensions}. "
                    "Update VECTOR(n) in sql/init_supabase.sql and EMBEDDING_DIMENSIONS to match."
                )
            
            logger.info(f"Generated embeddings for {len(texts)} texts with {self.embed_model}")
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
    
    async def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a single query.
        
        Args:
            query: Query text to embed
            
        Returns:
            Embedding vector
        """
        embeddings = await self.embed_texts([query], input_type="query")
        return embeddings[0]


# Global service instance
embedding_service = EmbeddingService()
