"""LLM Quiz Challenge service for the stump-the-AI feature."""

import asyncio
import logging
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import dspy

# Add llm-quiz to path for importing DSPy signatures
sys.path.insert(0, "llm-quiz")
from llm_quiz import AnswerQuizQuestion, EvaluateAnswer

if TYPE_CHECKING:
    from ..config import LLMQuizConfig
    from ..database.repositories import LLMQuizRepository

logger = logging.getLogger(__name__)


@dataclass
class LLMQuizChallengeResult:
    """Result of an LLM Quiz Challenge."""

    student_wins: bool
    llm_answer: str
    student_answer_correctness: str  # "CORRECT", "INCORRECT", "PARTIALLY_CORRECT"
    evaluation_summary: str  # Brief 1-2 sentence summary
    evaluation_explanation: str  # Detailed explanation (for logging)
    factual_issues: List[str]


class LLMQuizChallengeService:
    """Service for LLM Quiz Challenge feature."""

    def __init__(
        self,
        llm_quiz_repo: "LLMQuizRepository",
        config: "LLMQuizConfig",
        api_key: str,
    ):
        self.llm_quiz_repo = llm_quiz_repo
        self.config = config
        self.api_key = api_key
        self.target_wins_per_module = config.target_wins_per_module

        # Initialize DSPy LMs
        self._quiz_lm = None
        self._evaluator_lm = None

    def _get_quiz_lm(self) -> dspy.LM:
        """Get or create the DSPy LM for answering questions."""
        if self._quiz_lm is None:
            self._quiz_lm = dspy.LM(
                model=self.config.quiz_model,
                api_base=self.config.base_url,
                api_key=self.api_key,
            )
        return self._quiz_lm

    def _get_evaluator_lm(self) -> dspy.LM:
        """Get or create the DSPy LM for evaluating answers."""
        if self._evaluator_lm is None:
            self._evaluator_lm = dspy.LM(
                model=self.config.evaluator_model,
                api_base=self.config.base_url,
                api_key=self.api_key,
            )
        return self._evaluator_lm

    def _run_challenge_sync(
        self,
        question: str,
        student_answer: str,
        module_content: Optional[str],
        quiz_lm: dspy.LM,
        evaluator_lm: dspy.LM,
    ) -> LLMQuizChallengeResult:
        """Synchronous implementation of challenge logic (runs in thread pool)."""
        # Step 1: Quiz model attempts to answer the question
        logger.info("LLM Quiz Challenge: Quiz model attempting to answer question")
        with dspy.context(lm=quiz_lm):
            answerer = dspy.Predict(AnswerQuizQuestion)
            try:
                llm_response = answerer(
                    question=question,
                    context_content=module_content,
                )
                llm_answer = getattr(llm_response, "answer", "Unable to generate answer")
            except Exception as e:
                logger.error(f"Error generating LLM answer: {e}")
                llm_answer = f"Error generating answer: {str(e)}"

        logger.info("LLM Quiz Challenge: LLM answered, now evaluating")

        # Step 2: Evaluator model checks BOTH answers
        with dspy.context(lm=evaluator_lm):
            evaluator = dspy.ChainOfThought(EvaluateAnswer)
            try:
                evaluation = evaluator(
                    question=question,
                    correct_answer=student_answer,
                    llm_answer=llm_answer,
                )

                # Extract results from DSPy response
                student_wins = getattr(evaluation, "student_wins", False)
                summary = getattr(evaluation, "summary", "")
                explanation = getattr(evaluation, "explanation", "No explanation available")
                student_answer_correctness = getattr(
                    evaluation, "student_answer_correctness", "CORRECT"
                )
                factual_issues = getattr(evaluation, "factual_issues", [])

            except Exception as e:
                logger.error(f"Error evaluating answers: {e}")
                # Default to student loses on error
                student_wins = False
                summary = "Error during evaluation."
                explanation = f"Error during evaluation: {str(e)}"
                student_answer_correctness = "CORRECT"
                factual_issues = []

        logger.info(f"LLM Quiz Challenge: Student wins = {student_wins}")

        return LLMQuizChallengeResult(
            student_wins=student_wins,
            llm_answer=llm_answer,
            student_answer_correctness=student_answer_correctness,
            evaluation_summary=summary,
            evaluation_explanation=explanation,
            factual_issues=factual_issues if isinstance(factual_issues, list) else [],
        )

    async def challenge_llm(
        self,
        question: str,
        student_answer: str,
        module_content: Optional[str] = None,
    ) -> LLMQuizChallengeResult:
        """
        Run the LLM Quiz Challenge:
        1. Quiz model attempts to answer the student's question
        2. Evaluator model evaluates if LLM got it wrong (student wins if LLM wrong AND student right)

        Args:
            question: The student's question
            student_answer: The student's provided correct answer
            module_content: Optional context content from module

        Returns:
            LLMQuizChallengeResult with outcome
        """
        quiz_lm = self._get_quiz_lm()
        evaluator_lm = self._get_evaluator_lm()

        # Run blocking DSPy calls in thread pool to avoid blocking event loop
        return await asyncio.to_thread(
            self._run_challenge_sync,
            question,
            student_answer,
            module_content,
            quiz_lm,
            evaluator_lm,
        )

    async def log_attempt(
        self,
        user_id: int,
        module_id: str,
        question: str,
        student_answer: str,
        result: LLMQuizChallengeResult,
    ) -> None:
        """Log an LLM quiz challenge attempt to the database."""
        await self.llm_quiz_repo.log_attempt(
            user_id=user_id,
            module_id=module_id,
            question=question,
            student_answer=student_answer,
            llm_answer=result.llm_answer,
            student_wins=result.student_wins,
            student_answer_correctness=result.student_answer_correctness,
            evaluation_explanation=result.evaluation_explanation,
        )

    async def get_module_progress(
        self, user_id: int, module_id: str
    ) -> Tuple[int, int]:
        """Get progress for a specific module.

        Returns:
            Tuple of (wins_count, target_wins)
        """
        wins = await self.llm_quiz_repo.count_wins_for_module(user_id, module_id)
        return wins, self.target_wins_per_module

    async def get_all_progress(self, user_id: int) -> Dict[str, Tuple[int, int]]:
        """Get progress for all modules.

        Returns:
            Dict mapping module_id to (wins_count, target_wins)
        """
        progress = await self.llm_quiz_repo.get_progress_by_module(user_id)
        return {
            module_id: (wins, self.target_wins_per_module)
            for module_id, wins in progress.items()
        }

    def is_module_complete(self, wins_count: int) -> bool:
        """Check if a module is complete based on wins."""
        return wins_count >= self.target_wins_per_module
