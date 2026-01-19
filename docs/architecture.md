# Architecture Guide

Understanding the code structure and data flow in Chibi Bot.

## Table of Contents

- [High-Level Overview](#high-level-overview)
- [Directory Structure](#directory-structure)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Key Patterns](#key-patterns)

---

## High-Level Overview

Chibi is a Discord quiz bot that uses LangGraph for natural language routing, ChromaDB for RAG, and SQLite for user data. The architecture follows a layered pattern:

```
Discord Events → Agent Graph → Tools → Services → Repositories → Database
```

### Architecture Layers

1. **Discord Layer** (`bot.py`, `cogs/`) - Handles Discord events and user interactions
2. **Agent Layer** (`agent/`) - LangGraph StateGraph for natural language routing
3. **Tool Layer** (`tools/`) - Intent-specific tools (quiz, assistant, status)
4. **Service Layer** (`services/`) - Business logic and orchestration
5. **Repository Layer** (`database/repositories/`) - Data access abstraction
6. **Data Layer** (SQLite + ChromaDB) - Persistence

---

## Directory Structure

```
discord-qa-agent/
├── chibi/                      # Main bot package
│   ├── agent/                  # LangGraph agent system
│   │   ├── graph.py           # Main StateGraph definition
│   │   ├── memory.py          # Conversation history
│   │   ├── state.py           # Agent state schema
│   │   ├── context_manager.py # Context compression agent
│   │   └── nodes/             # Graph nodes (router, dispatcher)
│   │
│   ├── backup/                 # Google Sheets export/import
│   │   ├── backup_service.py  # Main backup orchestrator
│   │   ├── google_sheets_client.py  # OAuth + API client
│   │   ├── sheets_exporter.py # Export to Sheets
│   │   └── sheets_importer.py # Import from Sheets
│   │
│   ├── cogs/                   # Discord command handlers
│   │   ├── quiz.py            # /quiz command
│   │   ├── llm_quiz.py        # /llm-quiz command
│   │   ├── status.py          # /status command
│   │   ├── modules.py         # /modules command
│   │   ├── guidance.py        # /guidance command
│   │   ├── admin_slash.py     # /admin-* commands
│   │   ├── attendance_slash.py # Attendance slash commands
│   │   ├── backup_cog.py      # /export-progress, /import-progress
│   │   ├── admin.py           # Deprecated prefix commands
│   │   └── attendance.py      # Deprecated attendance prefix commands
│   │
│   ├── content/                # Course content management
│   │   ├── course.py          # Course data model
│   │   └── loader.py          # Fetch content from URLs
│   │
│   ├── database/               # Data persistence
│   │   ├── connection.py      # SQLite connection manager
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── mappers.py         # ORM to domain object mappers
│   │   └── repositories/      # Data access layer
│   │       ├── user_repository.py
│   │       ├── quiz_repository.py
│   │       ├── mastery_repository.py
│   │       ├── llm_quiz_repository.py
│   │       ├── attendance_repository.py
│   │       ├── rag_repository.py        # ChromaDB for RAG
│   │       └── similarity_repository.py # ChromaDB for anti-cheat
│   │
│   ├── learning/               # Mastery calculation
│   │   └── mastery.py         # Hybrid quality + accuracy scoring
│   │
│   ├── llm/                    # LLM provider abstraction
│   │   ├── manager.py         # LLMManager with fallback
│   │   ├── base.py            # Base provider interface
│   │   ├── ollama_provider.py # Local Ollama integration
│   │   └── openrouter_provider.py # Cloud OpenRouter integration
│   │
│   ├── prompts/                # LLM prompt templates
│   │   └── templates.py       # Jinja2 templates for prompts
│   │
│   ├── services/               # Business logic
│   │   ├── quiz_service.py    # Quiz generation + evaluation
│   │   ├── llm_quiz_service.py # LLM Challenge game logic
│   │   ├── similarity_service.py # Anti-cheat system
│   │   ├── rag_service.py     # RAG retrieval
│   │   ├── search_agent.py    # Centralized RAG for all tools
│   │   ├── content_indexer.py # Index course content
│   │   ├── contextual_chunking_service.py # Context-enhanced chunking
│   │   ├── embedding_service.py # Embedding generation
│   │   ├── grade_service.py   # Grade export to CSV
│   │   ├── guidance_service.py # Personalized study guidance
│   │   ├── attendance_session.py # Attendance session manager
│   │   ├── pending_quiz_manager.py # In-flight quiz tracking
│   │   └── chunking.py        # Text chunking utilities
│   │
│   ├── tools/                  # Agent tools (ReAct pattern)
│   │   ├── base.py            # Base Tool interface
│   │   ├── registry.py        # Tool auto-discovery
│   │   ├── quiz/              # Quiz tool
│   │   ├── llm_quiz/          # LLM Quiz tool
│   │   ├── status/            # Status tool
│   │   ├── guidance/          # Guidance tool
│   │   └── search/            # Search tool
│   │
│   ├── ui/                     # Discord UI components
│   │   ├── embeds/            # Discord embeds (rich messages)
│   │   │   ├── quiz.py
│   │   │   └── status.py
│   │   ├── views/             # Discord views (buttons, modals)
│   │   │   └── admin_review.py
│   │   └── formatters.py      # Text formatting utilities
│   │
│   ├── utils/                  # Utility modules
│   │   ├── code_generator.py # Attendance code generation
│   │   └── errors.py          # Custom exception types
│   │
│   ├── bot.py                  # Main ChibiBot class
│   ├── config.py               # Config loading and validation
│   └── constants.py            # Constants and enums
│
├── tests/                      # Test suite
│   ├── conftest.py            # Shared fixtures
│   ├── mocks/                 # Mock Discord and LLM objects
│   ├── scenarios/             # Scenario-based tests
│   └── unit/                  # Unit tests
│
├── docs/                       # Documentation
│   ├── architecture.md        # This file
│   ├── commands.md            # Command reference
│   ├── features.md            # Feature explanations
│   ├── configuration.md       # Config file reference
│   └── google-sheets-setup.md # OAuth setup guide
│
├── data/                       # Runtime data (gitignored)
│   ├── chibi.db               # SQLite database
│   └── chromadb/              # ChromaDB vector store
│
├── credentials/                # OAuth credentials (gitignored)
│   ├── google_oauth_credentials.json
│   └── token.json
│
├── config.yaml                 # Bot configuration
├── course.yaml                 # Course structure
├── .env                        # Environment variables
├── main.py                     # Entry point
├── README.md                   # Project overview
└── SETUP_GUIDE.md             # Beginner setup instructions
```

---

## Core Components

### 1. Bot Initialization (`bot.py`)

**Purpose**: Main bot class that initializes all components

**Key Responsibilities:**
- Load configuration from `config.yaml` and `.env`
- Initialize database connections (SQLite + ChromaDB)
- Create all repositories, services, and agents
- Load Discord cogs (command handlers)
- Handle Discord events (messages, interactions)

**Example Flow:**
```python
# bot.py:50-100
class ChibiBot(commands.Bot):
    def __init__(self, config: Config):
        # Initialize Discord client
        super().__init__(command_prefix="!", intents=intents)

        # Store config
        self.config = config

        # Initialize components (happens in setup_hook)
        self.database = None
        self.llm_manager = None
        self.repositories = {}
        self.services = {}
```

---

### 2. Agent System (`agent/`)

**Purpose**: LangGraph-based natural language routing using ReAct pattern

**Components:**

**`graph.py`** - Main StateGraph definition
- Entry node: Receives user message
- Router node: Classifies intent using LLM
- Dispatcher node: Routes to appropriate tool
- Response node: Formats tool output for Discord

**`memory.py`** - Conversation history per user/channel
- Stores messages, tool calls, and responses
- Limited to last N messages (configurable)
- Used for follow-up questions

**`context_manager.py`** - Context compression agent
- Summarizes long conversations
- Keeps context within token limits

**`state.py`** - Agent state schema
- Defines data structure passed between nodes

**Example Flow:**
```
User: "quiz me on module 1"
  ↓
Entry Node
  ↓
Router Node (LLM classifies intent as "quiz")
  ↓
Dispatcher Node (calls quiz tool)
  ↓
Quiz Tool (generates question via QuizService)
  ↓
Response Node (formats as Discord embed)
  ↓
Bot replies with quiz question
```

---

### 3. Tools (`tools/`)

**Purpose**: ReAct pattern tools that the agent can invoke

**Design Pattern:**
- Each tool implements `Tool` base class
- Auto-discovered via `registry.py`
- Tools call services (don't contain business logic)

**Available Tools:**

**Quiz Tool** (`tools/quiz/`) - Generate quiz questions
- Uses `QuizService` to generate and evaluate
- Opens modal for user answer submission

**LLM Quiz Tool** (`tools/llm_quiz/`) - Start LLM Challenge
- Uses `LLMQuizChallengeService` for game logic

**Status Tool** (`tools/status/`) - Show user progress
- Retrieves mastery data from repositories

**Guidance Tool** (`tools/guidance/`) - Personalized study advice
- Uses `GuidanceService` to analyze progress

**Search Tool** (`tools/search/`) - Search course content
- Uses `SearchAgentService` for RAG retrieval

**Example Tool:**
```python
# tools/quiz/tool.py
class QuizTool(Tool):
    async def execute(self, **kwargs):
        # Call service layer
        question = await self.quiz_service.generate_question(...)

        # Return formatted result
        return {"question": question, "format": "embed"}
```

---

### 4. Services (`services/`)

**Purpose**: Business logic layer that orchestrates operations

**Key Services:**

**QuizService** (`quiz_service.py`)
- Generate questions using RAG + LLM
- Evaluate answers using LLM
- Calculate quality scores (1-5)
- Update mastery tracking

**LLMQuizChallengeService** (`llm_quiz_service.py`)
- Manage "Stump the LLM" game
- Student answer evaluation
- LLM answer evaluation
- Anti-cheat via SimilarityService

**RAGService** (`rag_service.py`)
- Retrieve relevant course content
- Query ChromaDB vector store
- Return top-k most similar chunks

**SearchAgentService** (`search_agent.py`)
- Centralized RAG for all tools
- Combines RAG + LLM to answer questions
- Used by assistant, quiz, and LLM quiz

**ContentIndexer** (`content_indexer.py`)
- Fetch content from `content_urls`
- Chunk documents
- Generate embeddings
- Store in ChromaDB

**ContextualChunkingService** (`contextual_chunking_service.py`)
- Enhanced chunking with LLM-generated context
- Implements Anthropic's Contextual Retrieval pattern
- Improves RAG accuracy by 20-30%

**SimilarityService** (`similarity_service.py`)
- Detect similar questions (anti-cheat)
- Store winning questions as embeddings
- Reject questions above similarity threshold

**GuidanceService** (`guidance_service.py`)
- Analyze student's quiz history
- Identify weak concepts
- Generate personalized study advice

**AttendanceSessionManager** (`attendance_session.py`)
- Manage active attendance sessions
- Generate rotating attendance codes
- Track student submissions
- Thread-safe with asyncio.Lock

**Example Service:**
```python
# services/quiz_service.py
class QuizService:
    async def generate_question(self, module_id: str, concept_id: str):
        # 1. Retrieve relevant content via RAG
        context = await self.rag_service.retrieve(concept_id)

        # 2. Generate question using LLM
        question = await self.llm_manager.generate(
            prompt=quiz_prompt,
            context=context
        )

        return question
```

---

### 5. Repositories (`database/repositories/`)

**Purpose**: Data access layer that abstracts SQLite and ChromaDB

**SQL Repositories** (SQLite via SQLAlchemy):

**UserRepository** - User profiles and registration
**QuizRepository** - Quiz attempts and responses
**MasteryRepository** - Concept mastery tracking
**LLMQuizRepository** - LLM Challenge history
**AttendanceRepository** - Attendance records

**Vector Repositories** (ChromaDB):

**RAGRepository** - Course content embeddings for RAG
**SimilarityRepository** - Question embeddings for anti-cheat

**Design Pattern:**
- Repositories return domain objects (not ORM models)
- Mappers convert between ORM and domain (`mappers.py`)
- Connection pooling via `connection.py`

**Example Repository:**
```python
# database/repositories/quiz_repository.py
class QuizRepository:
    async def save_attempt(self, attempt: QuizAttempt) -> None:
        # Convert domain object to ORM model
        orm_attempt = QuizAttemptMapper.to_orm(attempt)

        # Save to database
        async with self.db.session() as session:
            session.add(orm_attempt)
            await session.commit()
```

---

### 6. LLM Manager (`llm/`)

**Purpose**: Unified interface for multiple LLM providers with fallback

**Providers:**

**OllamaProvider** (`ollama_provider.py`) - Local inference
- Connects to Ollama server (default: `localhost:11434`)
- Free, private, fast for local models

**OpenRouterProvider** (`openrouter_provider.py`) - Cloud inference
- Unified API for multiple cloud LLMs
- Used as fallback when Ollama unavailable

**LLMManager** (`manager.py`) - Provider orchestration
- Tries primary provider first
- Falls back to secondary on failure
- Retry logic with exponential backoff
- Logging and error handling

**Example Usage:**
```python
# Primary: Ollama (local)
# Fallback: OpenRouter (cloud)
response = await llm_manager.generate(prompt, context)
# Automatically tries Ollama first, OpenRouter if it fails
```

---

### 7. Discord Cogs (`cogs/`)

**Purpose**: Discord command handlers (slash commands and prefix commands)

**Slash Commands** (recommended):
- `quiz.py` - `/quiz [module:]`
- `llm_quiz.py` - `/llm-quiz module:`
- `status.py` - `/status [module:]`
- `modules.py` - `/modules`
- `guidance.py` - `/guidance`
- `admin_slash.py` - `/admin-*` commands (6 commands)
- `attendance_slash.py` - Attendance slash commands (6 commands)
- `backup_cog.py` - `/export-progress`, `/import-progress`, `/list-exports`

**Prefix Commands** (deprecated):
- `admin.py` - `!help`, `!status`, `!show_grade`, etc.
- `attendance.py` - `!open_attendance`, `!close_attendance`, etc.

**Design Pattern:**
- Cogs are Discord event handlers
- Minimal logic (delegate to services)
- Use Discord.py's native UI (embeds, modals, user pickers)

---

## Data Flow

### Quiz Generation Flow

```
1. User runs /quiz module:m01
   ↓
2. quiz.py cog receives interaction
   ↓
3. Cog calls QuizService.generate_question()
   ↓
4. QuizService calls RAGService.retrieve(concept_id)
   ↓
5. RAGService queries RAGRepository (ChromaDB)
   ↓
6. RAGRepository returns relevant course chunks
   ↓
7. QuizService calls LLMManager.generate(prompt + context)
   ↓
8. LLMManager tries OllamaProvider → OpenRouterProvider (fallback)
   ↓
9. LLM generates question
   ↓
10. QuizService returns question to cog
    ↓
11. Cog displays modal for answer submission
    ↓
12. User submits answer
    ↓
13. QuizService.evaluate_answer() is called
    ↓
14. LLM evaluates answer (correct/incorrect + quality 1-5)
    ↓
15. QuizRepository.save_attempt() stores result
    ↓
16. MasteryRepository.update_mastery() updates progress
    ↓
17. Cog displays feedback embed to user
```

---

### Natural Language Interaction Flow

```
1. User sends message: "@ChibiBot quiz me on module 1"
   ↓
2. bot.py on_message event handler
   ↓
3. Check if message should be processed (mention or auto-response channel)
   ↓
4. Call main_agent.invoke(message)
   ↓
5. Entry Node: Extract message content
   ↓
6. Router Node: LLM classifies intent → "quiz"
   ↓
7. Dispatcher Node: Looks up "quiz" in ToolRegistry
   ↓
8. QuizTool.execute() is called
   ↓
9. [Same flow as slash command from step 3 above]
   ↓
10. Response Node: Format tool output as Discord message
    ↓
11. bot.py sends message to channel
```

---

### LLM Quiz Challenge Flow

```
1. User runs /llm-quiz module:network-science
   ↓
2. llm_quiz.py cog opens modal with two fields:
   - "Your Question"
   - "Your Answer"
   ↓
3. User submits question + answer
   ↓
4. LLMQuizChallengeService.evaluate_challenge()
   ↓
5. Check similarity to past winning questions (anti-cheat)
   - SimilarityService.is_similar(question, module_id)
   - If too similar → reject
   ↓
6. LLM (quiz model) attempts to answer the question
   - Uses RAG to access same course content as student
   ↓
7. Evaluator LLM judges both answers:
   - Student answer: correct/incorrect
   - LLM answer: correct/incorrect
   ↓
8. Determine outcome:
   - Student wins: Student correct AND LLM incorrect
   - LLM wins: LLM correct (or both wrong)
   ↓
9. If student wins:
   - Store question in SimilarityRepository
   - Increment win count in LLMQuizRepository
   ↓
10. Display result embed with both answers + evaluation
```

---

### Attendance Session Flow

```
1. Admin runs /admin-open-attendance
   ↓
2. attendance_slash.py calls AttendanceSessionManager.start_session()
   ↓
3. Session manager generates random session_id
   ↓
4. Posts code to admin channel (for projector)
5. Posts notification to attendance channel
   ↓
6. Background task starts: rotate code every 15 seconds
   - Generate new 4-character code
   - Update admin channel message
   ↓
7. Student runs /here code:ABC123
   ↓
8. Bot checks:
   - Is session active?
   - Is code current? (or previous 2 codes)
   - Is this the attendance channel?
   ↓
9. If valid: Store submission in memory
   - Latest submission overwrites previous
   ↓
10. Admin runs /admin-close-attendance
    ↓
11. Session manager stops rotation task
    ↓
12. Save all submissions to AttendanceRepository (SQLite)
    ↓
13. Update channel messages to show "closed"
    ↓
14. Return summary (session_id, total submissions)
```

---

### Google Sheets Export Flow

```
1. Admin runs /export-progress
   ↓
2. backup_cog.py calls BackupService.export_progress()
   ↓
3. BackupService reads from all repositories:
   - UserRepository → user profiles
   - QuizRepository → quiz attempts
   - MasteryRepository → concept mastery
   - LLMQuizRepository → LLM Challenge history
   - AttendanceRepository → attendance records
   ↓
4. SheetsExporter formats data as rows
   ↓
5. GoogleSheetsClient authenticates:
   - Read credentials/google_oauth_credentials.json
   - Check for existing credentials/token.json
   - If no token: Open browser for OAuth consent
   - Save refresh token to credentials/token.json
   ↓
6. Create folder in Google Drive (if doesn't exist)
   ↓
7. Create new spreadsheet with 5 sheets:
   - Users
   - Quiz Attempts
   - Concept Mastery
   - LLM Quiz Attempts
   - Attendance
   ↓
8. Write data to spreadsheet
   ↓
9. Return spreadsheet URL to user
```

---

## Key Patterns

### 1. Dependency Injection

All components receive dependencies via constructor:

```python
class QuizService:
    def __init__(
        self,
        llm_manager: LLMManager,
        rag_service: RAGService,
        quiz_repo: QuizRepository,
        mastery_repo: MasteryRepository,
    ):
        self.llm_manager = llm_manager
        self.rag_service = rag_service
        self.quiz_repo = quiz_repo
        self.mastery_repo = mastery_repo
```

**Benefits:**
- Easy to test (inject mocks)
- Clear dependencies
- No hidden globals

---

### 2. Repository Pattern

Repositories abstract data access:

```python
# Service doesn't know about SQLAlchemy or ChromaDB
quiz_attempts = await quiz_repo.get_attempts_by_user(user_id)

# Repository handles ORM details
class QuizRepository:
    async def get_attempts_by_user(self, user_id: str):
        async with self.db.session() as session:
            result = await session.execute(
                select(QuizAttemptModel).where(...)
            )
            return [QuizAttemptMapper.to_domain(row) for row in result]
```

**Benefits:**
- Services don't depend on database implementation
- Easy to swap databases
- Consistent API

---

### 3. Provider Pattern with Fallback

LLM Manager tries providers in sequence:

```python
class LLMManager:
    async def generate(self, prompt: str):
        try:
            return await self.primary_provider.generate(prompt)
        except ProviderError:
            logger.warning("Primary failed, trying fallback")
            return await self.fallback_provider.generate(prompt)
```

**Benefits:**
- Reliability (failover to cloud)
- Cost optimization (prefer free local)
- Transparent to callers

---

### 4. ReAct Pattern (Agent Tools)

Tools combine reasoning and acting:

```python
# Agent reasons about intent
intent = await classify_intent(message)  # "The user wants a quiz"

# Agent acts by invoking tool
if intent == "quiz":
    result = await quiz_tool.execute(module=parsed_module)

# Tool returns structured result
return {"question": "...", "format": "modal"}
```

**Benefits:**
- Natural language interface
- Extensible (add new tools)
- Logged reasoning for debugging

---

### 5. Contextual Retrieval

Enhanced RAG with chunk context:

```python
# Traditional RAG problem:
chunk = "Revenue grew 3%"  # Missing context!

# Contextual Retrieval solution:
context = await llm.generate(f"Summarize context for: {chunk}")
# → "This chunk is from ACME Corp Q2 2023 report."

contextualized_chunk = context + chunk
embedding = embed(contextualized_chunk)

# Store original text, search with contextualized text
rag_repo.store(text=chunk, embedding=embedding)
```

**Benefits:**
- 20-30% better retrieval accuracy
- Preserves document context
- Improves cross-reference understanding

---

## Testing Architecture

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures (in-memory DB, mock bot)
├── mocks/
│   ├── discord_mocks.py    # Mock Discord objects
│   └── llm_mocks.py        # Mock LLM responses
├── scenarios/              # End-to-end scenario tests
│   ├── test_quiz_scenarios.py
│   └── test_llm_quiz_scenarios.py
└── unit/                   # Unit tests for individual components
    ├── test_mastery.py
    └── test_similarity_service.py
```

### Testing Patterns

**Scenario-Based Testing:**
```python
async def test_scenario_student_gives_correct_answer(quiz_service, mock_llm):
    # Arrange
    mock_llm.set_response("correct")

    # Act
    result = await quiz_service.evaluate_answer(...)

    # Assert
    assert result.is_correct
    assert result.quality_score >= 3
```

**In-Memory Database:**
```python
@pytest.fixture
async def db():
    """In-memory SQLite for fast tests."""
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.init()
    yield db
    await db.close()
```

**Manual Testing:**
- Google Sheets export/import
- Discord UI interactions
- OAuth flows
- Documented in `docs/manual-testing-*.md`

---

## Related Documentation

- [Setup Guide](../SETUP_GUIDE.md) - How to install and configure
- [Configuration Guide](configuration.md) - Config file reference
- [Features Guide](features.md) - Feature explanations
- [Commands Reference](commands.md) - All commands
