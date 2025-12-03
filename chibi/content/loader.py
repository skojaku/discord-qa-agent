"""Content loader for fetching module content from URLs."""

import logging
from typing import Dict

import httpx

from .course import Course, Module

logger = logging.getLogger(__name__)


class ContentLoader:
    """Loads and caches module content from URLs."""

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self._cache: Dict[str, str] = {}

    async def load_module_content(self, module: Module) -> Dict[str, str]:
        """Load content for a single module from all its URLs.

        Args:
            module: The module to load content for

        Returns:
            Dict mapping URL to content
        """
        if not module.content_urls:
            logger.warning(f"No content URLs for module {module.id}")
            return {}

        results = {}
        for url in module.content_urls:
            cache_key = f"{module.id}:{url}"

            # Check cache
            if cache_key in self._cache:
                results[url] = self._cache[cache_key]
                continue

            # Fetch from URL
            content = await self._fetch_url(url)
            if content:
                self._cache[cache_key] = content
                results[url] = content

        # Store in module
        module.contents = results
        return results

    async def load_all_content(self, course: Course) -> Dict[str, Dict[str, str]]:
        """Load content for all modules in a course.

        Args:
            course: The course to load content for

        Returns:
            Dict mapping module_id to dict of URL -> content
        """
        results = {}
        for module in course.modules:
            url_contents = await self.load_module_content(module)
            results[module.id] = url_contents
            if url_contents:
                total_chars = sum(len(c) for c in url_contents.values())
                logger.info(
                    f"Loaded content for module {module.id}: "
                    f"{len(url_contents)} URLs, {total_chars} chars total"
                )
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

    def get_cached_content(self, module_id: str) -> Dict[str, str]:
        """Get cached content for a module.

        Args:
            module_id: The module ID

        Returns:
            Dict mapping URL to content for cached entries
        """
        prefix = f"{module_id}:"
        return {
            key[len(prefix):]: value
            for key, value in self._cache.items()
            if key.startswith(prefix)
        }

    def clear_cache(self) -> None:
        """Clear the content cache."""
        self._cache.clear()
        logger.info("Content cache cleared")

    def invalidate_module(self, module_id: str) -> None:
        """Invalidate cache for a specific module.

        Args:
            module_id: The module ID to invalidate
        """
        prefix = f"{module_id}:"
        keys_to_delete = [key for key in self._cache if key.startswith(prefix)]
        for key in keys_to_delete:
            del self._cache[key]
        if keys_to_delete:
            logger.info(f"Cache invalidated for module {module_id}: {len(keys_to_delete)} entries")
