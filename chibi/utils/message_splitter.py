"""
Message splitter utility for handling long Discord messages.

Discord has a 2000 character limit per message. This utility intelligently
splits content at natural boundaries while preserving formatting.
"""

import re
from typing import List


class MessageSplitter:
    """Splits long messages intelligently for Discord's character limit."""

    def __init__(self, max_length: int = 1900):
        """
        Initialize the message splitter.

        Args:
            max_length: Maximum length per chunk (buffer under 2000 for safety)
        """
        self.max_length = max_length

    def split(self, content: str) -> List[str]:
        """
        Split content at natural boundaries while preserving formatting.

        Splitting priority:
        1. Double newlines (paragraph boundaries)
        2. Single newlines
        3. Sentences (periods, question marks, exclamation marks)
        4. Words (as last resort)

        Preserves:
        - Code blocks (```...```)
        - LaTeX equations ($$...$$ and $...$)
        - Callout blocks (:::...:::)
        - Markdown formatting

        Args:
            content: The content to split

        Returns:
            List of content chunks, each under max_length
        """
        if len(content) <= self.max_length:
            return [content]

        # Check if content contains special blocks that shouldn't be split
        chunks = self._split_preserving_blocks(content)

        # Further split any chunks that are still too long
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= self.max_length:
                final_chunks.append(chunk)
            else:
                final_chunks.extend(self._split_long_chunk(chunk))

        return [chunk.strip() for chunk in final_chunks if chunk.strip()]

    def _split_preserving_blocks(self, content: str) -> List[str]:
        """
        Split content while preserving code blocks, LaTeX, and callouts intact.

        Returns:
            List of content segments with blocks preserved
        """
        chunks = []
        current_chunk = ""

        # Regex patterns for blocks that should not be split
        code_block_pattern = r'```[\s\S]*?```'
        latex_block_pattern = r'\$\$[\s\S]*?\$\$'
        callout_pattern = r':::[\s\S]*?:::'

        # Combined pattern
        block_pattern = f'({code_block_pattern}|{latex_block_pattern}|{callout_pattern})'

        # Split content into blocks and non-blocks
        parts = re.split(block_pattern, content, flags=re.MULTILINE)

        for part in parts:
            if not part:
                continue

            # Check if this is a special block
            is_block = (
                part.startswith('```') or
                part.startswith('$$') or
                part.startswith(':::')
            )

            if is_block:
                # If adding this block would exceed limit, save current chunk
                if current_chunk and len(current_chunk) + len(part) > self.max_length:
                    chunks.append(current_chunk)
                    current_chunk = part
                else:
                    current_chunk += part
            else:
                # Regular text - can be split at paragraphs
                paragraphs = part.split('\n\n')
                for para in paragraphs:
                    if len(current_chunk) + len(para) + 2 <= self.max_length:
                        if current_chunk and not current_chunk.endswith('\n\n'):
                            current_chunk += '\n\n'
                        current_chunk += para
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = para

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _split_long_chunk(self, chunk: str) -> List[str]:
        """
        Split a chunk that's still too long after preserving blocks.

        Falls back to splitting by sentences, then words if necessary.

        Args:
            chunk: The chunk to split

        Returns:
            List of smaller chunks
        """
        if len(chunk) <= self.max_length:
            return [chunk]

        # Try splitting by sentences
        sentence_pattern = r'([.!?])\s+'
        sentences = re.split(sentence_pattern, chunk)

        # Recombine sentences with their punctuation
        combined_sentences = []
        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                combined_sentences.append(sentences[i] + sentences[i + 1])
            else:
                combined_sentences.append(sentences[i])

        chunks = []
        current_chunk = ""

        for sentence in combined_sentences:
            if len(sentence) > self.max_length:
                # Single sentence too long - split by words
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                chunks.extend(self._split_by_words(sentence))
            elif len(current_chunk) + len(sentence) + 1 <= self.max_length:
                if current_chunk:
                    current_chunk += " "
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _split_by_words(self, text: str) -> List[str]:
        """
        Last resort: split text by words.

        Args:
            text: The text to split

        Returns:
            List of chunks split at word boundaries
        """
        words = text.split()
        chunks = []
        current_chunk = ""

        for word in words:
            if len(word) > self.max_length:
                # Single word too long - hard split
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                # Split the word itself
                for i in range(0, len(word), self.max_length):
                    chunks.append(word[i:i + self.max_length])
            elif len(current_chunk) + len(word) + 1 <= self.max_length:
                if current_chunk:
                    current_chunk += " "
                current_chunk += word
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = word

        if current_chunk:
            chunks.append(current_chunk)

        return chunks


def split_message(content: str, max_length: int = 1900) -> List[str]:
    """
    Convenience function to split a message.

    Args:
        content: The content to split
        max_length: Maximum length per chunk (default 1900 for safety buffer)

    Returns:
        List of content chunks
    """
    splitter = MessageSplitter(max_length)
    return splitter.split(content)
