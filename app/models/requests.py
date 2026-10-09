# Copyright 2024
# Directory: rag-openrouter/app/models/requests.py

"""
Request models for the RAG API endpoints.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """Individual document chunk for seeding."""
    chunk_id: str = Field(..., description="Unique identifier for the chunk")
    source: str = Field(..., description="Source URL or identifier")
    text: str = Field(..., description="Text content of the chunk")


class SeedRequest(BaseModel):
    """Request model for the /seed endpoint."""
    docs: Optional[List[DocumentChunk]] = Field(
        None, 
        description="Optional list of documents to seed. If omitted, uses default documents."
    )


class ProjectDocumentRequest(BaseModel):
    """Request model for replacing a project's document."""
    content: Optional[Union[Dict[str, Any], str]] = Field(
        None,
        description="New JSON or Markdown knowledge base of the project. If omitted, re-indexes the file already on the server."
    )


class CreateProjectRequest(BaseModel):
    """Request model for adding a project that is not in the knowledge base yet."""
    content: Union[Dict[str, Any], str] = Field(..., description="JSON or Markdown knowledge base of the new project")
    filename: Optional[str] = Field(
        None,
        description="Original file name. Its stem becomes the project slug (for example campana-valores.json o proyecto.md)."
    )


class AnswerRequest(BaseModel):
    """Request model for the /answer endpoint."""
    query: str = Field(..., description="User question to answer")
    top_k: Optional[int] = Field(
        6, 
        ge=1, 
        le=20, 
        description="Number of chunks to retrieve for context"
    )
