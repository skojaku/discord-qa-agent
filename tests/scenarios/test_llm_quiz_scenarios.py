"""Scenario-based tests for the /llm-quiz command flow (LLM Quiz Challenge).

These tests simulate the LLM Quiz Challenge feature where students
try to "stump the AI" by asking questions it might answer incorrectly.
"""

import pytest
import pytest_asyncio
from dataclasses import dataclass
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from tests.mocks import MockUser, create_mock_interaction


@dataclass
class MockChallengeResult:
    """Mock result for LLM Quiz Challenge."""

    student_wins: bool
    llm_answer: str
    llm_answer_summary: str
    student_answer_correctness: str
    evaluation_summary: str
    evaluation_explanation: str
    factual_issues: List[str]


class TestLLMQuizChallengeScenarios:
    """Test scenarios for LLM Quiz Challenge feature."""

    @pytest.fixture
    def mock_llm_quiz_config(self):
        """Create mock config for LLM Quiz service."""

        class MockConfig:
            target_wins_per_module = 3
            quiz_model = "mock/quiz-model"
            quiz_base_url = "http://localhost"
            evaluator_model = "mock/evaluator-model"
            evaluator_base_url = "http://localhost"

        return MockConfig()

    @pytest_asyncio.fixture
    async def llm_quiz_service(self, llm_quiz_repository, mock_llm_quiz_config):
        """Create LLM Quiz service with mocked dependencies."""
        from chibi.services import LLMQuizChallengeService

        service = LLMQuizChallengeService(
            llm_quiz_repo=llm_quiz_repository,
            config=mock_llm_quiz_config,
            api_key="mock-api-key",
        )

        return service

    @pytest.mark.asyncio
    async def test_scenario_student_stumps_ai(
        self,
        llm_quiz_service,
        llm_quiz_repository,
        user_repository,
        mock_user,
    ):
        """
        Scenario: Student successfully stumps the AI

        Given: A student asks a tricky question about network analysis
        When: The LLM answers incorrectly and the student's answer is correct
        Then: The student should win the challenge
        And: The attempt should be logged with student_wins=True
        """
        # Create user
        user = await user_repository.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Create mock result where student wins
        result = MockChallengeResult(
            student_wins=True,
            llm_answer="Betweenness centrality measures the degree of a node.",
            llm_answer_summary="LLM incorrectly confused betweenness with degree.",
            student_answer_correctness="CORRECT",
            evaluation_summary="Student wins! LLM got the definition wrong.",
            evaluation_explanation="The LLM confused betweenness centrality with degree centrality. The student correctly stated that betweenness measures how often a node lies on shortest paths.",
            factual_issues=["LLM confused betweenness with degree centrality"],
        )

        # Log the attempt
        attempt = await llm_quiz_service.log_attempt(
            user_id=user.id,
            module_id="module-1",
            question="What does betweenness centrality measure?",
            student_answer="Betweenness centrality measures how often a node appears on shortest paths between other nodes.",
            result=result,
            discord_user_id=str(mock_user.id),
            requires_review=True,
        )

        # Verify attempt was logged correctly
        assert attempt.student_wins is True
        assert attempt.student_answer_correctness == "CORRECT"
        assert "pending" in attempt.review_status  # Requires admin review

    @pytest.mark.asyncio
    async def test_scenario_ai_answers_correctly(
        self,
        llm_quiz_service,
        llm_quiz_repository,
        user_repository,
        mock_user,
    ):
        """
        Scenario: AI answers the question correctly

        Given: A student asks a question
        When: The LLM answers correctly
        Then: The student should lose the challenge
        And: The attempt should be auto-approved
        """
        # Create user
        user = await user_repository.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Create mock result where student loses
        result = MockChallengeResult(
            student_wins=False,
            llm_answer="Network centrality measures identify important nodes based on their position in the network.",
            llm_answer_summary="LLM correctly explained network centrality.",
            student_answer_correctness="CORRECT",
            evaluation_summary="LLM wins - correctly answered the question.",
            evaluation_explanation="Both answers are correct. The LLM provided a comprehensive answer.",
            factual_issues=[],
        )

        # Log the attempt
        attempt = await llm_quiz_service.log_attempt(
            user_id=user.id,
            module_id="module-1",
            question="What is network centrality?",
            student_answer="Network centrality measures node importance.",
            result=result,
            discord_user_id=str(mock_user.id),
            requires_review=True,
        )

        # Verify attempt was logged correctly
        assert attempt.student_wins is False
        assert attempt.review_status == "auto_approved"

    @pytest.mark.asyncio
    async def test_scenario_student_answer_incorrect(
        self,
        llm_quiz_service,
        llm_quiz_repository,
        user_repository,
        mock_user,
    ):
        """
        Scenario: Student provides an incorrect answer

        Given: A student submits a question with an incorrect answer
        When: The evaluator determines the student's answer is wrong
        Then: The student should lose regardless of LLM's answer
        """
        # Create user
        user = await user_repository.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Create mock result where student's answer is wrong
        result = MockChallengeResult(
            student_wins=False,
            llm_answer="Degree centrality counts the number of connections.",
            llm_answer_summary="LLM correctly explained degree centrality.",
            student_answer_correctness="INCORRECT",
            evaluation_summary="Student loses - provided incorrect answer.",
            evaluation_explanation="The student's answer was factually incorrect. Degree centrality does not measure shortest paths.",
            factual_issues=["Student confused degree with betweenness centrality"],
        )

        # Log the attempt
        attempt = await llm_quiz_service.log_attempt(
            user_id=user.id,
            module_id="module-1",
            question="What is degree centrality?",
            student_answer="Degree centrality measures shortest paths.",  # Wrong!
            result=result,
            discord_user_id=str(mock_user.id),
            requires_review=True,
        )

        # Verify
        assert attempt.student_wins is False
        assert attempt.student_answer_correctness == "INCORRECT"


