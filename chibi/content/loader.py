"""Content loader for fetching module content from URLs."""

import logging
from typing import Dict, Optional

import httpx

from .course import Course, Module

logger = logging.getLogger(__name__)


class ContentLoader:
    """Loads and caches module content from URLs."""

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self._cache: Dict[str, str] = {}

    async def load_module_content(self, module: Module) -> str:
        """Load content for a single module.

        Args:
            module: The module to load content for

        Returns:
            The module content as a string
        """
        if not module.content_url:
            logger.warning(f"No content URL for module {module.id}")
            return ""

        # Check cache
        if module.id in self._cache:
            return self._cache[module.id]

        # Fetch from URL
        content = await self._fetch_url(module.content_url)
        if content:
            self._cache[module.id] = content
            module.content = content

        return content

    async def load_all_content(self, course: Course) -> Dict[str, str]:
        """Load content for all modules in a course.

        Args:
            course: The course to load content for

        Returns:
            Dict mapping module_id to content
        """
        results = {}
        for module in course.modules:
            content = await self.load_module_content(module)
            results[module.id] = content
            if content:
                logger.info(f"Loaded content for module {module.id} ({len(content)} chars)")
            else:
                logger.warning(f"Failed to load content for module {module.id}")

        return results

    async def _fetch_url(self, url: str) -> str:
        """Fetch content from a URL with retries.

        Args:
            url: The URL to fetch

        Returns:
            The content as a string, or empty string on failure
        """
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response.text

            except httpx.TimeoutException:
                logger.warning(f"Timeout fetching {url} (attempt {attempt + 1})")
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error fetching {url}: {e.response.status_code}")
                break  # Don't retry on HTTP errors
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")

        return ""

    def get_cached_content(self, module_id: str) -> Optional[str]:
        """Get cached content for a module.

        Args:
            module_id: The module ID

        Returns:
            The cached content, or None if not cached
        """
        return self._cache.get(module_id)

    def clear_cache(self) -> None:
        """Clear the content cache."""
        self._cache.clear()
        logger.info("Content cache cleared")

    def invalidate_module(self, module_id: str) -> None:
        """Invalidate cache for a specific module.

        Args:
            module_id: The module ID to invalidate
        """
        if module_id in self._cache:
            del self._cache[module_id]
            logger.info(f"Cache invalidated for module {module_id}")
