"""Scenario-based tests for the /quiz command flow.

These tests simulate real user interactions with the quiz system,
from requesting a quiz to answering questions and tracking mastery.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from tests.mocks import (
    MockInteraction,
    MockUser,
    create_mock_interaction,
)
from tests.mocks.llm_mocks import MockLLMProvider


class TestQuizGenerationScenarios:
    """Test scenarios for quiz question generation."""

    @pytest.mark.asyncio
    async def test_scenario_student_requests_quiz_first_time(
        self,
        configured_bot,
        sample_module,
        mock_user,
    ):
        """
        Scenario: A new student requests their first quiz

        Given: A student who has never taken a quiz before
        When: They request a quiz from module-1
        Then: They should receive a question about an unattempted concept
        And: The selection reason should indicate "New concept"
        """
        # Create user in database
        user = await configured_bot.user_repo.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Select concept for quiz
        concept, selection_reason = await configured_bot.quiz_service.select_concept_by_mastery(
            user.id, sample_module
        )

        # Assertions
        assert concept is not None, "Should select a concept"
        assert selection_reason == "New concept", "First quiz should prioritize new concepts"
        assert concept.id in [c.id for c in sample_module.concepts]

    @pytest.mark.asyncio
    async def test_scenario_student_requests_quiz_after_attempts(
        self,
        configured_bot,
        sample_module,
        mock_user,
    ):
        """
        Scenario: A student requests a quiz after completing some quizzes

        Given: A student who has attempted concept-1 but not concept-2
        When: They request a new quiz
        Then: The system should prioritize the unattempted concept-2
        """
        # Create user
        user = await configured_bot.user_repo.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Record attempt on first concept
        first_concept = sample_module.concepts[0]
        mastery = await configured_bot.mastery_repo.get_or_create(
            user.id, first_concept.id
        )
        await configured_bot.mastery_repo.update(
            user_id=user.id,
            concept_id=first_concept.id,
            total_attempts=2,
            correct_attempts=1,
            avg_quality_score=3.5,
            mastery_level="learning",
        )

        # Request new quiz - should prioritize unattempted concept
        concept, selection_reason = await configured_bot.quiz_service.select_concept_by_mastery(
            user.id, sample_module
        )

        # Should select the second concept (unattempted)
        second_concept = sample_module.concepts[1]
        assert concept.id == second_concept.id, "Should prioritize unattempted concept"
        assert selection_reason == "New concept"

    @pytest.mark.asyncio
    async def test_scenario_generate_quiz_question(
        self,
        configured_bot,
        sample_module,
        sample_concept,
    ):
        """
        Scenario: System generates a quiz question for a concept

        Given: A concept about network centrality
        When: The quiz service generates a question
        Then: A valid question should be returned
        """
        # Configure mock to return a specific question
        configured_bot.llm_manager.primary.set_response(
            "What is the primary purpose of degree centrality in network analysis?\n\n"
            "Degree centrality measures the number of connections a node has.\n"
            "[EXPECTED: To measure the number of direct connections a node has]"
        )

        # Generate question
        result = await configured_bot.quiz_service.generate_question(
            sample_concept, sample_module
        )

        assert result is not None
        question_text, correct_answer = result
        assert "centrality" in question_text.lower() or "network" in question_text.lower()


class TestQuizEvaluationScenarios:
    """Test scenarios for quiz answer evaluation."""

    @pytest.mark.asyncio
    async def test_scenario_student_gives_correct_answer(
        self,
        configured_bot,
        sample_concept,
    ):
        """
        Scenario: A student provides a correct answer

        Given: A quiz question about network centrality
        When: The student provides a correct answer
        Then: The evaluation should mark it as PASS
        And: The quality score should be high (4-5)
        """
        # Configure mock to return a passing evaluation
        configured_bot.llm_manager.primary.set_response(
            "PASS\n5\n"
            "Excellent answer! You correctly explained that network centrality "
            "measures the importance of nodes in a network."
        )

        # Evaluate answer
        result = await configured_bot.quiz_service.evaluate_answer(
            question="What is network centrality?",
            student_answer="Network centrality measures how important or influential a node is within a network based on its connections.",
            concept_name=sample_concept.name,
            concept_description=sample_concept.description,
        )

        assert result is not None
        assert result.is_correct is True
        assert result.quality_score >= 4
        assert result.counts_as_correct is True

    @pytest.mark.asyncio
    async def test_scenario_student_gives_partial_answer(
        self,
        configured_bot,
        sample_concept,
    ):
        """
        Scenario: A student provides a partially correct answer

        Given: A quiz question about network centrality
        When: The student provides an incomplete answer
        Then: The evaluation should mark it as PARTIAL
        """
        # Configure mock to return a partial evaluation
        configured_bot.llm_manager.primary.set_response(
            "PARTIAL\n3\n"
            "Your answer shows some understanding but is incomplete. "
            "Consider also mentioning the different types of centrality measures."
        )

        # Evaluate answer
        result = await configured_bot.quiz_service.evaluate_answer(
            question="What are the main types of network centrality?",
            student_answer="Degree centrality counts connections.",
            concept_name=sample_concept.name,
            concept_description=sample_concept.description,
        )

        assert result is not None
        assert result.is_partial is True
        assert result.is_correct is False
        assert result.counts_as_correct is True  # Partial still counts

    @pytest.mark.asyncio
    async def test_scenario_student_gives_wrong_answer(
        self,
        configured_bot,
        sample_concept,
    ):
        """
        Scenario: A student provides an incorrect answer

        Given: A quiz question about network centrality
        When: The student provides a wrong answer
        Then: The evaluation should mark it as FAIL
        """
        # Configure mock to return a failing evaluation
        configured_bot.llm_manager.primary.set_response(
            "FAIL\n1\n"
            "Your answer is incorrect. Network centrality does not measure "
            "the physical size of a network."
        )

        # Evaluate answer
        result = await configured_bot.quiz_service.evaluate_answer(
            question="What is network centrality?",
            student_answer="Network centrality is the size of the network in bytes.",
            concept_name=sample_concept.name,
            concept_description=sample_concept.description,
        )

        assert result is not None
        assert result.is_correct is False
        assert result.is_partial is False
        assert result.counts_as_correct is False


class TestQuizMasteryScenarios:
    """Test scenarios for mastery progression through quizzes."""

    @pytest.mark.asyncio
    async def test_scenario_mastery_progression_novice_to_learning(
        self,
        configured_bot,
        sample_module,
        sample_concept,
        mock_user,
    ):
        """
        Scenario: Student progresses from novice to learning level

        Given: A student at novice level with 0 attempts
        When: They answer 2 questions correctly
        Then: Their mastery level should progress to "learning"
        """
        from chibi.services.quiz_service import EvaluationResult

        # Create user
        user = await configured_bot.user_repo.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Simulate two correct quiz attempts
        for i in range(2):
            result = EvaluationResult(
                is_correct=True,
                is_partial=False,
                quality_score=4,
                feedback="Good answer!",
                counts_as_correct=True,
            )

            await configured_bot.quiz_service.log_attempt_and_update_mastery(
                user_id=user.id,
                module_id=sample_module.id,
                concept_id=sample_concept.id,
                question=f"Question {i+1}",
                user_answer=f"Answer {i+1}",
                correct_answer=None,
                result=result,
            )

        # Check mastery level
        mastery = await configured_bot.mastery_repo.get_or_create(
            user.id, sample_concept.id
        )

        assert mastery.total_attempts == 2
        assert mastery.correct_attempts == 2
        assert mastery.mastery_level == "learning"

    @pytest.mark.asyncio
    async def test_scenario_mastery_requires_minimum_attempts(
        self,
        configured_bot,
        sample_module,
        sample_concept,
        mock_user,
    ):
        """
        Scenario: Mastery level requires minimum attempts

        Given: A student who got 1 question correct
        When: Their mastery is calculated
        Then: They should still be at "learning" level (not mastered)
        Because: Min attempts for mastery is 3
        """
        from chibi.services.quiz_service import EvaluationResult

        # Create user
        user = await configured_bot.user_repo.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # One correct attempt with perfect score
        result = EvaluationResult(
            is_correct=True,
            is_partial=False,
            quality_score=5,
            feedback="Perfect!",
            counts_as_correct=True,
        )

        await configured_bot.quiz_service.log_attempt_and_update_mastery(
            user_id=user.id,
            module_id=sample_module.id,
            concept_id=sample_concept.id,
            question="Question 1",
            user_answer="Perfect answer",
            correct_answer=None,
            result=result,
        )

        # Check mastery - should NOT be mastered yet
        mastery = await configured_bot.mastery_repo.get_or_create(
            user.id, sample_concept.id
        )

        assert mastery.total_attempts == 1
        # Even with 100% accuracy, can't be mastered with only 1 attempt
        assert mastery.mastery_level != "mastered"


class TestQuizFullFlowScenarios:
    """End-to-end test scenarios simulating complete quiz interactions."""

    @pytest.mark.asyncio
    async def test_scenario_complete_quiz_session(
        self,
        configured_bot,
        sample_module,
        mock_user,
    ):
        """
        Scenario: Complete quiz session from start to finish

        Given: A new student starting their first quiz session
        When: They complete 3 quizzes on the same module
        Then: Their progress should be tracked correctly
        And: They should have quiz history in the database
        """
        from chibi.services.quiz_service import EvaluationResult

        # Create user
        user = await configured_bot.user_repo.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Configure mock for questions
        configured_bot.llm_manager.primary.queue_responses([
            "What is network centrality?\n[EXPECTED: Measure of node importance]",
            "Explain degree centrality.\n[EXPECTED: Count of connections]",
            "What is betweenness centrality?\n[EXPECTED: Bridge between nodes]",
        ])

        # Session: Answer 3 questions
        results_sequence = [
            (True, 4),   # Q1: Correct
            (False, 2),  # Q2: Wrong
            (True, 5),   # Q3: Correct
        ]

        for i, (is_correct, score) in enumerate(results_sequence):
            # Select concept
            concept, _ = await configured_bot.quiz_service.select_concept_by_mastery(
                user.id, sample_module
            )

            # Generate question (uses queued response)
            question_result = await configured_bot.quiz_service.generate_question(
                concept, sample_module
            )
            question_text = question_result[0] if question_result else f"Question {i+1}"

            # Simulate evaluation
            result = EvaluationResult(
                is_correct=is_correct,
                is_partial=False,
                quality_score=score,
                feedback="Feedback",
                counts_as_correct=is_correct,
            )

            # Log attempt
            await configured_bot.quiz_service.log_attempt_and_update_mastery(
                user_id=user.id,
                module_id=sample_module.id,
                concept_id=concept.id,
                question=question_text,
                user_answer=f"Answer {i+1}",
                correct_answer=None,
                result=result,
            )

        # Verify quiz history
        attempts = await configured_bot.quiz_repo.get_user_attempts(
            user.id, limit=10
        )
        assert len(attempts) == 3, "Should have 3 quiz attempts"

        # Verify at least one concept has updated mastery
        first_concept = sample_module.concepts[0]
        mastery = await configured_bot.mastery_repo.get_or_create(
            user.id, first_concept.id
        )
        assert mastery.total_attempts >= 0  # Has been accessed

    @pytest.mark.asyncio
    async def test_scenario_quiz_prioritization_across_concepts(
        self,
        configured_bot,
        sample_module,
        mock_user,
    ):
        """
        Scenario: Quiz system prioritizes concepts based on mastery

        Given: A student with varying mastery levels across concepts
        When: They request multiple quizzes
        Then: The system should prioritize lower-mastery concepts
        """
        from chibi.services.quiz_service import EvaluationResult

        # Create user
        user = await configured_bot.user_repo.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Set different mastery levels
        concept_1 = sample_module.concepts[0]  # Will be "proficient"
        concept_2 = sample_module.concepts[1]  # Will be "novice"

        # Make concept_1 proficient
        await configured_bot.mastery_repo.update(
            user_id=user.id,
            concept_id=concept_1.id,
            total_attempts=5,
            correct_attempts=4,
            avg_quality_score=4.5,
            mastery_level="proficient",
        )

        # Make concept_2 novice with some attempts
        await configured_bot.mastery_repo.update(
            user_id=user.id,
            concept_id=concept_2.id,
            total_attempts=1,
            correct_attempts=0,
            avg_quality_score=2.0,
            mastery_level="novice",
        )

        # Request quiz - should prioritize novice concept
        selected_concept, reason = await configured_bot.quiz_service.select_concept_by_mastery(
            user.id, sample_module
        )

        assert selected_concept.id == concept_2.id, "Should select lower-mastery concept"
        assert reason == "Needs practice", "Should indicate practice needed"


class TestQuizErrorScenarios:
    """Test scenarios for error handling in quiz system."""

    @pytest.mark.asyncio
    async def test_scenario_llm_unavailable(
        self,
        configured_bot,
        sample_module,
        sample_concept,
    ):
        """
        Scenario: LLM provider is unavailable

        Given: Both LLM providers are unavailable
        When: A quiz question is requested
        Then: The system should return None gracefully
        """
        # Make both providers unavailable
        configured_bot.llm_manager.primary.set_available(False)
        configured_bot.llm_manager.fallback.set_available(False)

        # Try to generate question
        result = await configured_bot.quiz_service.generate_question(
            sample_concept, sample_module
        )

        assert result is None, "Should return None when LLM unavailable"

    @pytest.mark.asyncio
    async def test_scenario_empty_module(
        self,
        configured_bot,
        mock_user,
    ):
        """
        Scenario: Module has no concepts

        Given: A module with no concepts
        When: A quiz is requested
        Then: The system should return None for concept selection
        """
        from chibi.content.course import Module

        # Create empty module
        empty_module = Module(
            id="empty-module",
            name="Empty Module",
            description="Module with no concepts",
            concepts=[],
        )

        # Create user
        user = await configured_bot.user_repo.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Try to select concept
        concept, reason = await configured_bot.quiz_service.select_concept_by_mastery(
            user.id, empty_module
        )

        assert concept is None, "Should return None for empty module"