class TestLLMQuizProgressScenarios:
    """Test scenarios for LLM Quiz progress tracking."""

    @pytest.fixture
    def mock_llm_quiz_config(self):
        """Create mock config for LLM Quiz service."""

        class MockConfig:
            target_wins_per_module = 3
            quiz_model = "mock/quiz-model"
            quiz_base_url = "http://localhost"
            evaluator_model = "mock/evaluator-model"
            evaluator_base_url = "http://localhost"

        return MockConfig()

    @pytest_asyncio.fixture
    async def llm_quiz_service(self, llm_quiz_repository, mock_llm_quiz_config):
        """Create LLM Quiz service with mocked dependencies."""
        from chibi.services import LLMQuizChallengeService

        service = LLMQuizChallengeService(
            llm_quiz_repo=llm_quiz_repository,
            config=mock_llm_quiz_config,
            api_key="mock-api-key",
        )

        return service

    @pytest.mark.asyncio
    async def test_scenario_track_wins_per_module(
        self,
        llm_quiz_service,
        llm_quiz_repository,
        user_repository,
        mock_user,
    ):
        """
        Scenario: Track student wins per module

        Given: A student who has won 2 challenges in module-1
        When: They check their progress
        Then: They should see 2/3 wins for that module
        """
        # Create user
        user = await user_repository.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Log two winning attempts
        for i in range(2):
            result = MockChallengeResult(
                student_wins=True,
                llm_answer=f"Wrong answer {i}",
                llm_answer_summary="LLM was wrong.",
                student_answer_correctness="CORRECT",
                evaluation_summary="Student wins!",
                evaluation_explanation="LLM got it wrong.",
                factual_issues=[],
            )

            await llm_quiz_service.log_attempt(
                user_id=user.id,
                module_id="module-1",
                question=f"Question {i+1}",
                student_answer=f"Correct answer {i+1}",
                result=result,
                discord_user_id=str(mock_user.id),
                requires_review=False,  # Auto-approve for test
            )

        # Check progress
        wins, target = await llm_quiz_service.get_module_progress(
            user.id, "module-1"
        )

        assert wins == 2
        assert target == 3
        assert not llm_quiz_service.is_module_complete(wins)

    @pytest.mark.asyncio
    async def test_scenario_complete_module_challenge(
        self,
        llm_quiz_service,
        llm_quiz_repository,
        user_repository,
        mock_user,
    ):
        """
        Scenario: Student completes all required wins for a module

        Given: A student who has won 2 challenges
        When: They win their 3rd challenge
        Then: The module should be marked as complete
        """
        # Create user
        user = await user_repository.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Log three winning attempts
        for i in range(3):
            result = MockChallengeResult(
                student_wins=True,
                llm_answer=f"Wrong answer {i}",
                llm_answer_summary="LLM was wrong.",
                student_answer_correctness="CORRECT",
                evaluation_summary="Student wins!",
                evaluation_explanation="LLM got it wrong.",
                factual_issues=[],
            )

            await llm_quiz_service.log_attempt(
                user_id=user.id,
                module_id="module-1",
                question=f"Question {i+1}",
                student_answer=f"Correct answer {i+1}",
                result=result,
                discord_user_id=str(mock_user.id),
                requires_review=False,
            )

        # Check completion
        wins, target = await llm_quiz_service.get_module_progress(
            user.id, "module-1"
        )

        assert wins == 3
        assert llm_quiz_service.is_module_complete(wins)

    @pytest.mark.asyncio
    async def test_scenario_multi_module_progress(
        self,
        llm_quiz_service,
        llm_quiz_repository,
        user_repository,
        mock_user,
    ):
        """
        Scenario: Track progress across multiple modules

        Given: A student with wins in multiple modules
        When: They check their overall progress
        Then: They should see progress for each module separately
        """
        # Create user
        user = await user_repository.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Log wins in different modules
        modules_wins = {
            "module-1": 3,  # Complete
            "module-2": 1,  # In progress
            "module-3": 0,  # Not started (no attempts to log)
        }

        for module_id, num_wins in modules_wins.items():
            for i in range(num_wins):
                result = MockChallengeResult(
                    student_wins=True,
                    llm_answer=f"Wrong answer",
                    llm_answer_summary="LLM was wrong.",
                    student_answer_correctness="CORRECT",
                    evaluation_summary="Student wins!",
                    evaluation_explanation="LLM got it wrong.",
                    factual_issues=[],
                )

                await llm_quiz_service.log_attempt(
                    user_id=user.id,
                    module_id=module_id,
                    question=f"Question {i+1} for {module_id}",
                    student_answer=f"Correct answer",
                    result=result,
                    discord_user_id=str(mock_user.id),
                    requires_review=False,
                )

        # Get all progress
        all_progress = await llm_quiz_service.get_all_progress(user.id)

        assert all_progress.get("module-1", (0, 3))[0] == 3
        assert all_progress.get("module-2", (0, 3))[0] == 1
        # module-3 won't be in progress since no attempts


