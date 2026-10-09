# Copyright 2024
# Directory: rag-openrouter/app/core/config.py

"""
Configuration management for the RAG application.
Handles environment variables and application settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Supabase Configuration
    supabase_url: str = Field(..., env="SUPABASE_URL")
    supabase_anon_key: str = Field(..., env="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(..., env="SUPABASE_SERVICE_ROLE_KEY")
    # Table and SQL functions created by sql/init_supabase.sql; each embedding model needs its own
    # table because vectors from different models (and dimensions) cannot be mixed
    rag_table: str = Field(default="rag_chunks_ies", env="RAG_TABLE")
    rag_match_function: str = Field(default="match_chunks_ies", env="RAG_MATCH_FUNCTION")
    rag_stats_function: str = Field(default="get_chunk_stats_ies", env="RAG_STATS_FUNCTION")
    
    # NVIDIA API Catalog (build.nvidia.com) configuration (chat + embeddings)
    nvidia_api_key: str = Field(..., min_length=1, env="NVIDIA_API_KEY")
    nvidia_base_url: str = Field(default="https://integrate.api.nvidia.com/v1", env="NVIDIA_BASE_URL")
    nvidia_model: str = Field(default="google/gemma-4-31b-it", env="NVIDIA_MODEL")
    # Comma-separated models tried in order if the main one fails or is rate-limited
    nvidia_fallback_models: str = Field(
        default="mistralai/mistral-large-2-instruct,nvidia/nemotron-3-super-120b-a12b",
        env="NVIDIA_FALLBACK_MODELS",
    )
    nvidia_embed_model: str = Field(default="nvidia/nemotron-3-embed-1b", env="NVIDIA_EMBED_MODEL")
    
    # Application Configuration
    environment: str = Field(default="development", env="ENVIRONMENT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # RAG Configuration
    default_top_k: int = Field(default=6)
    chunk_size: int = Field(default=400)  # Approximate tokens
    chunk_overlap: int = Field(default=60)  # 15% overlap
    temperature: float = Field(default=0.1)
    embed_batch_size: int = Field(default=32, env="EMBED_BATCH_SIZE")
    # Max input tokens per chunk sent to the embedding model; chunks are cut to stay below it
    embed_max_tokens: int = Field(default=512, env="EMBED_MAX_TOKENS")
    # Must match VECTOR(n) in sql/init_supabase.sql (nvidia/nemotron-3-embed-1b -> 2048)
    embedding_dimensions: int = Field(default=2048, env="EMBEDDING_DIMENSIONS")
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False
        # Old variables left in .env (e.g. OPENROUTER_*) must not stop the app from starting
        extra = "ignore"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance."""
    return settings
