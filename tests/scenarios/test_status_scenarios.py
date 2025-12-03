"""Scenario-based tests for the /status and /modules commands.

These tests simulate user interactions when checking their progress,
viewing module information, and tracking mastery levels.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from tests.mocks import MockUser, create_mock_interaction


class TestStatusSummaryScenarios:
    """Test scenarios for overall status summary display."""

    @pytest.mark.asyncio
    async def test_scenario_new_student_views_status(
        self,
        configured_bot,
        mock_user,
    ):
        """
        Scenario: A new student views their status for the first time

        Given: A student who has never taken any quizzes
        When: They use the /status command
        Then: They should see 0% progress
        And: They should see 0 quizzes taken
        """
        # Create user
        user = await configured_bot.user_repo.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Get summary
        summary = await configured_bot.mastery_repo.get_summary(user.id)

        # Verify empty state
        assert summary.get("mastered", 0) == 0
        assert summary.get("proficient", 0) == 0
        assert summary.get("learning", 0) == 0
        assert summary.get("novice", 0) == 0

    @pytest.mark.asyncio
    async def test_scenario_student_with_progress_views_status(
        self,
        configured_bot,
        sample_module,
        mock_user,
    ):
        """
        Scenario: A student with quiz history views their status

        Given: A student who has completed several quizzes
        When: They use the /status command
        Then: They should see their mastery breakdown
        And: They should see accurate quiz statistics
        """
        # Create user
        user = await configured_bot.user_repo.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Add mastery records
        concept_1 = sample_module.concepts[0]
        concept_2 = sample_module.concepts[1]

        # Set concept 1 as "proficient"
        await configured_bot.mastery_repo.update(
            user_id=user.id,
            concept_id=concept_1.id,
            total_attempts=5,
            correct_attempts=4,
            avg_quality_score=4.2,
            mastery_level="proficient",
        )

        # Set concept 2 as "learning"
        await configured_bot.mastery_repo.update(
            user_id=user.id,
            concept_id=concept_2.id,
            total_attempts=3,
            correct_attempts=2,
            avg_quality_score=3.5,
            mastery_level="learning",
        )

        # Get summary
        summary = await configured_bot.mastery_repo.get_summary(user.id)

        # Verify mastery breakdown
        assert summary.get("proficient", 0) == 1
        assert summary.get("learning", 0) == 1
        assert summary.get("mastered", 0) == 0
        assert summary.get("novice", 0) == 0


class TestModuleDetailScenarios:
    """Test scenarios for detailed module status view."""

    @pytest.mark.asyncio
    async def test_scenario_view_module_with_mixed_progress(
        self,
        configured_bot,
        sample_module,
        mock_user,
    ):
        """
        Scenario: View a module with concepts at different mastery levels

        Given: A student with varied progress on a module's concepts
        When: They request detailed status for that module
        Then: They should see each concept's mastery level
        And: They should see their accuracy for each concept
        """
        # Create user
        user = await configured_bot.user_repo.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Set varied mastery levels
        concept_1 = sample_module.concepts[0]
        await configured_bot.mastery_repo.update(
            user_id=user.id,
            concept_id=concept_1.id,
            total_attempts=10,
            correct_attempts=9,
            avg_quality_score=4.5,
            mastery_level="mastered",
        )

        concept_2 = sample_module.concepts[1]
        # Leave concept_2 as not started

        # Get mastery records
        mastery_records = await configured_bot.mastery_repo.get_all_for_user(user.id)
        mastery_by_concept = {m.concept_id: m for m in mastery_records}

        # Verify concept_1 is mastered
        assert concept_1.id in mastery_by_concept
        assert mastery_by_concept[concept_1.id].mastery_level == "mastered"

        # Verify concept_2 is not started
        assert concept_2.id not in mastery_by_concept

    @pytest.mark.asyncio
    async def test_scenario_view_nonexistent_module(
        self,
        configured_bot,
        mock_user,
    ):
        """
        Scenario: Request status for a module that doesn't exist

        Given: A student trying to view a non-existent module
        When: They request status with an invalid module ID
        Then: The system should return None for the module
        """
        # Try to get non-existent module
        module = configured_bot.course.get_module("invalid-module-id")

        assert module is None


class TestModuleListScenarios:
    """Test scenarios for viewing available modules."""

    @pytest.mark.asyncio
    async def test_scenario_view_all_modules(
        self,
        configured_bot,
    ):
        """
        Scenario: View list of all available modules

        Given: A course with multiple modules
        When: A user views the module list
        Then: They should see all modules with their names
        And: Each module should have concept count visible
        """
        # Get module choices
        module_choices = configured_bot.course.get_module_choices()

        # Verify modules are listed
        assert len(module_choices) == 2  # sample_course has 2 modules
        assert any("Network Analysis" in name for name, _ in module_choices)
        assert any("Graph Algorithms" in name for name, _ in module_choices)

    @pytest.mark.asyncio
    async def test_scenario_get_module_concepts(
        self,
        configured_bot,
        sample_module,
    ):
        """
        Scenario: View concepts within a module

        Given: A module with multiple concepts
        When: A user views the module details
        Then: They should see all concepts
        And: Concepts should include descriptions
        """
        # Get concepts for the module
        concepts = sample_module.concepts

        assert len(concepts) == 2
        assert concepts[0].name == "Network Centrality"
        assert concepts[1].name == "Graph Theory Basics"

        # Each concept should have required attributes
        for concept in concepts:
            assert concept.id is not None
            assert concept.name is not None
            assert concept.description is not None


class TestMasteryCalculationScenarios:
    """Test scenarios for mastery level calculations."""

    @pytest.mark.asyncio
    async def test_scenario_mastery_level_novice(
        self,
        mastery_repository,
        user_repository,
        mock_user,
    ):
        """
        Scenario: Calculate mastery level for a novice

        Given: A student with low accuracy
        When: Mastery is calculated
        Then: They should be at "novice" level
        """
        from chibi.learning.mastery import MasteryCalculator, MasteryConfig, MasteryLevel

        # Create user
        user = await user_repository.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Initialize mastery calculator
        config = MasteryConfig(min_attempts_for_mastery=3)
        calculator = MasteryCalculator(config)

        # Low accuracy: 1/4 = 25%
        level = calculator.calculate_level(
            total_attempts=4,
            correct_attempts=1,
            avg_quality_score=2.0,
        )

        assert level == MasteryLevel.NOVICE

    @pytest.mark.asyncio
    async def test_scenario_mastery_level_learning(
        self,
        mastery_repository,
        user_repository,
        mock_user,
    ):
        """
        Scenario: Calculate mastery level for a learning student

        Given: A student with moderate accuracy (30-60%)
        When: Mastery is calculated
        Then: They should be at "learning" level
        """
        from chibi.learning.mastery import MasteryCalculator, MasteryConfig, MasteryLevel

        config = MasteryConfig(min_attempts_for_mastery=3)
        calculator = MasteryCalculator(config)

        # Moderate accuracy: 2/5 = 40% (between learning_ratio 0.3 and proficient_ratio 0.6)
        level = calculator.calculate_level(
            total_attempts=5,
            correct_attempts=2,
            avg_quality_score=3.0,
        )

        assert level == MasteryLevel.LEARNING

    @pytest.mark.asyncio
    async def test_scenario_mastery_level_proficient(
        self,
        mastery_repository,
        user_repository,
        mock_user,
    ):
        """
        Scenario: Calculate mastery level for a proficient student

        Given: A student with good accuracy
        When: Mastery is calculated
        Then: They should be at "proficient" level
        """
        from chibi.learning.mastery import MasteryCalculator, MasteryConfig, MasteryLevel

        config = MasteryConfig(min_attempts_for_mastery=3)
        calculator = MasteryCalculator(config)

        # Good accuracy: 5/7 = ~71%
        level = calculator.calculate_level(
            total_attempts=7,
            correct_attempts=5,
            avg_quality_score=4.0,
        )

        assert level == MasteryLevel.PROFICIENT

    @pytest.mark.asyncio
    async def test_scenario_mastery_level_mastered(
        self,
        mastery_repository,
        user_repository,
        mock_user,
    ):
        """
        Scenario: Calculate mastery level for a master

        Given: A student with high accuracy and minimum attempts met
        When: Mastery is calculated
        Then: They should be at "mastered" level
        """
        from chibi.learning.mastery import MasteryCalculator, MasteryConfig, MasteryLevel

        config = MasteryConfig(min_attempts_for_mastery=3)
        calculator = MasteryCalculator(config)

        # High accuracy: 5/5 = 100% with high quality
        level = calculator.calculate_level(
            total_attempts=5,
            correct_attempts=5,
            avg_quality_score=4.8,
        )

        assert level == MasteryLevel.MASTERED


class TestGradeCalculationScenarios:
    """Test scenarios for grade calculation and export."""

    @pytest.mark.asyncio
    async def test_scenario_calculate_module_grade(
        self,
        configured_bot,
        sample_module,
        mock_user,
    ):
        """
        Scenario: Calculate grade for a module

        Given: A student with progress on a module
        When: Their grade is calculated
        Then: It should reflect their mastery levels
        """
        # Create user
        user = await configured_bot.user_repo.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Add mastery records
        for i, concept in enumerate(sample_module.concepts):
            await configured_bot.mastery_repo.update(
                user_id=user.id,
                concept_id=concept.id,
                total_attempts=5,
                correct_attempts=4,
                avg_quality_score=4.0,
                mastery_level="proficient",
            )

        # Get grade data
        summary = await configured_bot.mastery_repo.get_summary(user.id)

        # All concepts should be proficient
        assert summary.get("proficient", 0) == 2

    @pytest.mark.asyncio
    async def test_scenario_no_attempts_grade(
        self,
        configured_bot,
        sample_module,
        mock_user,
    ):
        """
        Scenario: Grade for a student with no attempts

        Given: A student who hasn't taken any quizzes
        When: Their grade is requested
        Then: They should have 0 progress
        """
        # Create user but no attempts
        user = await configured_bot.user_repo.get_or_create(
            discord_id=str(mock_user.id),
            username=mock_user.name,
        )

        # Get grade data
        summary = await configured_bot.mastery_repo.get_summary(user.id)

        # All should be zero
        total = sum(summary.values())
        assert total == 0


class TestCourseNavigationScenarios:
    """Test scenarios for course and module navigation."""

    @pytest.mark.asyncio
    async def test_scenario_get_concept_from_module(
        self,
        sample_module,
    ):
        """
        Scenario: Get a specific concept from a module

        Given: A module with concepts
        When: A specific concept is requested by ID
        Then: The correct concept should be returned
        """
        concept = sample_module.get_concept("concept-1")

        assert concept is not None
        assert concept.name == "Network Centrality"

    @pytest.mark.asyncio
    async def test_scenario_get_nonexistent_concept(
        self,
        sample_module,
    ):
        """
        Scenario: Get a concept that doesn't exist

        Given: A module with concepts
        When: A non-existent concept is requested
        Then: None should be returned
        """
        concept = sample_module.get_concept("nonexistent-concept")

        assert concept is None

    @pytest.mark.asyncio
    async def test_scenario_get_all_course_concepts(
        self,
        sample_course,
    ):
        """
        Scenario: Get all concepts across all modules

        Given: A course with multiple modules
        When: All concepts are requested
        Then: Concepts from all modules should be returned
        """
        all_concepts = sample_course.get_all_concepts()

        # Course has 2 modules with 2 + 1 = 3 concepts
        assert len(all_concepts) == 3
        assert "concept-1" in all_concepts
        assert "concept-2" in all_concepts
        assert "concept-3" in all_concepts
