"""Service for handling Q&A interactions."""

import logging
from dataclasses import dataclass
from typing import Optional

from .base import BaseService
from ..prompts.templates import PromptTemplates

logger = logging.getLogger(__name__)


@dataclass
class AskResponse:
    """Response from ask service."""

    content: str
    module_id: str
    success: bool
    error_message: Optional[str] = None


class AskService(BaseService):
    """Service for handling Q&A interactions."""

    async def answer_question(
        self,
        user_discord_id: str,
        username: str,
        question: str,
        module_id: Optional[str] = None,
    ) -> AskResponse:
        """Process a question and generate an answer.

        Args:
            user_discord_id: Discord user ID
            username: User's display name
            question: The question to answer
            module_id: Optional module ID to contextualize the answer

        Returns:
            AskResponse with the answer content or error
        """
        # Get or create user
        user = await self.repository.get_or_create_user(
            discord_id=user_discord_id,
            username=username,
        )

        # Build context
        module_context = self._build_module_context(module_id)
        student_context = await self._build_student_context(user.id)

        # Build system prompt
        system_prompt = PromptTemplates.get_system_prompt(
            module_name=module_context.get("name", ""),
            module_description=module_context.get("description", ""),
            module_content=module_context.get("content", ""),
            concept_list=module_context.get("concept_list", ""),
            mastery_summary=student_context.get("mastery_summary", "No data yet"),
            recent_topics=student_context.get("recent_topics", "None"),
        )

        # Generate response
        response = await self.llm_manager.generate(
            prompt=question,
            system_prompt=system_prompt,
            max_tokens=self.config.llm.max_tokens,
            temperature=self.config.llm.temperature,
        )

        if not response:
            return AskResponse(
                content="",
                module_id=module_id or "general",
                success=False,
                error_message=self.llm_manager.get_error_message(),
            )

        # Log interaction
        await self.repository.log_interaction(
            user_id=user.id,
            module_id=module_id or "general",
            question=question,
            response=response.content,
        )

        logger.info(
            f"Answered question from {username} about module {module_id or 'general'}"
        )

        return AskResponse(
            content=response.content,
            module_id=module_id or "general",
            success=True,
        )

    def _build_module_context(self, module_id: Optional[str]) -> dict:
        """Build module context for prompt.

        Args:
            module_id: Optional module ID

        Returns:
            Dictionary with module context
        """
        if not module_id or not self.course:
            return {}

        module = self.course.get_module(module_id)
        if not module:
            return {}

        return {
            "name": module.name,
            "description": module.description,
            "content": module.content or "",
            "concept_list": "\n".join(
                f"- {c.name}: {c.description}" for c in module.concepts
            ),
        }

    async def _build_student_context(self, user_id: int) -> dict:
        """Build student context for prompt.

        Args:
            user_id: Database user ID

        Returns:
            Dictionary with student context
        """
        mastery_summary = "No mastery data yet"
        recent_topics = "None"

        # Get mastery summary
        summary = await self.repository.get_mastery_summary(user_id)
        if summary.get("total_quiz_attempts", 0) > 0:
            mastery_summary = (
                f"Mastered: {summary.get('mastered', 0)}, "
                f"Proficient: {summary.get('proficient', 0)}, "
                f"Learning: {summary.get('learning', 0)}"
            )

        # Get recent interactions
        recent = await self.repository.get_recent_interactions(user_id, limit=3)
        if recent:
            recent_topics = ", ".join(r.module_id for r in recent)

        return {
            "mastery_summary": mastery_summary,
            "recent_topics": recent_topics,
        }