class TestLLMQuizReviewScenarios:
    """Test scenarios for admin review of LLM Quiz wins."""

    @pytest.fixture
    def mock_llm_quiz_config(self):
        """Create mock config for LLM Quiz service."""

        class MockConfig:
            target_wins_per_module = 3
            quiz_model = "mock/quiz-model"
            quiz_base_url = "http://localhost"
            evaluator_model = "mock/evaluator-model"
            evaluator_base_url = "http://localhost"

        return MockConfig()

    @pytest_asyncio.fixture
    async def llm_quiz_service(self, llm_quiz_repository, mock_llm_quiz_config):
        """Create LLM Quiz service with mocked dependencies."""
        from chibi.services import LLMQuizChallengeService

        service = LLMQuizChallengeService(
            llm_quiz_repo=llm_quiz_repository,
            config=mock_llm_quiz_config,
            api_key="mock-api-key",
        )

        return service

    @pytest.mark.asyncio
    async def test_scenario_pending_review_for_wins(
        self,
        llm_quiz_service,
        llm_quiz_repository,
        user_repository,
        mock_user,
    ):
        """
        Scenario: Student wins require admin review

        Given: A student wins a challenge
        When: The attempt is logged with requires_review=True
        Then: The status should be PENDING for admin review
        """
        from chibi.database.models import ReviewStatus

        # Create user
        user = await user_repository.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Log a winning attempt that requires review
        result = MockChallengeResult(
            student_wins=True,
            llm_answer="Wrong answer",
            llm_answer_summary="LLM was wrong.",
            student_answer_correctness="CORRECT",
            evaluation_summary="Student wins!",
            evaluation_explanation="LLM made an error.",
            factual_issues=[],
        )

        attempt = await llm_quiz_service.log_attempt(
            user_id=user.id,
            module_id="module-1",
            question="Tricky question",
            student_answer="Correct answer",
            result=result,
            discord_user_id=str(mock_user.id),
            requires_review=True,
        )

        # Verify pending status
        assert attempt.review_status == ReviewStatus.PENDING

    @pytest.mark.asyncio
    async def test_scenario_admin_approves_win(
        self,
        llm_quiz_repository,
        user_repository,
        mock_user,
    ):
        """
        Scenario: Admin approves a pending win

        Given: A student has a pending win
        When: An admin approves the win
        Then: The status should change to APPROVED
        And: The win should count towards progress
        """
        from chibi.database.models import ReviewStatus

        # Create user
        user = await user_repository.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Create a pending attempt
        attempt = await llm_quiz_repository.log_attempt(
            user_id=user.id,
            module_id="module-1",
            question="Question",
            student_answer="Answer",
            llm_answer="LLM Answer",
            student_wins=True,
            student_answer_correctness="CORRECT",
            evaluation_explanation="Explanation",
            review_status=ReviewStatus.PENDING,
            discord_user_id=str(mock_user.id),
        )

        # Admin approves
        updated = await llm_quiz_repository.update_review_status(
            attempt_id=attempt.id,
            review_status=ReviewStatus.APPROVED,
            reviewed_by="admin-123",
        )

        assert updated is not None

        # Verify the status was updated
        assert updated.review_status == ReviewStatus.APPROVED

    @pytest.mark.asyncio
    async def test_scenario_admin_rejects_win(
        self,
        llm_quiz_repository,
        user_repository,
        mock_user,
    ):
        """
        Scenario: Admin rejects a pending win

        Given: A student has a pending win
        When: An admin rejects it (e.g., content mismatch)
        Then: The status should change to REJECTED
        And: The win should NOT count towards progress
        """
        from chibi.database.models import ReviewStatus

        # Create user
        user = await user_repository.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Create a pending attempt
        attempt = await llm_quiz_repository.log_attempt(
            user_id=user.id,
            module_id="module-1",
            question="Off-topic question",
            student_answer="Answer",
            llm_answer="LLM Answer",
            student_wins=True,
            student_answer_correctness="CORRECT",
            evaluation_explanation="Explanation",
            review_status=ReviewStatus.PENDING,
            discord_user_id=str(mock_user.id),
        )

        # Admin rejects for content mismatch
        updated = await llm_quiz_repository.update_review_status(
            attempt_id=attempt.id,
            review_status=ReviewStatus.REJECTED_CONTENT_MISMATCH,
            reviewed_by="admin-123",
        )

        assert updated is not None

        # Verify the status was updated
        assert updated.review_status == ReviewStatus.REJECTED_CONTENT_MISMATCH

        # Verify wins count doesn't include rejected attempts
        wins = await llm_quiz_repository.count_wins_for_module(user.id, "module-1")
        assert wins == 0


