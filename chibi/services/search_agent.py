"""Centralized Search Agent Service for all RAG operations.

This service provides a unified interface for searching course content,
handling deduplication, and optionally synthesizing answers using LLM.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from ..agent.context_manager import ContextManagerAgent, ContextSource
    from ..agent.memory import ConversationMemory
    from ..content.course import Concept, Module
    from ..llm.manager import LLMManager

logger = logging.getLogger(__name__)


class SearchContextType(Enum):
    """Types of search context for different use cases."""

    ASSISTANT = "assistant"  # General Q&A - uses LLM synthesis
    QUIZ_GENERATION = "quiz_generation"  # Quiz generation - raw chunks
    QUIZ_EVALUATION = "quiz_evaluation"  # Answer evaluation - raw chunks
    LLM_QUIZ = "llm_quiz"  # LLM quiz challenge - raw chunks


@dataclass
class SearchResult:
    """Result from a search operation."""

    answer: str  # LLM-synthesized answer (empty if synthesis disabled)
    raw_context: str  # Formatted raw chunks
    sources: List["ContextSource"] = field(default_factory=list)
    chunk_ids: List[str] = field(default_factory=list)  # For deduplication tracking
    has_relevant_content: bool = False
    query: str = ""


class SearchAgentService:
    """Centralized search agent for all RAG operations.

    This service:
    1. Handles all RAG queries from tools (AssistantTool, QuizTool, etc.)
    2. Automatically excludes previously retrieved chunks (deduplication)
    3. Optionally synthesizes coherent answers using LLM (for assistant queries)
    4. Provides a unified interface for different search contexts
    """

    SYNTHESIS_SYSTEM_PROMPT = """You are a helpful teaching assistant. Your task is to answer the student's question based on the provided course content.

Guidelines:
- Be encouraging and supportive
- Start with intuition, analogies, or real-world examples before technical details
- Keep your response concise (2-4 sentences)
- Cite which module the information comes from when relevant
- If the content doesn't fully answer the question, acknowledge what you can answer and what's missing
- Use a friendly, conversational tone"""

    SYNTHESIS_USER_PROMPT = """COURSE CONTENT:
{context}

STUDENT QUESTION: {query}

