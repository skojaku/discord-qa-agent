"""Prompt templates for Chibi bot."""


class PromptTemplates:
    """Collection of prompt templates for Chibi bot."""

    # Main system prompt for Chibi persona
    SYSTEM_PROMPT = """You are Chibi, an intelligent AI tutor robot from the 22nd century who specializes in helping students learn. You've traveled back in time to help students understand complex concepts using your advanced pedagogical algorithms.

{module_context}

{student_profile_context}

CORE INSTRUCTIONS:
CRITICAL: NEVER start responses with greetings like "Hi", "Hello", "Hey there", etc. Go straight to answering or helping.

Q&A INSTRUCTIONS:
- **INTUITION FIRST**: Start with relatable analogies, real-world examples, or everyday scenarios before any technical definitions
- **BUILD UNDERSTANDING GRADUALLY**: Go from familiar concepts to technical details
- **Use concrete examples**: Provide specific, tangible examples that students can visualize or relate to their experience
- **Make it relatable**: Connect abstract concepts to things students already know (games, social media, everyday activities)
- **Tell mini-stories**: Use brief narratives or scenarios to illustrate how concepts work in practice
- Keep responses BRIEF and conversational (2-3 sentences max) with Chibi's friendly personality
- DO NOT ask follow-up questions (slash commands are single interactions)
- Use proper syntax highlighting: ```python, ```r, ```qmd
- Use LaTeX notation: $inline$ or $$display$$
- Use a moderate number of emojis (one or two) to make explanations friendly and engaging

Remember: As Chibi, maintain your friendly, time-traveling robot personality with one or two emojis where appropriate. You're here to make learning enjoyable! 🚀"""

    # Context template for module information
    MODULE_CONTEXT = """CURRENT MODULE: {module_name}
MODULE DESCRIPTION: {module_description}

MODULE CONTENT:
{module_content}

CONCEPTS IN THIS MODULE:
{concept_list}"""

    # Student profile context template
    STUDENT_PROFILE = """STUDENT LEARNING PROFILE:
- Mastery Progress: {mastery_summary}
- Recent Topics: {recent_topics}"""

    # Quiz generation prompt
    QUIZ_PROMPT = """Generate a quiz question about the concept "{concept_name}" in the "{quiz_format}" format.

CONCEPT DETAILS:
- Description: {concept_description}
- Quiz Focus: {quiz_focus}

MODULE CONTENT FOR CONTEXT:
{module_content}

QUIZ FORMAT INSTRUCTIONS:
{format_instructions}

CRITICAL RULES:
- DO NOT GREET. GO STRAIGHT TO THE QUESTION.
- Ask EXACTLY ONE question about core concepts
- Focus on fundamental principles, not trivia
- NEVER provide the answer in the question
- Add a relevant emoji or two to make the quiz more inviting (e.g., 📝, 🤔)
- End quiz questions with "Please provide your answer, and I'll give you feedback! 🧠"
- ALWAYS generate a DIFFERENT question when asked for "another" or "different" question

Generate the quiz question now:"""

    # Format-specific instructions
    FORMAT_INSTRUCTIONS = {
        "multiple-choice": """MULTIPLE-CHOICE FORMAT:
- Provide 4 options (A, B, C, D) with exactly one correct answer
- Options should be plausible but clearly distinguishable
- Include the correct answer letter at the end in this exact format: [CORRECT: X]
  where X is A, B, C, or D""",
        "free-form": """FREE-FORM FORMAT:
- Ask ONE focused question about a SINGLE aspect of the concept
- DO NOT ask multi-part questions (e.g., "explain X, why Y, and describe Z")
- The question should test conceptual understanding, not memorization
- DO NOT expect mathematical formulas in answers (this is a chat interface)
- Good question starters: "Explain...", "Why does...", "What happens when...", "How would you..."
- Keep the expected answer scope to 2-4 sentences""",
        "short-answer": """SHORT-ANSWER FORMAT:
- Ask a question expecting a brief, specific response (1-3 sentences)
- Include the expected answer at the end in this exact format: [EXPECTED: your answer here]""",
        "true-false": """TRUE-FALSE FORMAT:
- Present a statement for true/false evaluation
- Ask the student to explain their reasoning briefly
- Include the correct answer at the end in this exact format: [CORRECT: True] or [CORRECT: False]""",
        "fill-blank": """FILL-IN-THE-BLANK FORMAT:
- Create a sentence with one key term missing, marked with _____
- The blank should test knowledge of an important concept
- Include the correct answer at the end in this exact format: [ANSWER: term]""",
    }

    # Quiz answer evaluation prompt
    EVALUATION_PROMPT = """Evaluate the student's answer to this quiz question.

QUESTION: {question}

STUDENT'S ANSWER: {student_answer}

{correct_answer_context}

CONCEPT BEING TESTED: {concept_name}
CONCEPT DESCRIPTION: {concept_description}

CRITICAL EVALUATION RULES:
1. ONLY evaluate based on what the QUESTION EXPLICITLY ASKED
2. DO NOT penalize for missing mathematical formulas (this is a chat interface)
3. DO NOT expect details that weren't asked for
4. Focus on whether the student understands the CORE CONCEPT

QUALITY SCORE CRITERIA (1-5):
- 5 (PASS): Correctly answers what was asked, shows clear understanding
- 4 (PASS): Good understanding with minor omissions
- 3 (PARTIAL): Captures the main idea but incomplete or slightly inaccurate
- 2 (FAIL): Shows some awareness but major gaps or misconceptions
- 1 (FAIL): Incorrect or irrelevant

STRICT OUTPUT FORMAT (you MUST follow this exactly):
Line 1: PASS, PARTIAL, or FAIL (nothing else on this line)
Line 2: Score (1-5) as a single number
Line 3 onwards: Your feedback starting with an emoji (✅ for pass, 🔶 for partial, ❌ for fail)

DO NOT ask follow-up questions - just provide feedback and end.

EXAMPLE OUTPUT:
PASS
4
✅ Good answer! You correctly explained that... [feedback continues]

NOW EVALUATE:"""

    @classmethod
    def get_system_prompt(
        cls,
        module_name: str = "",
        module_description: str = "",
        module_content: str = "",
        concept_list: str = "",
        mastery_summary: str = "No data yet",
        recent_topics: str = "None",
    ) -> str:
        """Build the complete system prompt with context."""
        module_context = ""
        if module_name:
            module_context = cls.MODULE_CONTEXT.format(
                module_name=module_name,
                module_description=module_description,
                module_content=module_content[:4000],  # Limit content length
                concept_list=concept_list,
            )

        student_context = cls.STUDENT_PROFILE.format(
            mastery_summary=mastery_summary,
            recent_topics=recent_topics,
        )

        return cls.SYSTEM_PROMPT.format(
            module_context=module_context,
            student_profile_context=student_context,
        )

    @classmethod
    def get_quiz_prompt(
        cls,
        concept_name: str,
        concept_description: str,
        quiz_focus: str,
        quiz_format: str,
        module_content: str = "",
    ) -> str:
        """Build the quiz generation prompt."""
        format_instructions = cls.FORMAT_INSTRUCTIONS.get(
            quiz_format, cls.FORMAT_INSTRUCTIONS["free-form"]
        )

        return cls.QUIZ_PROMPT.format(
            concept_name=concept_name,
            concept_description=concept_description,
            quiz_focus=quiz_focus,
            quiz_format=quiz_format,
            module_content=module_content[:3000],  # Limit content length
            format_instructions=format_instructions,
        )

    @classmethod
    def get_evaluation_prompt(
        cls,
        question: str,
        student_answer: str,
        concept_name: str,
        concept_description: str,
        correct_answer: str = "",
    ) -> str:
        """Build the answer evaluation prompt."""
        correct_answer_context = ""
        if correct_answer:
            correct_answer_context = f"EXPECTED/CORRECT ANSWER: {correct_answer}"

        return cls.EVALUATION_PROMPT.format(
            question=question,
            student_answer=student_answer,
            correct_answer_context=correct_answer_context,
            concept_name=concept_name,
            concept_description=concept_description,
        )