class TestLLMQuizValidationScenarios:
    """Test scenarios for input validation in LLM Quiz."""

    @pytest.fixture
    def mock_llm_quiz_config(self):
        """Create mock config for LLM Quiz service."""

        class MockConfig:
            target_wins_per_module = 3
            quiz_model = "mock/quiz-model"
            quiz_base_url = "http://localhost"
            evaluator_model = "mock/evaluator-model"
            evaluator_base_url = "http://localhost"

        return MockConfig()

    @pytest_asyncio.fixture
    async def llm_quiz_service(self, llm_quiz_repository, mock_llm_quiz_config):
        """Create LLM Quiz service with mocked dependencies."""
        from chibi.services import LLMQuizChallengeService

        service = LLMQuizChallengeService(
            llm_quiz_repo=llm_quiz_repository,
            config=mock_llm_quiz_config,
            api_key="mock-api-key",
        )

        return service

    @pytest.mark.asyncio
    async def test_scenario_losses_auto_approved(
        self,
        llm_quiz_service,
        llm_quiz_repository,
        user_repository,
        mock_user,
    ):
        """
        Scenario: Losses are automatically approved

        Given: A student loses a challenge
        When: The attempt is logged
        Then: It should be auto-approved (no admin review needed)
        """
        from chibi.database.models import ReviewStatus

        # Create user
        user = await user_repository.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Log a losing attempt
        result = MockChallengeResult(
            student_wins=False,
            llm_answer="Correct answer",
            llm_answer_summary="LLM answered correctly.",
            student_answer_correctness="CORRECT",
            evaluation_summary="LLM wins!",
            evaluation_explanation="The LLM provided a correct answer.",
            factual_issues=[],
        )

        attempt = await llm_quiz_service.log_attempt(
            user_id=user.id,
            module_id="module-1",
            question="Easy question",
            student_answer="Answer",
            result=result,
            discord_user_id=str(mock_user.id),
            requires_review=True,  # Even with review flag, losses auto-approve
        )

        # Verify auto-approved status
        assert attempt.review_status == ReviewStatus.AUTO_APPROVED