Please provide a helpful answer based on the course content above."""

    def __init__(
        self,
        context_manager: "ContextManagerAgent",
        llm_manager: "LLMManager",
        conversation_memory: "ConversationMemory",
    ):
        """Initialize the search agent.

        Args:
            context_manager: Agent for RAG-based context retrieval
            llm_manager: Manager for LLM operations (synthesis)
            conversation_memory: Memory for tracking retrieved chunks
        """
        self.context_manager = context_manager
        self.llm_manager = llm_manager
        self.conversation_memory = conversation_memory

    async def search(
        self,
        query: str,
        context_type: SearchContextType,
        user_id: str,
        channel_id: str,
        module_id: Optional[str] = None,
        concept: Optional["Concept"] = None,
        module: Optional["Module"] = None,
    ) -> SearchResult:
        """Execute a search and optionally synthesize an answer.

        Args:
            query: The search query
            context_type: Type of search context (determines synthesis behavior)
            user_id: Discord user ID for deduplication tracking
            channel_id: Discord channel ID for deduplication tracking
            module_id: Optional module to filter results
            concept: Optional concept for targeted retrieval
            module: Optional module object for quiz-related searches

        Returns:
            SearchResult with answer (if synthesized), raw context, and metadata
        """
        # 1. Get excluded chunk IDs from conversation memory
        exclude_chunk_ids = self.conversation_memory.get_recent_chunk_ids(
            user_id=user_id,
            channel_id=channel_id,
            max_messages=5,
        )

        if exclude_chunk_ids:
            logger.debug(
                f"Search excluding {len(exclude_chunk_ids)} previously retrieved chunks"
            )

        # 2. Get context based on search type
        context_result = await self._get_context(
            query=query,
            context_type=context_type,
            module_id=module_id,
            concept=concept,
            module=module,
            exclude_chunk_ids=exclude_chunk_ids,
        )

        # 3. Synthesize answer if ASSISTANT type and has relevant content
        answer = ""
        if (
            context_type == SearchContextType.ASSISTANT
            and context_result.has_relevant_content
        ):
            answer = await self._synthesize_answer(query, context_result.context)

        logger.info(
            f"Search completed: type={context_type.value}, "
            f"chunks={context_result.total_chunks}, "
            f"synthesized={bool(answer)}"
        )

        return SearchResult(
            answer=answer,
            raw_context=context_result.context,
            sources=context_result.sources,
            chunk_ids=context_result.chunk_ids,
            has_relevant_content=context_result.has_relevant_content,
            query=query,
        )

    async def search_for_assistant(
        self,
        query: str,
        user_id: str,
        channel_id: str,
        module_id: Optional[str] = None,
    ) -> SearchResult:
        """Search for general assistant queries with LLM synthesis.

        Args:
            query: The user's question
            user_id: Discord user ID
            channel_id: Discord channel ID
            module_id: Optional module to focus on

        Returns:
            SearchResult with synthesized answer
        """
        return await self.search(
            query=query,
            context_type=SearchContextType.ASSISTANT,
            user_id=user_id,
            channel_id=channel_id,
            module_id=module_id,
        )

    async def search_for_quiz(
        self,
        concept: "Concept",
        module: "Module",
        user_id: str = "",
        channel_id: str = "",
    ) -> SearchResult:
        """Search for quiz generation context (raw chunks, no synthesis).

        Args:
            concept: The concept to generate quiz for
            module: The module containing the concept
            user_id: Discord user ID (optional for quiz, no deduplication needed)
            channel_id: Discord channel ID

        Returns:
            SearchResult with raw context for quiz generation
        """
        # Build query from concept
        query_parts = [concept.name]
        if concept.description:
            query_parts.append(concept.description)
        if concept.quiz_focus:
            query_parts.append(concept.quiz_focus)
        query = " ".join(query_parts)

        return await self.search(
            query=query,
            context_type=SearchContextType.QUIZ_GENERATION,
            user_id=user_id,
            channel_id=channel_id,
            module_id=module.id,
            concept=concept,
            module=module,
        )

    async def search_for_evaluation(
        self,
        question: str,
        concept_name: str,
        concept_description: str,
        user_id: str = "",
        channel_id: str = "",
        module_id: Optional[str] = None,
    ) -> SearchResult:
        """Search for quiz evaluation context (raw chunks, no synthesis).

        Args:
            question: The quiz question being evaluated
            concept_name: Name of the concept
            concept_description: Description of the concept
            user_id: Discord user ID
            channel_id: Discord channel ID
            module_id: Optional module to filter

        Returns:
            SearchResult with raw context for evaluation
        """
        query = f"{concept_name}: {question}"

        return await self.search(
            query=query,
            context_type=SearchContextType.QUIZ_EVALUATION,
            user_id=user_id,
            channel_id=channel_id,
            module_id=module_id,
        )

    async def search_for_llm_quiz(
        self,
        question: str,
        module: "Module",
        user_id: str = "",
        channel_id: str = "",
    ) -> SearchResult:
        """Search for LLM quiz challenge context (raw chunks, no synthesis).

        Args:
            question: The student's challenge question
            module: The module being challenged
            user_id: Discord user ID
            channel_id: Discord channel ID

        Returns:
            SearchResult with raw context for LLM quiz challenge
        """
        return await self.search(
            query=question,
            context_type=SearchContextType.LLM_QUIZ,
            user_id=user_id,
            channel_id=channel_id,
            module_id=module.id,
            module=module,
        )

    async def _get_context(
        self,
        query: str,
        context_type: SearchContextType,
        module_id: Optional[str],
        concept: Optional["Concept"],
        module: Optional["Module"],
        exclude_chunk_ids: set,
    ):
        """Get context from ContextManagerAgent based on search type.

        Args:
            query: Search query
            context_type: Type of search
            module_id: Optional module filter
            concept: Optional concept for quiz
            module: Optional module object
            exclude_chunk_ids: Chunk IDs to exclude

        Returns:
            ContextResult from context manager
        """
        if context_type == SearchContextType.QUIZ_GENERATION and concept and module:
            return await self.context_manager.get_context_for_quiz(
                concept=concept,
                module=module,
            )
        elif context_type == SearchContextType.QUIZ_EVALUATION:
            return await self.context_manager.get_context_for_evaluation(
                question=query,
                concept_name="",  # Not needed, query already has concept info
                concept_description="",
                module_id=module_id,
            )
        elif context_type == SearchContextType.LLM_QUIZ and module:
            return await self.context_manager.get_context_for_llm_quiz(
                question=query,
                module=module,
            )
        else:
            # Default: ASSISTANT or fallback
            return await self.context_manager.get_context_for_assistant(
                question=query,
                module_id=module_id,
                exclude_chunk_ids=exclude_chunk_ids,
            )

    async def _synthesize_answer(self, query: str, context: str) -> str:
        """Synthesize a coherent answer from context using LLM.

        Args:
            query: The user's question
            context: Retrieved course content

        Returns:
            Synthesized answer string
        """
        try:
            prompt = self.SYNTHESIS_USER_PROMPT.format(
                context=context,
                query=query,
            )

            response = await self.llm_manager.generate(
                prompt=prompt,
                system_prompt=self.SYNTHESIS_SYSTEM_PROMPT,
                max_tokens=512,
                temperature=0.7,
            )

            if response and response.content:
                return response.content.strip()

            logger.warning("Empty response from LLM synthesis")
            return ""

        except Exception as e:
            logger.error(f"Error synthesizing answer: {e}", exc_info=True)
            return ""
