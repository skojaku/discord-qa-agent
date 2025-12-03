"""Context Manager Agent for RAG-based context retrieval.

This agent provides centralized context retrieval for all tools,
using RAG to find relevant course content based on the query type.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..content.course import Concept, Course, Module
    from ..services.embedding_service import EmbeddingService
    from ..services.rag_service import RAGService

logger = logging.getLogger(__name__)


class ContextType(Enum):
    """Types of context retrieval for different use cases."""

    QUIZ_GENERATION = "quiz_generation"  # Context for generating quiz questions
    ANSWER_EVALUATION = "answer_evaluation"  # Context for evaluating answers
    LLM_QUIZ_CHALLENGE = "llm_quiz_challenge"  # Context for LLM quiz challenge
    GENERAL_ASSISTANT = "general_assistant"  # Context for general Q&A


@dataclass
class ContextSource:
    """A source of context information."""

    source_id: str
    source_name: str
    content: str
    relevance_score: float = 0.0
    chunk_id: str = ""  # Unique ID for deduplication across searches


@dataclass
class ContextResult:
    """Result of a context retrieval operation."""

    context: str  # Combined context string
    sources: List[ContextSource] = field(default_factory=list)
    query: str = ""
    context_type: ContextType = ContextType.GENERAL_ASSISTANT
    total_chunks: int = 0
    has_relevant_content: bool = False

    @property
    def source_names(self) -> List[str]:
        """Get list of unique source names."""
        return list(set(s.source_name for s in self.sources))

    @property
    def chunk_ids(self) -> List[str]:
        """Get list of chunk IDs for deduplication."""
        return [s.chunk_id for s in self.sources if s.chunk_id]


class ContextManagerAgent:
    """Agent that retrieves and manages context for tools.

    This agent centralizes RAG-based context retrieval, providing
    optimized context for different use cases (quiz generation,
    answer evaluation, LLM quiz challenge, general Q&A).
    """

    def __init__(
        self,
        rag_service: "RAGService",
        embedding_service: "EmbeddingService",
        course: "Course",
        default_top_k: int = 5,
        min_similarity: float = 0.3,
    ):
        """Initialize the context manager.

        Args:
            rag_service: Service for RAG retrieval
            embedding_service: Service for generating embeddings
            course: Course object with modules and concepts
            default_top_k: Default number of chunks to retrieve
            min_similarity: Minimum similarity threshold
        """
        self.rag_service = rag_service
        self.embedding_service = embedding_service
        self.course = course
        self.default_top_k = default_top_k
        self.min_similarity = min_similarity

    async def get_context(
        self,
        query: str,
        context_type: ContextType = ContextType.GENERAL_ASSISTANT,
        module_id: Optional[str] = None,
        concept: Optional["Concept"] = None,
        top_k: Optional[int] = None,
        exclude_chunk_ids: Optional[set] = None,
    ) -> ContextResult:
        """Retrieve context based on query and context type.

        Args:
            query: The search query or topic
            context_type: Type of context to retrieve
            module_id: Optional module to filter results
            concept: Optional concept for more targeted retrieval
            top_k: Override default number of chunks
            exclude_chunk_ids: Optional set of chunk IDs to exclude (already retrieved)

        Returns:
            ContextResult with retrieved context
        """
        if top_k is None:
            top_k = self._get_top_k_for_type(context_type)

        # Build enhanced query based on context type
        enhanced_query = self._enhance_query(query, context_type, concept)

        # Check if RAG service is available
        if self.rag_service is None:
            logger.warning("RAG service not available")
            return self._build_fallback_context(query, context_type, module_id, concept)

        try:
            is_ready = await self.rag_service.is_ready()
            if not is_ready:
                logger.warning("RAG service not ready")
                return self._build_fallback_context(
                    query, context_type, module_id, concept
                )

            # Retrieve using RAG
            result = await self.rag_service.retrieve(
                query=enhanced_query,
                source_id=module_id,
                top_k=top_k,
                exclude_chunk_ids=exclude_chunk_ids,
            )

            if not result.chunks:
                logger.debug(f"No RAG results for query: {query[:50]}")
                return self._build_fallback_context(
                    query, context_type, module_id, concept
                )

            # Convert to ContextResult
            sources = [
                ContextSource(
                    source_id=chunk.source_id,
                    source_name=chunk.source_name,
                    content=chunk.text,
                    relevance_score=chunk.similarity_score,
                    chunk_id=chunk.chunk_id,
                )
                for chunk in result.chunks
            ]

            # Format context based on context type
            formatted_context = self._format_context(
                sources, context_type, concept
            )

            logger.info(
                f"Context retrieved for {context_type.value}: "
                f"{len(sources)} chunks from {len(set(s.source_name for s in sources))} sources"
            )

            return ContextResult(
                context=formatted_context,
                sources=sources,
                query=query,
                context_type=context_type,
                total_chunks=len(sources),
                has_relevant_content=True,
            )

        except Exception as e:
            logger.error(f"Context retrieval error: {e}", exc_info=True)
            return self._build_fallback_context(query, context_type, module_id, concept)

    async def get_context_for_quiz(
        self,
        concept: "Concept",
        module: "Module",
        include_similar_concepts: bool = True,
    ) -> ContextResult:
        """Get context specifically for quiz question generation.

        Args:
            concept: The concept to quiz on
            module: The module containing the concept
            include_similar_concepts: Whether to include related concepts

        Returns:
            ContextResult optimized for quiz generation
        """
        # Build query from concept
        query_parts = [concept.name]
        if concept.description:
            query_parts.append(concept.description)
        if concept.quiz_focus:
            query_parts.append(concept.quiz_focus)

        query = " ".join(query_parts)

        return await self.get_context(
            query=query,
            context_type=ContextType.QUIZ_GENERATION,
            module_id=module.id,
            concept=concept,
            top_k=5,
        )

    async def get_context_for_evaluation(
        self,
        question: str,
        concept_name: str,
        concept_description: str,
        module_id: Optional[str] = None,
    ) -> ContextResult:
        """Get context for evaluating a quiz answer.

        Args:
            question: The quiz question
            concept_name: Name of the concept
            concept_description: Description of the concept
            module_id: Optional module to filter

        Returns:
            ContextResult optimized for answer evaluation
        """
        # Combine question and concept for better retrieval
        query = f"{concept_name}: {question}"

        return await self.get_context(
            query=query,
            context_type=ContextType.ANSWER_EVALUATION,
            module_id=module_id,
            top_k=3,  # Fewer chunks for evaluation
        )

    async def get_context_for_llm_quiz(
        self,
        question: str,
        module: "Module",
    ) -> ContextResult:
        """Get context for LLM quiz challenge.

        Args:
            question: The student's question
            module: The module being challenged

        Returns:
            ContextResult optimized for LLM quiz challenge
        """
        return await self.get_context(
            query=question,
            context_type=ContextType.LLM_QUIZ_CHALLENGE,
            module_id=module.id,
            top_k=7,  # More chunks for challenge context
        )

    async def get_context_for_assistant(
        self,
        question: str,
        module_id: Optional[str] = None,
        exclude_chunk_ids: Optional[set] = None,
    ) -> ContextResult:
        """Get context for the general assistant.

        Args:
            question: The user's question
            module_id: Optional module to focus on
            exclude_chunk_ids: Optional set of chunk IDs to exclude (already retrieved)

        Returns:
            ContextResult optimized for general Q&A
        """
        return await self.get_context(
            query=question,
            context_type=ContextType.GENERAL_ASSISTANT,
            module_id=module_id,
            top_k=5,
            exclude_chunk_ids=exclude_chunk_ids,
        )

    def _get_top_k_for_type(self, context_type: ContextType) -> int:
        """Get recommended top_k for each context type."""
        return {
            ContextType.QUIZ_GENERATION: 5,
            ContextType.ANSWER_EVALUATION: 3,
            ContextType.LLM_QUIZ_CHALLENGE: 7,
            ContextType.GENERAL_ASSISTANT: 5,
        }.get(context_type, self.default_top_k)

    def _enhance_query(
        self,
        query: str,
        context_type: ContextType,
        concept: Optional["Concept"],
    ) -> str:
        """Enhance query based on context type."""
        enhanced = query

        if concept:
            # Add concept information for better retrieval
            if concept.name not in query:
                enhanced = f"{concept.name}: {enhanced}"

        if context_type == ContextType.QUIZ_GENERATION:
            # Add quiz-specific terms
            enhanced = f"quiz question about {enhanced}"
        elif context_type == ContextType.ANSWER_EVALUATION:
            # Focus on factual content
            enhanced = f"facts and definitions: {enhanced}"

        return enhanced

    def _format_context(
        self,
        sources: List[ContextSource],
        context_type: ContextType,
        concept: Optional["Concept"],
    ) -> str:
        """Format context based on context type."""
        if not sources:
            return ""

        parts = []

        # Add concept information if available
        if concept and context_type in (
            ContextType.QUIZ_GENERATION,
            ContextType.ANSWER_EVALUATION,
        ):
            parts.append(f"**Concept: {concept.name}**")
            if concept.description:
                parts.append(f"Description: {concept.description}")
            if concept.quiz_focus:
                parts.append(f"Focus: {concept.quiz_focus}")
            parts.append("")

        # Group by source
        sources_by_name = {}
        for source in sources:
            if source.source_name not in sources_by_name:
                sources_by_name[source.source_name] = []
            sources_by_name[source.source_name].append(source)

        # Add content from each source
        for source_name, source_list in sources_by_name.items():
            parts.append(f"--- From {source_name} ---")
            for source in source_list:
                parts.append(source.content.strip())
            parts.append("")

        return "\n".join(parts).strip()

    def _build_fallback_context(
        self,
        query: str,
        context_type: ContextType,
        module_id: Optional[str],
        concept: Optional["Concept"],
    ) -> ContextResult:
        """Build fallback context when RAG is not available."""
        parts = []
        sources = []

        # Add concept information if available
        if concept:
            parts.append(f"**Concept: {concept.name}**")
            if concept.description:
                parts.append(f"Description: {concept.description}")
            if concept.quiz_focus:
                parts.append(f"Focus: {concept.quiz_focus}")
            parts.append("")

        # Add module information if specified
        if module_id:
            module = self.course.get_module(module_id)
            if module:
                parts.append(f"**Module: {module.name}**")
                if module.description:
                    parts.append(module.description)
                all_content = module.get_all_content()
                if all_content:
                    # Truncate module content for fallback
                    content_preview = all_content[:2000]
                    if len(all_content) > 2000:
                        content_preview += "..."
                    parts.append(content_preview)

                sources.append(
                    ContextSource(
                        source_id=module.id,
                        source_name=module.name,
                        content=all_content,
                        relevance_score=0.5,
                    )
                )

        # Add course overview if no specific module
        if not module_id:
            parts.append(f"**Course: {self.course.name}**")
            if self.course.description:
                parts.append(self.course.description)

            # Add module list
            parts.append("\nAvailable Modules:")
            for module in self.course.modules[:5]:
                parts.append(f"- {module.name}: {module.description or 'No description'}")

        context = "\n".join(parts).strip()

        return ContextResult(
            context=context,
            sources=sources,
            query=query,
            context_type=context_type,
            total_chunks=len(sources),
            has_relevant_content=bool(sources),
        )


def create_context_manager(
    rag_service: "RAGService",
    embedding_service: "EmbeddingService",
    course: "Course",
) -> ContextManagerAgent:
    """Create a ContextManagerAgent instance.

    Args:
        rag_service: RAG service for retrieval
        embedding_service: Embedding service
        course: Course object

    Returns:
        Configured ContextManagerAgent
    """
    return ContextManagerAgent(
        rag_service=rag_service,
        embedding_service=embedding_service,
        course=course,
    )
