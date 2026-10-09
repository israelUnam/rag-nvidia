# Copyright 2024
# Directory: rag-openrouter/app/services/chat.py

"""
Chat completion service for generating RAG responses through the NVIDIA API Catalog.
"""

import logging
import re
from typing import List, Dict, Any
from ..core.config import get_settings
from ..core.nvidia import create_nvidia_client

logger = logging.getLogger(__name__)
settings = get_settings()


class ChatService:
    """Service for chat completions using NVIDIA-hosted models."""
    
    def __init__(self):
        """Initialize the NVIDIA chat client."""
        self.provider = "nvidia"
        self.client = create_nvidia_client()
        self.model = settings.nvidia_model
        fallbacks = [m.strip() for m in settings.nvidia_fallback_models.split(",") if m.strip()]
        self.models = [self.model] + [m for m in fallbacks if m != self.model]
        
        logger.info(f"Initialized chat service with {self.provider} ({', '.join(self.models)})")
    
    async def generate_answer(self, query: str, context_blocks: List[Dict[str, Any]]) -> str:
        """
        Generate RAG answer using context blocks.
        
        Args:
            query: User's question
            context_blocks: Retrieved chunks with metadata
            
        Returns:
            Generated answer with citations
        """
        # Build context string with citations
        context_parts = []
        for block in context_blocks:
            chunk_id = block.get('chunk_id', 'unknown')
            text = block.get('text', '')
            context_parts.append(f"[{chunk_id}] {text}")
        
        context = "\n\n".join(context_parts)
        
        system_prompt = """You are a helpful AI assistant for customer support that answers questions based on provided context.

                            IMPORTANT RULES:
                            1. For questions about policies, returns, shipping, sizing, or support: Answer ONLY using the provided context and include citations
                            2. For general greetings or casual conversation: You can respond naturally and friendly
                            3. For questions outside your knowledge base: Politely redirect to relevant policies or suggest contacting support
                            4. Always include citations [chunk_id] when using context information
                            5. Be concise but comprehensive
                            6. Maintain a helpful, professional tone"""

        user_prompt = f"""Context:
                        {context}

                        Question: {query}

                        Please provide an answer based on the context above, including appropriate citations."""

        # Free models are often rate-limited, and reasoning models can spend the whole
        # token budget thinking and return empty content, so try each model in turn.
        last_error = None
        for model in self.models:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=settings.temperature,
                    max_tokens=4000,
                )
                choice = response.choices[0] if response.choices else None
                answer = (choice.message.content or "") if choice else ""
                # Reasoning models may put their thinking inline before the answer
                answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.S).strip()
                
                if answer:
                    logger.info(f"Generated answer using {self.provider} ({getattr(response, 'model', model)})")
                    return answer
                
                last_error = f"{model} returned an empty answer (finish_reason={choice and choice.finish_reason})"
                logger.warning(last_error)
                
            except Exception as e:
                last_error = f"{model}: {e}"
                logger.warning(f"Model {model} failed: {e}")
        
        logger.error(f"Failed to generate answer with any model. Last error: {last_error}")
        return "I couldn't generate an answer. All configured models failed or are rate-limited; please try again shortly."


# Global service instance
chat_service = ChatService()
