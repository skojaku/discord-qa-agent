# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Run Commands

```bash
# Run the bot
python main.py

# Run all tests
uv run pytest tests/

# Run a specific test file
uv run pytest tests/scenarios/test_quiz_scenarios.py -v

# Run a specific test class
uv run pytest tests/scenarios/test_quiz_scenarios.py::TestQuizEvaluationScenarios -v

# Run a specific test
uv run pytest tests/scenarios/test_quiz_scenarios.py::TestQuizEvaluationScenarios::test_scenario_student_gives_correct_answer -v

# Run with coverage
uv run pytest tests/ --cov=chibi --cov-report=term-missing
```

## Architecture Overview

Chibi is a Discord quiz bot that uses LangGraph for natural language routing, ChromaDB for RAG, and SQLite for user data. The architecture follows a layered pattern:

### Core Flow
1. **Discord Events** (`bot.py`) → User messages/interactions are received
2. **Agent Graph** (`agent/graph.py`) → LangGraph StateGraph routes natural language messages through: entry → router → dispatcher → response
3. **Tools** (`tools/`) → Intent is dispatched to the appropriate tool (quiz, assistant, status, etc.)
4. **Services** (`services/`) → Business logic layer that tools call
5. **Repositories** (`database/repositories/`) → Data access layer (SQLite + ChromaDB)

### Key Components

**Bot & Agent System:**
- `chibi/bot.py`: Main ChibiBot class - initializes all services, repositories, and handles Discord events
- `chibi/agent/graph.py`: LangGraph StateGraph with nodes for intent classification and tool dispatch
- `chibi/agent/nodes/router.py`: Intent classification node using LLM
- `chibi/agent/nodes/dispatcher.py`: Routes to appropriate tool based on detected intent
- `chibi/agent/memory.py`: Per-user conversation history

**Tools** (in `chibi/tools/`):
- Each tool has a `tool.py` implementing the base Tool interface
- Tools are auto-discovered and registered via `registry.py`
- Main tools: quiz, assistant, llm_quiz, status, guidance

**Services** (in `chibi/services/`):
- `QuizService`: Quiz generation and answer evaluation
- `RAGService`: Context retrieval from ChromaDB
- `SearchAgentService`: Centralized RAG operations for all tools
- `LLMQuizChallengeService`: "Stump the LLM" game logic
- `SimilarityService`: Question deduplication (anti-cheat)

**Repositories** (in `chibi/database/repositories/`):
- SQLite repos: `UserRepository`, `QuizRepository`, `MasteryRepository`, `LLMQuizRepository`
- ChromaDB repos: `RAGRepository`, `SimilarityRepository`

**Cogs** (in `chibi/cogs/`):
- Discord slash commands: `/quiz`, `/status`, `/llm-quiz`, `/modules`, `/guidance`
- Admin prefix commands: `!help`, `!status`, `!show_grade`, `!clear_similarity`

### LLM Integration
- `chibi/llm/manager.py`: LLMManager with primary (Ollama) and fallback (OpenRouter) providers
- `chibi/llm/ollama_provider.py`: Local LLM via Ollama
- `chibi/llm/openrouter_provider.py`: Cloud LLM via OpenRouter API

### Configuration
- `config.yaml`: Bot and LLM settings
- `course.yaml`: Course modules, concepts, and content URLs
- `.env`: Discord token, API keys

## Testing Approach

Tests use scenario-based patterns with extensive mocking:
- `tests/mocks/discord_mocks.py`: Mock Discord objects (User, Channel, Interaction)
- `tests/mocks/llm_mocks.py`: Mock LLM providers with configurable responses
- `tests/conftest.py`: Shared fixtures including in-memory SQLite database
- All tests are async using pytest-asyncio with `asyncio_mode = "auto"`
