"""Course and module data models."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml


@dataclass
class Concept:
    """A concept within a module that students should master."""

    id: str
    name: str
    type: str = "theory"
    difficulty: int = 1
    description: str = ""
    quiz_focus: str = ""
    prerequisites: List[str] = field(default_factory=list)


@dataclass
class Module:
    """A course module with content and concepts."""

    id: str
    name: str
    description: str = ""
    content_urls: List[str] = field(default_factory=list)
    concepts: List[Concept] = field(default_factory=list)
    contents: Dict[str, str] = field(default_factory=dict)  # URL -> content mapping

    def get_concept(self, concept_id: str) -> Optional[Concept]:
        """Get a concept by ID."""
        for concept in self.concepts:
            if concept.id == concept_id:
                return concept
        return None

    def get_concept_names(self) -> List[str]:
        """Get all concept names."""
        return [c.name for c in self.concepts]

    def get_all_content(self) -> str:
        """Get all content from all URLs concatenated.

        Returns:
            All URL contents joined with newlines
        """
        return "\n\n".join(self.contents.values())


@dataclass
class QuizFormat:
    """Available quiz format."""

    id: str
    name: str
    description: str = ""


@dataclass
class Course:
    """Course information and structure."""

    name: str
    code: str
    description: str = ""
    modules: List[Module] = field(default_factory=list)
    quiz_formats: List[QuizFormat] = field(default_factory=list)

    def get_module(self, module_id: str) -> Optional[Module]:
        """Get a module by ID."""
        for module in self.modules:
            if module.id == module_id:
                return module
        return None

    def find_module(self, query: str) -> Optional[Module]:
        """Find a module by ID, name, or concept name (fuzzy matching).

        Args:
            query: Module ID, name, or partial name to search for

        Returns:
            Matching module or None
        """
        if not query:
            return None

        query_lower = query.lower().strip()

        # 1. Exact ID match
        for module in self.modules:
            if module.id.lower() == query_lower:
                return module

        # 2. Exact name match (case-insensitive)
        for module in self.modules:
            if module.name.lower() == query_lower:
                return module

        # 3. Partial name match (query is substring of module name)
        for module in self.modules:
            if query_lower in module.name.lower():
                return module

        # 4. Partial name match (module name is substring of query)
        for module in self.modules:
            if module.name.lower() in query_lower:
                return module

        # 5. Check if query matches a concept name - return containing module
        for module in self.modules:
            for concept in module.concepts:
                if query_lower in concept.name.lower() or concept.name.lower() in query_lower:
                    return module

        # 6. Word-based fuzzy matching (any word in query matches module name)
        query_words = set(query_lower.split())
        for module in self.modules:
            module_words = set(module.name.lower().split())
            if query_words & module_words:  # intersection
                return module

        return None

    def get_module_choices(self) -> List[tuple]:
        """Get module choices for Discord autocomplete.

        Returns:
            List of (display_name, module_id) tuples
        """
        return [(f"{m.id}: {m.name}", m.id) for m in self.modules]

    def get_all_concepts(self) -> Dict[str, Concept]:
        """Get all concepts across all modules.

        Returns:
            Dict mapping concept_id to Concept
        """
        concepts = {}
        for module in self.modules:
            for concept in module.concepts:
                concepts[concept.id] = concept
        return concepts

    def get_quiz_format(self, format_id: str) -> Optional[QuizFormat]:
        """Get a quiz format by ID."""
        for fmt in self.quiz_formats:
            if fmt.id == format_id:
                return fmt
        return None

    def get_quiz_format_choices(self) -> List[tuple]:
        """Get quiz format choices for Discord autocomplete.

        Returns:
            List of (display_name, format_id) tuples
        """
        return [(f.name, f.id) for f in self.quiz_formats]


def load_course(course_path: str = "course.yaml") -> Course:
    """Load course configuration from YAML file.

    Args:
        course_path: Path to the course YAML file

    Returns:
        Course object with all modules and concepts
    """
    path = Path(course_path)
    if not path.exists():
        raise FileNotFoundError(f"Course file not found: {course_path}")

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    course_data = data.get("course", {})

    # Parse modules
    modules = []
    for mod_data in data.get("modules", []):
        concepts = []
        for concept_data in mod_data.get("concepts", []):
            concept = Concept(
                id=concept_data.get("id", ""),
                name=concept_data.get("name", ""),
                type=concept_data.get("type", "theory"),
                difficulty=concept_data.get("difficulty", 1),
                description=concept_data.get("description", ""),
                quiz_focus=concept_data.get("quiz_focus", ""),
                prerequisites=concept_data.get("prerequisites", []),
            )
            concepts.append(concept)

        module = Module(
            id=mod_data.get("id", ""),
            name=mod_data.get("name", ""),
            description=mod_data.get("description", ""),
            content_urls=mod_data.get("content_urls", []),
            concepts=concepts,
        )
        modules.append(module)

    # Parse quiz formats
    quiz_formats = []
    for fmt_data in data.get("quiz_formats", []):
        quiz_format = QuizFormat(
            id=fmt_data.get("id", ""),
            name=fmt_data.get("name", ""),
            description=fmt_data.get("description", ""),
        )
        quiz_formats.append(quiz_format)

    return Course(
        name=course_data.get("name", ""),
        code=course_data.get("code", ""),
        description=course_data.get("description", ""),
        modules=modules,
        quiz_formats=quiz_formats,
    )
