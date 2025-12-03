"""Pytest configuration and shared fixtures for Chibi bot tests."""

import asyncio
import sys
from pathlib import Path
from types import ModuleType
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock the llm_quiz module that may not be available in test environment
# This must be done BEFORE importing any chibi modules
if "llm_quiz" not in sys.modules:
    mock_llm_quiz = ModuleType("llm_quiz")
    mock_llm_quiz.AnswerQuizQuestion = MagicMock()
    mock_llm_quiz.EvaluateAnswer = MagicMock()
    sys.modules["llm_quiz"] = mock_llm_quiz

from tests.mocks.discord_mocks import (
    MockBot,
    MockChannel,
    MockGuild,
    MockInteraction,
    MockMessage,
    MockUser,
    ScenarioContext,
    create_mock_interaction,
    create_mock_message,
)
from tests.mocks.llm_mocks import (
    MockLLMManager,
    MockLLMProvider,
    MockLLMResponse,
    create_evaluation_mock_provider,
    create_quiz_mock_provider,
    quiz_evaluation_generator,
    quiz_question_generator,
)


# ============================================================================
# Event Loop Configuration
# ============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def test_database():
    """Create an in-memory database for testing."""
    from chibi.database.connection import Database

    # Use in-memory SQLite
    db = Database(":memory:")
    await db.connect()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def user_repository(test_database):
    """Create a user repository with the test database."""
    from chibi.database.repositories import UserRepository

    return UserRepository(test_database)


@pytest_asyncio.fixture
async def quiz_repository(test_database):
    """Create a quiz repository with the test database."""
    from chibi.database.repositories import QuizRepository

    return QuizRepository(test_database)


@pytest_asyncio.fixture
async def mastery_repository(test_database):
    """Create a mastery repository with the test database."""
    from chibi.database.repositories import MasteryRepository

    return MasteryRepository(test_database)


@pytest_asyncio.fixture
async def llm_quiz_repository(test_database):
    """Create an LLM quiz repository with the test database."""
    from chibi.database.repositories import LLMQuizRepository

    return LLMQuizRepository(test_database)


# ============================================================================
# Course Fixtures
# ============================================================================


@pytest.fixture
def sample_concept():
    """Create a sample concept for testing."""
    from chibi.content.course import Concept

    return Concept(
        id="concept-1",
        name="Network Centrality",
        type="theory",
        difficulty=2,
        description="Understanding measures of node importance in networks",
        quiz_focus="Calculate and interpret centrality measures",
    )


@pytest.fixture
def sample_concept_2():
    """Create a second sample concept for testing."""
    from chibi.content.course import Concept

    return Concept(
        id="concept-2",
        name="Graph Theory Basics",
        type="theory",
        difficulty=1,
        description="Fundamental concepts in graph theory",
        quiz_focus="Identify graph types and properties",
    )


@pytest.fixture
def sample_module(sample_concept, sample_concept_2):
    """Create a sample module for testing."""
    from chibi.content.course import Module

    return Module(
        id="module-1",
        name="Network Analysis Fundamentals",
        description="Introduction to network analysis concepts",
        content_url="",
        concepts=[sample_concept, sample_concept_2],
        content="This module covers network centrality measures including degree, betweenness, and eigenvector centrality.",
    )


@pytest.fixture
def sample_module_2():
    """Create a second sample module for testing."""
    from chibi.content.course import Concept, Module

    return Module(
        id="module-2",
        name="Advanced Graph Algorithms",
        description="Advanced algorithms for graph analysis",
        content_url="",
        concepts=[
            Concept(
                id="concept-3",
                name="Shortest Path Algorithms",
                type="algorithm",
                difficulty=3,
                description="Algorithms for finding shortest paths",
                quiz_focus="Apply Dijkstra's and BFS algorithms",
            ),
        ],
        content="This module covers shortest path algorithms.",
    )


@pytest.fixture
def sample_course(sample_module, sample_module_2):
    """Create a sample course for testing."""
    from chibi.content.course import Course, QuizFormat

    return Course(
        name="Network Science 101",
        code="NS101",
        description="Introduction to Network Science",
        modules=[sample_module, sample_module_2],
        quiz_formats=[
            QuizFormat(id="free-form", name="Free Form", description="Open-ended questions"),
        ],
    )


# ============================================================================
# LLM Fixtures
# ============================================================================


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def mock_quiz_provider():
    """Create a mock LLM provider configured for quiz generation."""
    return create_quiz_mock_provider()


@pytest.fixture
def mock_evaluation_provider():
    """Create a mock LLM provider configured for answer evaluation."""
    return create_evaluation_mock_provider()


@pytest.fixture
def mock_llm_manager(mock_quiz_provider, mock_evaluation_provider):
    """Create a mock LLM manager."""
    return MockLLMManager(
        primary_provider=mock_quiz_provider,
        fallback_provider=mock_evaluation_provider,
    )


# ============================================================================
# Service Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def quiz_service(mastery_repository, quiz_repository, mock_llm_manager):
    """Create a quiz service with mock dependencies."""
    from chibi.learning.mastery import MasteryCalculator, MasteryConfig
    from chibi.services.quiz_service import QuizService

    mastery_config = MasteryConfig(min_attempts_for_mastery=3)
    mastery_calculator = MasteryCalculator(mastery_config)

    return QuizService(
        mastery_repo=mastery_repository,
        quiz_repo=quiz_repository,
        llm_manager=mock_llm_manager,
        mastery_calculator=mastery_calculator,
        max_tokens=1000,
    )


