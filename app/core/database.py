# Copyright 2024
# Directory: rag-openrouter/app/core/database.py

"""
Database connection and schema management using Supabase SDK.
Handles Supabase Postgres with pgvector extension for RAG operations.
"""

import logging
from typing import Dict, List, Any, Optional
from supabase import create_client, Client
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Database:
    """Supabase database operations manager for RAG functionality."""
    
    def __init__(self):
        """Initialize Supabase client."""
        self.supabase: Optional[Client] = None
        self._admin_client: Optional[Client] = None
    
    async def connect(self) -> None:
        """Initialize Supabase clients."""
        try:
            # Regular client with anon key (for future frontend compatibility)
            self.supabase = create_client(
                settings.supabase_url,
                settings.supabase_anon_key
            )
            
            # Admin client with service role key (for backend operations)
            self._admin_client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key
            )
            
            logger.info("Supabase clients initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase clients: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close Supabase connections (cleanup if needed)."""
        # Supabase clients don't need explicit disconnection
        logger.info("Supabase clients cleaned up")
    
    def get_client(self, admin: bool = True) -> Client:
        """
        Get Supabase client instance.
        
        Args:
            admin: If True, returns admin client with service role key.
                   If False, returns regular client with anon key.
        """
        if not self.supabase or not self._admin_client:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        return self._admin_client if admin else self.supabase
    
    async def initialize_schema(self) -> None:
        """
        Check if database schema is initialized.
        
        Note: The actual schema setup must be done manually in Supabase.
        Run the SQL script: sql/init_supabase.sql in your Supabase SQL Editor.
        """
        try:
            client = self.get_client(admin=True)
            
            # Check if the table exists and has the required structure
            result = client.table(settings.rag_table).select('id').limit(1).execute()
            
            if result.data is not None:
                logger.info(f"Database schema is properly initialized (table {settings.rag_table})")
                
                # Test the vector search function
                try:
                    stats_result = client.rpc(settings.rag_stats_function).execute()
                    if stats_result.data:
                        stats = stats_result.data[0]
                        logger.info(f"Database stats: {stats['total_chunks']} chunks, {stats['unique_sources']} sources")
                except Exception:
                    logger.warning(f"{settings.rag_stats_function} function not available - some features may not work")
                    
            else:
                logger.error("Database schema not initialized!")
                logger.error(
                    "Please run the SQL initialization script:\n"
                    "1. Open your Supabase project dashboard\n"
                    "2. Go to SQL Editor\n"
                    "3. Run the script: sql/init_supabase.sql\n"
                    "4. Restart your application"
                )
                
        except Exception as e:
            logger.error(f"Database schema check failed: {e}")
            logger.error(
                "Please ensure you've run sql/init_supabase.sql in your Supabase dashboard"
            )
    
    async def upsert_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """
        Upsert document chunks into the database using Supabase SDK.
        
        Args:
            chunks: List of chunk dictionaries with keys: chunk_id, source, text, embedding
            
        Returns:
            Number of chunks inserted
        """
        if not chunks:
            return 0
        
        try:
            client = self.get_client(admin=True)
            
            # Prepare data for Supabase
            chunk_data = []
            for chunk in chunks:
                chunk_data.append({
                    'chunk_id': chunk['chunk_id'],
                    'source': chunk['source'],
                    'text': chunk['text'],
                    'embedding': chunk['embedding']  # Supabase handles vector serialization
                })
            
            # Use upsert with on_conflict parameter
            result = client.table(settings.rag_table).upsert(
                chunk_data,
                on_conflict='chunk_id'
            ).execute()
            
            inserted_count = len(result.data) if result.data else 0
            logger.info(f"Upserted {inserted_count} chunks to database")
            return inserted_count
            
        except Exception as e:
            logger.error(f"Failed to upsert chunks: {e}")
            raise
    
    async def delete_stale_chunks(self, prefix: str, keep_chunk_ids: List[str]) -> int:
        """
        Delete chunks whose chunk_id starts with prefix and is not in keep_chunk_ids.
        
        Args:
            prefix: chunk_id prefix of the document (e.g. '<file-stem>__')
            keep_chunk_ids: chunk_ids of the current version, which are kept
            
        Returns:
            Number of chunks deleted
        """
        client = self.get_client(admin=True)
        keep = set(keep_chunk_ids)
        
        # LIKE treats '_' as a wildcard and may match extra rows, so confirm the exact prefix in Python
        result = client.table(settings.rag_table).select('chunk_id').like('chunk_id', f"{prefix}%").execute()
        stale = [
            row['chunk_id'] for row in (result.data or [])
            if row['chunk_id'].startswith(prefix) and row['chunk_id'] not in keep
        ]
        
        for start in range(0, len(stale), 100):
            client.table(settings.rag_table).delete().in_('chunk_id', stale[start:start + 100]).execute()
        
        logger.info(f"Deleted {len(stale)} stale chunks with prefix '{prefix}'")
        return len(stale)
    
    async def delete_project_chunks(self, slug: str) -> int:
        """
        Delete all chunks for a given project from Supabase.
        Matches by chunk_id prefix ('<slug>__') and source ('<slug>.json%').
        
        Args:
            slug: Project slug
            
        Returns:
            Number of chunks deleted
        """
        client = self.get_client(admin=True)
        prefix = f"{slug}__"
        
        # Match by chunk_id prefix
        result = client.table(settings.rag_table).select('chunk_id').like('chunk_id', f"{prefix}%").execute()
        stale = [
            row['chunk_id'] for row in (result.data or [])
            if row['chunk_id'].startswith(prefix)
        ]
        
        # Also check chunks where source matches slug.json
        try:
            source_result = client.table(settings.rag_table).select('chunk_id').like('source', f"{slug}.json%").execute()
            for row in (source_result.data or []):
                cid = row.get('chunk_id')
                if cid and cid not in stale:
                    stale.append(cid)
        except Exception as e:
            logger.warning(f"Could not query chunks by source for project '{slug}': {e}")
            
        for start in range(0, len(stale), 100):
            client.table(settings.rag_table).delete().in_('chunk_id', stale[start:start + 100]).execute()
            
        logger.info(f"Deleted {len(stale)} chunks for project '{slug}' from Supabase table '{settings.rag_table}'")
        return len(stale)
    
    async def vector_search(self, query_embedding: List[float], top_k: int = 6) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search using Supabase SDK.
        
        Args:
            query_embedding: Query vector embedding
            top_k: Number of results to return
            
        Returns:
            List of matching chunks with similarity scores
        """
        try:
            client = self.get_client(admin=True)
            
            # Use RPC call for vector similarity search
            # This requires creating a PostgreSQL function in Supabase
            # Over-fetch: with small LIMITs Postgres uses the approximate vector index,
            # which can miss the closest chunks; larger LIMITs get an exact scan.
            result = client.rpc(settings.rag_match_function, {
                'query_embedding': query_embedding,
                'match_count': max(top_k, 30)
            }).execute()
            
            if not result.data:
                logger.warning(f"Vector search returned no results (check {settings.rag_table} and {settings.rag_match_function})")
                return []
            
            results = sorted(result.data, key=lambda row: row['similarity'], reverse=True)[:top_k]
            logger.info(f"Vector search returned {len(results)} results")
            return results
                
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Check Supabase connection health."""
        try:
            client = self.get_client(admin=True)
            
            # Simple query to test connection
            result = client.table(settings.rag_table).select('id').limit(1).execute()
            
            return True  # If no exception, connection is healthy
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database instance
db = Database()