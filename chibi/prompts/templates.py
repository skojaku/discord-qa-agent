"""Prompt templates for Chibi bot."""


class PromptTemplates:
    """Collection of prompt templates for Chibi bot."""

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

    # Format-specific instructions (only free-form is used)
    FORMAT_INSTRUCTIONS = {
        "free-form": """FREE-FORM FORMAT:
- Ask ONE focused question about a SINGLE aspect of the concept
- DO NOT ask multi-part questions (e.g., "explain X, why Y, and describe Z")
- The question should test conceptual understanding, not memorization
- DO NOT expect mathematical formulas in answers (this is a chat interface)
- Good question starters: "Explain...", "Why does...", "What happens when...", "How would you..."
- Keep the expected answer scope to 2-4 sentences""",
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