@pytest_asyncio.fixture
async def grade_service(user_repository, mastery_repository, sample_course):
    """Create a grade service with mock dependencies."""
    from chibi.services.grade_service import GradeService

    return GradeService(
        user_repo=user_repository,
        mastery_repo=mastery_repository,
        course=sample_course,
    )


# ============================================================================
# Discord Fixtures
# ============================================================================


@pytest.fixture
def mock_user():
    """Create a mock Discord user."""
    return MockUser(id=123456789, name="TestStudent", display_name="TestStudent")


@pytest.fixture
def mock_channel():
    """Create a mock Discord channel."""
    return MockChannel(id=987654321, name="test-channel")


@pytest.fixture
def mock_guild(mock_channel):
    """Create a mock Discord guild."""
    return MockGuild(id=111222333, name="Test Server", channels=[mock_channel])


@pytest.fixture
def mock_interaction(mock_user, mock_channel, mock_guild):
    """Create a mock Discord interaction."""
    mock_channel.guild = mock_guild
    return MockInteraction(
        user=mock_user,
        channel=mock_channel,
        guild=mock_guild,
    )


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    return MockBot()


# ============================================================================
# Scenario Context Fixtures
# ============================================================================


@pytest.fixture
def scenario_context():
    """Create a scenario context for tracking test state."""
    return ScenarioContext()


@pytest.fixture
def student_scenario_context(mock_user, mock_channel, mock_guild):
    """Create a pre-configured scenario context for student interactions."""
    context = ScenarioContext()
    context.user = mock_user
    context.channel = mock_channel
    context.guild = mock_guild
    return context


# ============================================================================
# Integration Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def configured_bot(
    test_database,
    user_repository,
    quiz_repository,
    mastery_repository,
    llm_quiz_repository,
    sample_course,
    mock_llm_manager,
):
    """Create a fully configured bot-like context for integration tests.

    This doesn't create a real bot, but provides all the services
    and repositories that would be attached to a real bot.
    """
    from chibi.learning.mastery import MasteryCalculator, MasteryConfig
    from chibi.services.grade_service import GradeService
    from chibi.services.quiz_service import QuizService

    mastery_config = MasteryConfig(min_attempts_for_mastery=3)
    mastery_calculator = MasteryCalculator(mastery_config)

    # Create services
    quiz_service = QuizService(
        mastery_repo=mastery_repository,
        quiz_repo=quiz_repository,
        llm_manager=mock_llm_manager,
        mastery_calculator=mastery_calculator,
        max_tokens=1000,
    )

    grade_service = GradeService(
        user_repo=user_repository,
        mastery_repo=mastery_repository,
        course=sample_course,
    )

    # Return a context object with all services
    class BotContext:
        pass

    ctx = BotContext()
    ctx.database = test_database
    ctx.user_repo = user_repository
    ctx.quiz_repo = quiz_repository
    ctx.mastery_repo = mastery_repository
    ctx.llm_quiz_repo = llm_quiz_repository
    ctx.course = sample_course
    ctx.llm_manager = mock_llm_manager
    ctx.quiz_service = quiz_service
    ctx.grade_service = grade_service

    return ctx


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def test_user(user_repository, mock_user):
    """Create a test user in the database."""
    user = await user_repository.get_or_create(
        discord_id=str(mock_user.id),
        username=mock_user.name,
    )
    return user


@pytest_asyncio.fixture
async def test_user_with_history(
    user_repository,
    quiz_repository,
    mastery_repository,
    sample_module,
    mock_user,
):
    """Create a test user with quiz history."""
    # Create user
    user = await user_repository.get_or_create(
        discord_id=str(mock_user.id),
        username=mock_user.name,
    )

    # Add some quiz attempts
    concept = sample_module.concepts[0]

    await quiz_repository.log_attempt(
        user_id=user.id,
        module_id=sample_module.id,
        concept_id=concept.id,
        quiz_format="free-form",
        question="What is network centrality?",
        user_answer="It measures importance of nodes",
        correct_answer=None,
        is_correct=True,
        llm_feedback="Good answer!",
        llm_quality_score=4,
    )

    # Update mastery
    mastery = await mastery_repository.get_or_create(user.id, concept.id)
    await mastery_repository.update(
        user_id=user.id,
        concept_id=concept.id,
        total_attempts=1,
        correct_attempts=1,
        avg_quality_score=4.0,
        mastery_level="learning",
    )

    return user


# ============================================================================
# Utility Fixtures
# ============================================================================


@pytest.fixture
def assert_embed_contains():
    """Fixture that returns an assertion helper for embed content."""

    def _assert_embed_contains(embed, expected_text: str, field_name: str = None):
        """Assert that an embed contains expected text."""
        if field_name:
            for field in getattr(embed, "fields", []):
                if field.name == field_name:
                    assert expected_text in str(field.value), \
                        f"Expected '{expected_text}' in field '{field_name}'"
                    return
            pytest.fail(f"Field '{field_name}' not found in embed")
        else:
            # Check title, description, and all fields
            embed_text = str(getattr(embed, "title", "")) + \
                        str(getattr(embed, "description", ""))
            for field in getattr(embed, "fields", []):
                embed_text += str(field.name) + str(field.value)

            assert expected_text in embed_text, \
                f"Expected '{expected_text}' in embed content"

    return _assert_embed_contains
