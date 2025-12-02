"""Base service class for all services."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Config
    from ..content.course import Course
    from ..database.repository import Repository
    from ..llm.manager import LLMManager


class BaseService:
    """Base class for all services.

    Provides access to common dependencies through dependency injection.
    """

    def __init__(
        self,
        repository: "Repository",
        llm_manager: "LLMManager",
        course: "Course",
        config: "Config",
    ):
        """Initialize the base service.

        Args:
            repository: Database repository for data access
            llm_manager: LLM manager for AI responses
            course: Course configuration with modules and concepts
            config: Application configuration
        """
        self.repository = repository
        self.llm_manager = llm_manager
        self.course = course
        self.config = config
