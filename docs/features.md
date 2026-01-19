# Features Guide

Complete overview of Chibi's learning features and systems.

## Table of Contents

- [Quiz System](#quiz-system)
- [Mastery System](#mastery-system)
- [LLM Quiz Challenge](#llm-quiz-challenge)
- [Attendance Tracking](#attendance-tracking)
- [RAG with Contextual Retrieval](#rag-with-contextual-retrieval)
- [Natural Language Interface](#natural-language-interface)
- [Conversation Memory](#conversation-memory)

---

## Quiz System

### Overview

Free-form quizzes where students explain concepts in their own words. AI evaluates responses for comprehension and provides detailed feedback.

### How It Works

1. **Student requests a quiz:**
   ```
   /quiz module:network-science
   ```

2. **Bot generates a question** based on course content:
   - Uses RAG to retrieve relevant context
   - Selects a concept from the specified module
   - Generates a question focused on that concept

3. **Student submits answer** via modal dialog

4. **AI evaluates the response:**
   - Checks factual correctness
   - Assesses depth of understanding
   - Provides constructive feedback
   - Assigns a quality score (1-5)

5. **Progress is tracked:**
   - Correct answers build mastery
   - Feedback helps students improve
   - History is saved for follow-up questions

### Quiz Formats

Currently supported:
- **Free Form** - Open-ended questions requiring paragraph responses

Configured quiz formats (in `course.yaml`):
- Multiple Choice
- True/False
- Short Answer
- Fill in the Blank

*Note: Only free form is currently implemented. Other formats are defined for future use.*

---

## Mastery System

### Overview

Tracks student progress per concept using a hybrid evaluation system that combines LLM quality scores with accuracy ratios.

### Mastery Levels

| Level | Emoji | Description | Requirements |
|-------|-------|-------------|--------------|
| **Novice** | ⬜ | Just starting | Initial state |
| **Learning** | 🟨 | Making progress | Some correct attempts |
| **Proficient** | 🟦 | Strong understanding | Consistent performance |
| **Mastered** | 🟩 | Expert level | Min attempts + high quality |

### Calculation Method

**Hybrid Evaluation:**
1. **Quality Score** (1-5 from LLM) - Depth of understanding
2. **Accuracy Ratio** - Correct attempts / Total attempts

**Level Requirements (configurable in `config.yaml`):**

```yaml
mastery:
  min_attempts_for_mastery: 3
  quality_threshold: 3.5
  correct_ratio_threshold: 0.7
```

**Logic:**
- **Novice** → Starting point
- **Learning** → At least 1 correct attempt
- **Proficient** → Correct ratio ≥ 0.7 AND average quality ≥ 3.5
- **Mastered** → Proficient + at least min_attempts correct answers

### Viewing Progress

Students can check progress with:
```
/status                    # Overall progress across all modules
/status module:m01         # Detailed progress for one module
```

Admins can view any student's progress with:
```
/admin-status student:@StudentName
/admin-status student:@StudentName module:m01
```

---

## LLM Quiz Challenge

### Overview

Students create quiz questions to challenge an AI. If the student can answer correctly but the AI cannot, the student wins. This encourages critical thinking and deep understanding.

### How It Works

1. **Student starts challenge:**
   ```
   /llm-quiz module:network-science
   ```

2. **Student creates a question** via modal:
   - Writes a question
   - Provides their answer

3. **Quiz Model attempts to answer:**
   - Uses RAG to access course content
   - Generates its best answer
   - Same context available to both student and AI

4. **Evaluator Model judges both answers:**
   - Student answer: Correct or Incorrect
   - LLM answer: Correct or Incorrect

5. **Outcome determined:**
   - ✅ **Student Wins:** Student correct AND LLM incorrect
   - ❌ **LLM Wins:** LLM correct (or both wrong)
   - 📊 **Progress tracked:** Wins counted toward module completion

### Anti-Cheat System

**Embedding-based similarity detection** prevents reusing questions:

- All **winning questions** are stored with embeddings
- New questions are compared to previous questions
- Questions above similarity threshold (default: 0.85) are rejected
- Students must create genuinely unique questions

**What gets checked:**
- Only winning questions (losses don't count)
- Similarity is per-module (can reuse across modules)
- Threshold is configurable in `config.yaml`

### Progress Tracking

Each module has a target number of wins (default: 3):

```yaml
llm_quiz:
  target_wins_per_module: 3
```

View progress:
```
/status module:network-science
```

Shows: "LLM Quiz: 2/3 wins" with emoji indicators.

### Configuration

```yaml
llm_quiz:
  target_wins_per_module: 3  # Wins needed per module
  quiz_model: "openrouter/google/gemma-3-12b-it"  # Model that answers
  evaluator_model: "openrouter/google/gemini-2.5-flash-lite"  # Judge
  base_url: "https://openrouter.ai/api/v1"
```

---

## Attendance Tracking

### Overview

Built-in attendance system with rotating codes for classroom use. Prevents code-sharing while being easy to use.

### Features

- **Rotating codes** - Change every 15 seconds
- **Student registration** - Link Discord to student IDs
- **Multiple submission tracking** - Only latest submission counts
- **Manual overrides** - Excuse absences, mark present, remove records
- **CSV export** - Download attendance data

### Student Workflow

1. **Register once (optional but recommended):**
   ```
   /register student_id:12345 student_name:John Doe
   ```

2. **Submit attendance during class:**
   ```
   /here code:ABC123
   ```

### Admin Workflow

1. **Start session:**
   ```
   /admin-open-attendance
   ```
   - Code appears in admin channel (show on projector)
   - Students notified in attendance channel
   - Code rotates automatically

2. **Close session:**
   ```
   /admin-close-attendance
   ```
   - Records saved to database
   - Session summary displayed

3. **Export records:**
   ```
   /admin-export-attendance
   ```
   Gets CSV with: student_id, name, Discord username, timestamp, status

### Manual Attendance Management

**Mark student excused:**
```
/admin-excuse student:@StudentName date:2025-01-19
```

**Manually mark present:**
```
/admin-mark-present student:@StudentName date:2025-01-19
```

**Remove attendance record:**
```
/admin-remove-attendance student:@StudentName date:2025-01-19
```

### Configuration

```yaml
attendance:
  code_rotation_interval: 15  # Seconds between code changes
  code_length: 4              # Length of attendance codes
```

Set channel IDs in `.env`:
```
ATTENDANCE_CHANNEL_ID=123456789
ADMIN_CHANNEL_ID=987654321
```

---

## RAG with Contextual Retrieval

### Overview

Retrieval-Augmented Generation (RAG) allows the bot to search course content when answering questions. Enhanced with [Anthropic's Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) technique for improved accuracy.

### How It Works

**Traditional RAG Problem:**
- Chunks lose document context
- "Revenue grew 3%" - what company? what period?

**Contextual Retrieval Solution:**
1. **Documents are split into chunks** (default: 500 chars, 100 overlap)
2. **For each chunk, an LLM generates context** (50-100 tokens)
3. **Context is prepended before embedding:**
   - Original: "Revenue grew 3%"
   - Contextualized: "This chunk is from ACME Corp's Q2 2023 report. Revenue grew 3%"
4. **Original text stored for display, contextualized text for search**

### Configuration

```yaml
contextual_retrieval:
  enabled: true
  max_context_tokens: 100     # Max tokens for context summary
  batch_size: 5               # Chunks to process concurrently
  batch_delay_seconds: 0.5    # Rate limiting between batches
  temperature: 0.3            # LLM temperature for context
  model: "default"            # Use main LLM or specify custom
```

### When RAG is Used

- **Quiz generation** - Find relevant content for questions
- **Question answering** - Search course materials for answers
- **LLM Quiz Challenge** - Give AI access to course content
- **Natural language interactions** - Answer student questions

### Content Sources

Configure in `course.yaml`:

```yaml
modules:
  - id: "m01"
    content_urls:
      - "https://example.com/lecture1.md"
      - "https://example.com/notes.md"
```

**Best Practices:**
- Use raw file URLs (e.g., GitHub raw links)
- Prefer markdown or plain text
- Ensure URLs are publicly accessible
- Update URLs when content changes

---

## Natural Language Interface

### Overview

Students can interact naturally without remembering specific commands.

### Interaction Methods

1. **@mention the bot:**
   ```
   @ChibiBot explain network centrality
   ```

2. **Direct message:**
   ```
   DM: quiz me on module 1
   ```

3. **Auto-response channels** (no mention needed):
   ```
   Just type: what is betweenness centrality?
   ```

### ReAct Framework

The bot uses **Reasoning + Acting** to intelligently decide actions:

1. **Student asks:** "quiz me on module 1"
2. **Bot reasons:** This is a quiz request
3. **Bot acts:** Invokes quiz tool
4. **Bot responds:** Generates quiz question

### Tools Available

- **Quiz** - Generate quiz questions
- **LLM Quiz** - Start LLM Challenge
- **Status** - Show progress
- **Search** - Search course content
- **Assistant** - General Q&A with RAG

### Configuration

Set auto-response channels in `.env`:

```
NL_ROUTING_CHANNELS=123456789,987654321
```

---

## Conversation Memory

### Overview

Tracks conversation history to enable contextual follow-up questions.

### What Gets Stored

**Per user, per channel:**
- User messages
- Bot responses
- Quiz questions and answers
- Feedback and evaluations
- Tool invocations

### Example Use Cases

**After a quiz:**
```
Student: "what was my answer to that last question?"
Bot: "You answered: [shows previous answer]"
```

**Follow-up questions:**
```
Student: "can you explain that concept in more detail?"
Bot: [Retrieves previous context and elaborates]
```

**Reflecting on progress:**
```
Student: "how can I improve?"
Bot: [Analyzes recent quiz attempts and provides advice]
```

### Memory Scope

- **User-specific** - Each user has separate memory
- **Channel-specific** - DMs separate from server channels
- **Session-based** - Cleared on bot restart (stored in memory, not database)

### Privacy

- Memory is ephemeral (not persisted to database)
- Only accessible to the individual user
- Not shared across users or channels

---

## Related Documentation

- [Commands Reference](commands.md) - All available commands
- [Configuration Guide](configuration.md) - Detailed config options
- [Setup Guide](../SETUP_GUIDE.md) - Installation and setup
- [Google Sheets Setup](google-sheets-setup.md) - Backup system setup
