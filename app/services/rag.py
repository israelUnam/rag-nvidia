# Copyright 2024
# Directory: rag-openrouter/app/services/rag.py

"""
RAG (Retrieval-Augmented Generation) service implementation.
Orchestrates the complete RAG pipeline: chunk → embed → search → generate.
"""

import logging
import time
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Tuple
from ..core.database import db
from .embedding import embedding_service
from .chat import chat_service
from .chunker import chunker
import json
import shutil
from typing import Optional, Union
from ..data.default_documents import (
    DEFAULT_DOCUMENTS, DOCUMENTS_DIR, load_projects, parse_json_data,
    parse_markdown_data, extract_markdown_metadata, reload_documents
)

logger = logging.getLogger(__name__)


def _slug_from_filename(filename: Optional[str], project_name: str) -> str:
    """Turn an uploaded file name, or the project name, into a safe stem."""
    raw = Path(filename).name if filename else project_name
    for ext in (".jsonl", ".ndjson", ".json", ".markdown", ".md"):
        if raw.lower().endswith(ext):
            raw = raw[:-len(ext)]
            break
    stem = Path(raw).stem if Path(raw).suffix else raw
    normalized = unicodedata.normalize("NFKD", stem)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    if not slug:
        raise ValueError("No se pudo generar un nombre de archivo válido para el proyecto")
    if len(slug) > 120:
        slug = slug[:120].rstrip("-")
    return slug


