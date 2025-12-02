"""Text chunking utilities for RAG."""

import re
from dataclasses import dataclass
from typing import List


@dataclass
class TextChunk:
    """A chunk of text with metadata."""

    text: str
    chunk_index: int
    source_id: str  # Module ID or document ID
    source_name: str  # Module name or document name
    start_char: int
    end_char: int

    @property
    def chunk_id(self) -> str:
        """Generate a unique ID for this chunk."""
        return f"{self.source_id}_chunk_{self.chunk_index}"


class TextChunker:
    """Utility for splitting text into overlapping chunks.

    Uses a recursive strategy that tries to split on natural boundaries
    (paragraphs, sentences, words) while maintaining chunk size limits.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        min_chunk_size: int = 50,
    ):
        """Initialize the chunker.

        Args:
            chunk_size: Target size for each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            min_chunk_size: Minimum chunk size (smaller chunks are merged)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

        # Separators in order of preference (try larger boundaries first)
        self.separators = [
            "\n\n",  # Paragraph breaks
            "\n",  # Line breaks
            ". ",  # Sentence endings
            "? ",
            "! ",
            "; ",  # Clause separators
            ", ",
            " ",  # Words
            "",  # Characters (last resort)
        ]

    def chunk_text(
        self,
        text: str,
        source_id: str,
        source_name: str,
    ) -> List[TextChunk]:
        """Split text into overlapping chunks.

        Args:
            text: The text to chunk
            source_id: Identifier for the source document
            source_name: Human-readable name for the source

        Returns:
            List of TextChunk objects
        """
        if not text or not text.strip():
            return []

        # Clean up text
        text = self._clean_text(text)

        # Split into initial chunks
        raw_chunks = self._recursive_split(text, self.separators)

        # Merge small chunks and create overlap
        merged_chunks = self._merge_and_overlap(raw_chunks)

        # Create TextChunk objects with metadata
        result = []
        current_pos = 0

        for i, chunk_text in enumerate(merged_chunks):
            # Find the position of this chunk in the original text
            start_pos = text.find(chunk_text[:50], current_pos)
            if start_pos == -1:
                start_pos = current_pos

            result.append(
                TextChunk(
                    text=chunk_text,
                    chunk_index=i,
                    source_id=source_id,
                    source_name=source_name,
                    start_char=start_pos,
                    end_char=start_pos + len(chunk_text),
                )
            )

            # Move position forward (accounting for overlap)
            current_pos = start_pos + len(chunk_text) - self.chunk_overlap

        return result

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Replace multiple whitespace with single space
        text = re.sub(r"[ \t]+", " ", text)
        # Replace multiple newlines with double newline
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Strip leading/trailing whitespace
        return text.strip()

    def _recursive_split(
        self,
        text: str,
        separators: List[str],
    ) -> List[str]:
        """Recursively split text using separators.

        Tries each separator in order until chunks are small enough.
        """
        if not text:
            return []

        # If text is small enough, return as single chunk
        if len(text) <= self.chunk_size:
            return [text]

        # Try each separator
        for sep in separators:
            if sep == "":
                # Last resort: split by character count
                return self._split_by_size(text)

            if sep in text:
                splits = text.split(sep)
                # Filter empty strings
                splits = [s for s in splits if s.strip()]

                if len(splits) > 1:
                    # Recursively process each split
                    result = []
                    for split in splits:
                        if len(split) <= self.chunk_size:
                            result.append(split)
                        else:
                            # Need to split further
                            sub_chunks = self._recursive_split(
                                split, separators[separators.index(sep) :]
                            )
                            result.extend(sub_chunks)
                    return result

        # Fallback: split by size
        return self._split_by_size(text)

    def _split_by_size(self, text: str) -> List[str]:
        """Split text into fixed-size chunks."""
        chunks = []
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk = text[i : i + self.chunk_size]
            if chunk.strip():
                chunks.append(chunk)
        return chunks

    def _merge_and_overlap(self, chunks: List[str]) -> List[str]:
        """Merge small chunks and create overlapping chunks."""
        if not chunks:
            return []

        result = []
        current_chunk = ""

        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            # If adding this chunk would exceed size, save current and start new
            if len(current_chunk) + len(chunk) + 1 > self.chunk_size:
                if current_chunk:
                    result.append(current_chunk.strip())
                # Start new chunk with overlap from previous
                if result and self.chunk_overlap > 0:
                    overlap_text = result[-1][-self.chunk_overlap :]
                    current_chunk = overlap_text + " " + chunk
                else:
                    current_chunk = chunk
            else:
                # Add to current chunk
                if current_chunk:
                    current_chunk += " " + chunk
                else:
                    current_chunk = chunk

        # Don't forget the last chunk
        if current_chunk.strip():
            result.append(current_chunk.strip())

        # Filter out chunks that are too small
        result = [c for c in result if len(c) >= self.min_chunk_size]

        return result
