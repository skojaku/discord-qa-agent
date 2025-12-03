# Prompt for Generating course.yaml

Use this prompt with Google Gemini (or other LLMs) to generate a `course.yaml` file for Chibi Bot.

---

## Prompt

```
You are helping me create a course.yaml configuration file for Chibi, an AI-powered Discord quiz bot that helps students learn course material through quizzes and natural conversation.

Before generating the course.yaml, please ask me clarifying questions to understand:

1. **Course Information**
   - What is the course name and code?
   - What is the course about (brief description)?
   - What level are the students (undergraduate, graduate, professional)?

2. **Module Structure**
   - How many modules does the course have?
   - What are the module names/topics?
   - Do you have online content URLs (markdown files, lecture notes) for each module that the bot can use for RAG (Retrieval-Augmented Generation)?

3. **Concepts and Learning Objectives**
   - For each module, what are the key concepts students should master?
   - What difficulty level (1-5) would you assign to each concept?
   - Are there prerequisite relationships between concepts?
   - What should quizzes focus on for each concept?

4. **Quiz Formats**
   - Which quiz formats do you want to support?
     - Multiple choice
     - Free form (open-ended)
     - Short answer
     - True/False
     - Fill in the blank

Please ask me these questions one by one or in logical groups. Once you have all the information, generate the course.yaml file following this exact structure:

---

### Required Structure

```yaml
# Course Configuration for Chibi Bot
course:
  name: "Course Name"
  code: "COURSE101"
  description: "Brief course description"

modules:
  - id: "m01"                    # Short unique identifier (e.g., m01, m02)
    name: "Module Name"
    description: "What this module covers"
    content_urls:                # List of URLs to course content (markdown, text)
      - "https://example.com/module1-notes.md"
    concepts:
      - id: "concept-id"         # Lowercase with hyphens (e.g., "binary-search")
        name: "Concept Name"
        type: "theory"           # "theory" or "practical"
        difficulty: 3            # 1 (easy) to 5 (hard)
        description: "Detailed description of the concept"
        quiz_focus: "What aspects to focus on for quizzes"
        prerequisites:           # List of concept IDs that should be learned first
          - "other-concept-id"

quiz_formats:
  - id: "multiple-choice"
    name: "Multiple Choice"
    description: "Choose the correct answer from 4 options (A, B, C, D)"
  - id: "free-form"
    name: "Free Form"
    description: "Explain concepts in your own words"
  # Add other formats as needed
```

### Field Requirements

**Course Section:**
- `name`: Full course name (required)
- `code`: Course code like "CS101" (required)
- `description`: 1-2 sentence description (optional but recommended)

**Modules:**
- `id`: Short unique ID like "m01", "m02" (required)
- `name`: Display name for the module (required)
- `description`: What the module covers (optional but recommended)
- `content_urls`: List of URLs to markdown/text files for RAG indexing (required for quiz generation)
- `concepts`: List of concepts in this module (required, at least 1)

**Concepts:**
- `id`: Lowercase hyphenated ID like "binary-search" (required, must be unique across all modules)
- `name`: Display name (required)
- `type`: Either "theory" or "practical" (default: "theory")
- `difficulty`: Integer 1-5 where 1=beginner, 5=advanced (default: 1)
- `description`: Full description of the concept (required)
- `quiz_focus`: What aspects quizzes should test (required for good quiz generation)
- `prerequisites`: List of concept IDs that should be learned first (optional, empty list if none)

**Quiz Formats:**
- `id`: Lowercase hyphenated ID (required)
- `name`: Display name (required)
- `description`: How this format works (required)

---

Now, please ask me the questions to gather the information needed for my course.
```

---

## Tips for Using This Prompt

1. **Provide Content URLs**: If you have lecture notes, slides, or documentation online (especially as markdown files), provide those URLs. The bot uses these for RAG to generate contextually relevant quizzes.

2. **Think About Prerequisites**: Consider which concepts build on others. This helps the mastery system track student progress appropriately.

3. **Be Specific in quiz_focus**: The more specific you are about what quizzes should test, the better the generated questions will be. Include:
   - Key terms to define
   - Calculations or algorithms to demonstrate
   - Common misconceptions to address
   - Real-world applications to connect

4. **Difficulty Guidelines**:
   - 1: Basic definitions and recall
   - 2: Simple applications and connections
   - 3: Intermediate analysis and problem-solving
   - 4: Complex synthesis and evaluation
   - 5: Advanced research-level concepts

5. **Content URL Best Practices**:
   - Use raw file URLs (e.g., GitHub raw URLs)
   - Prefer markdown or plain text formats
   - Ensure URLs are publicly accessible
   - Each module can have multiple content URLs