class RAGService:
    """Main RAG service orchestrating the complete pipeline."""
    
    def __init__(self):
        """Initialize RAG service."""
        self.db = db
        self.embedding_service = embedding_service
        self.chat_service = chat_service
        self.chunker = chunker
    
    async def seed_documents(self, documents: List[Dict[str, str]] = None) -> int:
        """
        Seed the knowledge base with documents.
        
        Args:
            documents: Optional list of documents. If None, uses default documents.
            
        Returns:
            Number of chunks successfully inserted
        """
        start_time = time.time()
        
        # Use default documents if none provided
        if documents is None:
            documents = DEFAULT_DOCUMENTS
            logger.info("Using default documents for seeding")
        
        try:
            # Step 1: Chunk documents
            chunks = self.chunker.chunk_documents(documents)
            logger.info(f"Created {len(chunks)} chunks from {len(documents)} documents")
            
            # Step 2: Generate embeddings for all chunks
            texts = [chunk['text'] for chunk in chunks]
            embeddings = await self.embedding_service.embed_texts(texts)
            
            # Step 3: Combine chunks with embeddings
            for chunk, embedding in zip(chunks, embeddings):
                chunk['embedding'] = embedding
            
            # Step 4: Store in database
            inserted_count = await self.db.upsert_chunks(chunks)
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Seeding completed in {elapsed_ms}ms: {inserted_count} chunks inserted")
            
            return inserted_count
            
        except Exception as e:
            logger.error(f"Seeding failed: {e}")
            raise
    
    async def update_project_document(self, slug: str, content: Optional[Union[Dict[str, Any], str]] = None) -> Dict[str, Any]:
        """
        Replace a project's chunks in the database with a new version of its JSON or Markdown document.
        
        New chunks are upserted first and stale ones deleted afterwards, so a failure
        midway never leaves the project without data. The file on disk is only
        overwritten (keeping a .bak copy) after the database update succeeds.
        
        Args:
            slug: Project file name without extension (as returned by /projects)
            content: New JSON dict or Markdown string. If None, re-reads the current file from disk.
            
        Returns:
            Dictionary with slug, project name, documents, inserted and deleted counts
        """
        start_time = time.time()
        existing = {p['slug']: p for p in load_projects()}
        if slug not in existing:
            raise LookupError(f"Proyecto '{slug}' no encontrado")
        
        json_path = DOCUMENTS_DIR / f"{slug}.json"
        md_path = DOCUMENTS_DIR / f"{slug}.md"
        
        # Determine whether this project or incoming content is Markdown
        is_md = isinstance(content, str) or (isinstance(content, dict) and "markdown" in content) or md_path.exists()
        
        if is_md and (md_path.exists() or not json_path.exists()):
            path = md_path
            raw_text = content if isinstance(content, str) else (
                (content.get("markdown") if isinstance(content, dict) else None)
                if content is not None else (path.read_text(encoding="utf-8") if path.exists() else "")
            )
            if not raw_text or not raw_text.strip():
                raise ValueError("El documento Markdown no tiene contenido para indexar")
            
            meta = extract_markdown_metadata(raw_text, slug)
            nombre = meta.get("nombre", slug)
            documents = parse_markdown_data(raw_text, slug, path.name)
            if not documents:
                raise ValueError("El documento Markdown no tiene secciones para indexar")
            
            chunks = self.chunker.chunk_documents(documents)
            embeddings = await self.embedding_service.embed_texts([chunk['text'] for chunk in chunks])
            for chunk, embedding in zip(chunks, embeddings):
                chunk['embedding'] = embedding

            inserted = await self.db.upsert_chunks(chunks)
            deleted = await self.db.delete_stale_chunks(f"{slug}__", [chunk['chunk_id'] for chunk in chunks])

            if content is not None:
                if path.exists():
                    shutil.copyfile(path, path.with_suffix(".md.bak"))
                path.write_text(raw_text, encoding="utf-8")
            reload_documents()

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Project '{slug}' updated from Markdown in {elapsed_ms}ms: {inserted} chunks upserted, {deleted} deleted")
            return {
                'slug': slug,
                'nombre': nombre,
                'documents': len(documents),
                'inserted': inserted,
                'deleted': deleted,
                'latency_ms': elapsed_ms,
            }
        
        # Standard JSON project handling
        path = json_path
        data = content if content is not None else json.loads(path.read_text(encoding="utf-8"))
        
        project = (data.get("baseConocimientos") or {}).get("proyecto") if isinstance(data, dict) else None
        if not project:
            raise ValueError("The document must contain baseConocimientos.proyecto")
        current_id = existing[slug].get('id')
        if current_id is not None and project.get('id') is not None and str(project['id']) != str(current_id):
            raise ValueError(
                f"The document belongs to project id {project['id']}, but '{slug}' is project id {current_id}"
            )
        
        documents = parse_json_data(data, slug, path.name)
        if not documents:
            raise ValueError("The document has no content to index")
        
        chunks = self.chunker.chunk_documents(documents)
        embeddings = await self.embedding_service.embed_texts([chunk['text'] for chunk in chunks])
        for chunk, embedding in zip(chunks, embeddings):
            chunk['embedding'] = embedding
        
        inserted = await self.db.upsert_chunks(chunks)
        deleted = await self.db.delete_stale_chunks(f"{slug}__", [chunk['chunk_id'] for chunk in chunks])
        
        if content is not None:
            shutil.copyfile(path, path.with_suffix(".json.bak"))
            path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        reload_documents()
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Project '{slug}' updated in {elapsed_ms}ms: {inserted} chunks upserted, {deleted} deleted")
        return {
            'slug': slug,
            'nombre': project.get('nombre', slug),
            'documents': len(documents),
            'inserted': inserted,
            'deleted': deleted,
            'latency_ms': elapsed_ms,
        }

    async def create_project_document(self, content: Union[Dict[str, Any], str], filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Index a new project and save its JSON or Markdown file.

        The database is updated first. If saving the file fails afterwards, the
        chunks just inserted are removed so the project is not left half-created.
        """
        start_time = time.time()
        is_md = isinstance(content, str) or (filename and filename.lower().endswith((".md", ".markdown")))
        if not is_md and isinstance(content, dict) and ("markdown" in content or "contenido_md" in content):
            is_md = True

        if is_md:
            raw_text = content if isinstance(content, str) else str(
                (content or {}).get("markdown") or (content or {}).get("contenido_md") or ""
            )
            if not raw_text.strip():
                raise ValueError("El documento Markdown está vacío o no contiene texto")
            
            meta = extract_markdown_metadata(raw_text, Path(filename or "proyecto").stem)
            nombre = str(meta.get("nombre") or "").strip()
            if not nombre:
                raise ValueError("No se pudo determinar el nombre del proyecto en el documento Markdown")

            slug = _slug_from_filename(filename, nombre)
            path = DOCUMENTS_DIR / f"{slug}.md"
            if path.exists() or (DOCUMENTS_DIR / f"{slug}.json").exists():
                raise FileExistsError(
                    f"Ya existe un proyecto con el archivo '{slug}'. Usa Actualizar en esa tarjeta."
                )

            project_id = meta.get("id")
            if project_id is not None:
                for existing in load_projects():
                    if existing.get("id") is not None and str(existing["id"]) == str(project_id):
                        raise FileExistsError(
                            f'Ya existe el proyecto "{existing["nombre"]}" con id {project_id}. '
                            "Usa Actualizar en esa tarjeta."
                        )

            documents = parse_markdown_data(raw_text, slug, path.name)
            if not documents:
                raise ValueError("El documento Markdown no tiene contenido para indexar")

            chunks = self.chunker.chunk_documents(documents)
            embeddings = await self.embedding_service.embed_texts([chunk["text"] for chunk in chunks])
            for chunk, embedding in zip(chunks, embeddings):
                chunk["embedding"] = embedding

            inserted = await self.db.upsert_chunks(chunks)
            try:
                with path.open("x", encoding="utf-8") as handle:
                    handle.write(raw_text)
            except FileExistsError:
                await self.db.delete_stale_chunks(f"{slug}__", [])
                raise FileExistsError(
                    f"Ya existe un proyecto con el archivo '{slug}.md'. Usa Actualizar en esa tarjeta."
                )
            except Exception:
                await self.db.delete_stale_chunks(f"{slug}__", [])
                raise
            reload_documents()

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Project '{slug}' created from Markdown in {elapsed_ms}ms: {inserted} chunks inserted")
            return {
                "slug": slug,
                "nombre": nombre,
                "documents": len(documents),
                "inserted": inserted,
                "deleted": 0,
                "latency_ms": elapsed_ms,
            }

        # Otherwise JSON document
        project = (content.get("baseConocimientos") or {}).get("proyecto") if isinstance(content, dict) else None
        if not isinstance(project, dict):
            raise ValueError("The document must contain baseConocimientos.proyecto")

        nombre = str(project.get("nombre") or "").strip()
        if not nombre:
            raise ValueError("The document must contain baseConocimientos.proyecto.nombre")

        slug = _slug_from_filename(filename, nombre)
        path = DOCUMENTS_DIR / f"{slug}.json"
        if path.exists() or (DOCUMENTS_DIR / f"{slug}.md").exists():
            raise FileExistsError(
                f"Ya existe un proyecto con el archivo '{slug}'. Usa Actualizar en esa tarjeta."
            )

        project_id = project.get("id")
        if project_id is not None:
            for existing in load_projects():
                if existing.get("id") is not None and str(existing["id"]) == str(project_id):
                    raise FileExistsError(
                        f'Ya existe el proyecto "{existing["nombre"]}" con id {project_id}. '
                        "Usa Actualizar en esa tarjeta."
                    )

        documents = parse_json_data(content, slug, path.name)
        if not documents:
            raise ValueError("The document has no content to index")

        chunks = self.chunker.chunk_documents(documents)
        embeddings = await self.embedding_service.embed_texts([chunk["text"] for chunk in chunks])
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding

        inserted = await self.db.upsert_chunks(chunks)
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(content, ensure_ascii=False, indent=2))
        except FileExistsError:
            await self.db.delete_stale_chunks(f"{slug}__", [])
            raise FileExistsError(
                f"Ya existe un proyecto con el archivo '{slug}.json'. Usa Actualizar en esa tarjeta."
            )
        except Exception:
            await self.db.delete_stale_chunks(f"{slug}__", [])
            raise
        reload_documents()

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Project '{slug}' created in {elapsed_ms}ms: {inserted} chunks inserted")
        return {
            "slug": slug,
            "nombre": nombre,
            "documents": len(documents),
            "inserted": inserted,
            "deleted": 0,
            "latency_ms": elapsed_ms,
        }

    async def delete_project(self, slug: str) -> Dict[str, Any]:
        """
        Delete a project from Supabase database and filesystem.
        
        Args:
            slug: Project file name without extension
            
        Returns:
            Dictionary with slug, project name, deleted chunks count, and latency
        """
        start_time = time.time()
        existing = {p['slug']: p for p in load_projects()}
        if slug not in existing:
            raise LookupError(f"Proyecto '{slug}' no encontrado")
        
        project_info = existing[slug]
        nombre = project_info.get('nombre', slug)
        
        # 1. Delete all chunks belonging to this project in Supabase
        deleted = await self.db.delete_project_chunks(slug)
        
        # 2. Delete JSON and MD files and backup copies on disk if they exist
        for candidate in (
            DOCUMENTS_DIR / f"{slug}.json",
            DOCUMENTS_DIR / f"{slug}.json.bak",
            DOCUMENTS_DIR / f"{slug}.md",
            DOCUMENTS_DIR / f"{slug}.md.bak",
        ):
            if candidate.exists():
                candidate.unlink()
            
        # 3. Reload in-memory document cache
        reload_documents()
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Project '{slug}' deleted in {elapsed_ms}ms: {deleted} chunks removed")
        return {
            'slug': slug,
            'nombre': nombre,
            'deleted': deleted,
            'latency_ms': elapsed_ms,
        }
    
    async def answer_query(self, query: str, top_k: int = 6) -> Dict[str, Any]:
        """
        Process a query through the complete RAG pipeline.
        
        Args:
            query: User's question
            top_k: Number of chunks to retrieve
            
        Returns:
            Dictionary with answer, citations, and debug info
        """
        start_time = time.time()
        
        try:
            # Step 1: Generate query embedding
            query_embedding = await self.embedding_service.embed_query(query)
            
            # Step 2: Vector similarity search
            search_results = await self.db.vector_search(query_embedding, top_k)
            
            if not search_results:
                return {
                    'text': "I don't have enough information to answer your question. Could you please rephrase or provide more context?",
                    'citations': [],
                    'debug': {
                        'top_doc_ids': [],
                        'latency_ms': int((time.time() - start_time) * 1000)
                    }
                }
            
            # Step 3: Deduplicate and prepare context
            context_blocks = self._prepare_context(search_results)
            
            # Step 4: Generate answer
            answer_text = await self.chat_service.generate_answer(query, context_blocks)
            # Some models cite with full-width brackets 【id】 instead of [id]
            answer_text = re.sub(r'【([^】]+)】', r'[\1]', answer_text)
            
            # Step 5: Extract citations from answer
            citations = self._extract_citations(answer_text, context_blocks)
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            result = {
                'text': answer_text,
                'citations': citations,
                'debug': {
                    'top_doc_ids': [block['chunk_id'] for block in context_blocks],
                    'latency_ms': elapsed_ms
                }
            }
            
            logger.info(f"Query processed in {elapsed_ms}ms with {len(citations)} citations")
            return result
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {
                'text': f"I encountered an error while processing your question: {str(e)}",
                'citations': [],
                'debug': {
                    'top_doc_ids': [],
                    'latency_ms': int((time.time() - start_time) * 1000)
                }
            }
    
    def _prepare_context(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prepare context blocks from search results, dropping duplicate chunks.
        
        Several chunks from the same document are allowed, since long documents
        are split into many chunks and the answer may span more than one.
        
        Args:
            search_results: Raw search results from database
            
        Returns:
            Processed context blocks
        """
        seen_chunk_ids = set()
        context_blocks = []
        
        for result in search_results:
            chunk_id = result.get('chunk_id', '')
            
            if chunk_id not in seen_chunk_ids:
                context_blocks.append(result)
                seen_chunk_ids.add(chunk_id)
            
            # Limit to reasonable context size
            if len(context_blocks) >= 6:
                break
        
        logger.info(f"Prepared {len(context_blocks)} unique context blocks")
        return context_blocks
    
    def _extract_citations(self, answer_text: str, context_blocks: List[Dict[str, Any]]) -> List[str]:
        """
        Extract citation chunk_ids from the generated answer.
        
        Args:
            answer_text: Generated answer text
            context_blocks: Context blocks that were provided
            
        Returns:
            List of chunk_ids that were cited
        """
        # Find all citations in format [chunk_id]
        citation_pattern = r'\[([^\]]+)\]'
        found_citations = re.findall(citation_pattern, answer_text)
        
        # Filter to only include valid chunk_ids from context
        valid_chunk_ids = {block['chunk_id'] for block in context_blocks}
        valid_citations = [cite for cite in found_citations if cite in valid_chunk_ids]
        
        # Remove duplicates while preserving order
        unique_citations = []
        for cite in valid_citations:
            if cite not in unique_citations:
                unique_citations.append(cite)
        
        return unique_citations


# Global RAG service instance
rag_service = RAGService()
