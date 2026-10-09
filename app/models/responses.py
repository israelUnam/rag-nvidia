# Copyright 2024
# Directory: rag-openrouter/app/models/responses.py

"""
Response models for the RAG API endpoints.
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field


class SeedResponse(BaseModel):
    """Response model for the /seed endpoint."""
    inserted: int = Field(..., description="Number of chunks successfully inserted")


class ProjectDocumentResponse(BaseModel):
    """Response model for replacing a project's document."""
    slug: str = Field(..., description="Project file name without .json")
    nombre: str = Field(..., description="Project name")
    documents: int = Field(..., description="Sections / work packages indexed")
    inserted: int = Field(..., description="Chunks inserted or replaced")
    deleted: int = Field(..., description="Old chunks removed because they no longer exist")
    latency_ms: int = Field(..., description="Total processing time in milliseconds")


class DeleteProjectResponse(BaseModel):
    """Response model for deleting a project."""
    slug: str = Field(..., description="Project file name without .json")
    nombre: str = Field(..., description="Project name")
    deleted: int = Field(..., description="Number of chunks deleted from Supabase")
    latency_ms: int = Field(..., description="Total processing time in milliseconds")


class DebugInfo(BaseModel):
    """Debug information for RAG responses."""
    top_doc_ids: List[str] = Field(..., description="IDs of retrieved chunks")
    latency_ms: int = Field(..., description="Total processing time in milliseconds")


class AnswerResponse(BaseModel):
    """Response model for the /answer endpoint."""
    text: str = Field(..., description="Generated answer with inline citations")
    citations: List[str] = Field(..., description="List of chunk IDs used as sources")
    debug: DebugInfo = Field(..., description="Debug information")


class HealthResponse(BaseModel):
    """Response model for the /healthz endpoint."""
    status: str = Field(..., description="Health status")
    database_connected: bool = Field(..., description="Database connection status")


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error message")
    detail: str = Field(..., description="Detailed error information")
