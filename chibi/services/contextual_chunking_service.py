"""Contextual chunking service for enhanced RAG retrieval."""

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from ..llm.manager import LLMManager
    from .chunking import TextChunk

logger = logging.getLogger(__name__)


@dataclass
class ContextualChunkConfig:
    """Configuration for contextual chunking."""

    enabled: bool = True
    max_context_tokens: int = 100
    batch_size: int = 5
    batch_delay_seconds: float = 0.5
    fallback_on_error: bool = True
    temperature: float = 0.3  # Lower for more deterministic context


CONTEXTUAL_PROMPT_TEMPLATE = """<document>
{document_content}
</document>

Here is a chunk from the document:
<chunk>
{chunk_content}
</chunk>

Please provide a brief context (2-3 sentences, under 100 tokens) that situates this chunk within the document. The context should:
1. Identify key entities, topics, or concepts mentioned that need context
2. Explain what section or topic of the document this chunk belongs to
3. Note any important preceding information needed to understand this chunk

Provide ONLY the contextual summary, no additional explanation."""


class ContextualChunkingService:
    """Service for generating contextual summaries for text chunks.

    Uses an LLM to generate contextual information that situates
    each chunk within its source document, improving retrieval accuracy.
    """

    def __init__(
        self,
        llm_manager: "LLMManager",
        config: Optional[ContextualChunkConfig] = None,
    ):
        """Initialize the contextual chunking service.

        Args:
            llm_manager: LLM manager for generating context
            config: Optional configuration override
        """
        self.llm_manager = llm_manager
        self.config = config or ContextualChunkConfig()
        self._stats = {
            "total_chunks": 0,
            "successful_contexts": 0,
            "failed_contexts": 0,
        }

    async def generate_context(
        self,
        chunk_text: str,
        document_text: str,
        document_title: Optional[str] = None,
    ) -> Optional[str]:
        """Generate contextual summary for a single chunk.

        Args:
            chunk_text: The chunk to contextualize
            document_text: The full document content
            document_title: Optional title for the document

        Returns:
            Contextual summary or None if generation failed
        """
        if not self.config.enabled:
            return None

        # Truncate document if too long (keep beginning and end)
        max_doc_chars = 8000  # Reasonable context window
        if len(document_text) > max_doc_chars:
            half = max_doc_chars // 2
            document_text = (
                document_text[:half]
                + "\n\n[... content truncated ...]\n\n"
                + document_text[-half:]
            )

        prompt = CONTEXTUAL_PROMPT_TEMPLATE.format(
            document_content=document_text,
            chunk_content=chunk_text,
        )

        system_prompt = (
            "You are a precise document analyst. Generate brief, factual "
            "contextual summaries that help situate text chunks within their "
            "source documents. Be concise and focus on key identifying information."
        )

        if document_title:
            system_prompt += f"\n\nDocument title: {document_title}"

        try:
            response = await self.llm_manager.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=self.config.max_context_tokens,
                temperature=self.config.temperature,
            )

            if response and response.content:
                self._stats["successful_contexts"] += 1
                return response.content.strip()

        except Exception as e:
            logger.warning(f"Failed to generate context for chunk: {e}")
            self._stats["failed_contexts"] += 1

        return None

    async def contextualize_chunks(
        self,
        chunks: List["TextChunk"],
        document_text: str,
        document_title: Optional[str] = None,
    ) -> List["TextChunk"]:
        """Add contextual information to a list of chunks.

        Processes chunks in batches with rate limiting to avoid
        overwhelming the LLM provider.

        Args:
            chunks: List of TextChunk objects to contextualize
            document_text: The full document these chunks came from
            document_title: Optional title for better context

        Returns:
            List of TextChunk objects with context field populated
        """
        if not self.config.enabled:
            return chunks

        self._stats["total_chunks"] += len(chunks)

        # Process in batches
        for i in range(0, len(chunks), self.config.batch_size):
            batch = chunks[i : i + self.config.batch_size]

            # Process batch concurrently
            tasks = [
                self.generate_context(
                    chunk_text=chunk.text,
                    document_text=document_text,
                    document_title=document_title,
                )
                for chunk in batch
            ]

            contexts = await asyncio.gather(*tasks, return_exceptions=True)

            # Assign contexts to chunks
            for chunk, context in zip(batch, contexts):
                if isinstance(context, Exception):
                    logger.warning(f"Context generation error: {context}")
                    context = None
                chunk.context = context

            # Rate limiting delay between batches
            if i + self.config.batch_size < len(chunks):
                await asyncio.sleep(self.config.batch_delay_seconds)

        logger.info(
            f"Contextualized {len(chunks)} chunks: "
            f"{self._stats['successful_contexts']} success, "
            f"{self._stats['failed_contexts']} failed"
        )

        return chunks

    def get_stats(self) -> dict:
        """Get statistics about context generation."""
        return dict(self._stats)

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._stats = {
            "total_chunks": 0,
            "successful_contexts": 0,
            "failed_contexts": 0,
        }
