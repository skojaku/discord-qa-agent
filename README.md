# Chibi - Discord Quiz Bot for Lecture Content

Chibi is an AI-powered Discord bot that helps students learn course material through quizzes and natural conversation. It uses Ollama (local) or OpenRouter (cloud) for LLM capabilities, RAG (Retrieval-Augmented Generation) for context-aware responses, and tracks student progress with a mastery system.

## Features

### Natural Language Interface
Students can interact with Chibi naturally by:
- **@mentioning** the bot in any channel
- **Direct messaging** the bot
- Asking questions like "quiz me on module 1" or "how does network centrality work?"

The bot uses a ReAct (Reasoning + Acting) framework to intelligently decide when to search course content.

### Student Commands
- **`/quiz [module]`** - Get quiz questions to test your knowledge
- **`/llm-quiz <module>`** - Challenge the AI! Create questions to stump the LLM
- **`/status [module]`** - Track your learning progress and concept mastery
- **`/modules`** - List all available course modules with descriptions

### Admin Commands
Admin commands use prefix commands (`!command`) instead of slash commands to keep them completely hidden from students. They only work in the configured admin channel.

- **`!help`** (or `!admin`) - Show admin help with available commands, modules, and students
- **`!modules`** - List all available modules
- **`!students`** - List all registered students
- **`!show_grade [module]`** - Generate CSV report of student grades
- **`!status <student> [module]`** - View a specific student's learning progress (supports @mentions)
- **`!clear_similarity [module]`** - Clear LLM Quiz similarity database (for duplicate detection reset)

### Quiz Format
- Free Form (open-ended questions with AI-evaluated responses)

### Mastery System
- Tracks quiz performance per concept
- Hybrid evaluation: LLM quality scores + accuracy ratio
- Four levels: Novice → Learning → Proficient → Mastered

### LLM Quiz Challenge
Students can create their own quiz questions to challenge the AI:
- Student submits a question + their correct answer via modal dialog
- A quiz model attempts to answer the question (contextualized with RAG-retrieved content)
- An evaluator model judges both answers for factual correctness
- Student wins only if their answer is correct AND the LLM's answer is incorrect
- Progress is tracked per module with a configurable target (default: 3 wins per module)
- **Anti-cheat**: Embedding-based similarity detection prevents reusing questions (only winning questions are recorded)

### RAG System
Chibi uses ChromaDB for vector storage and retrieval:
- Course content is automatically indexed for semantic search
- Quiz questions are generated with relevant context
- The assistant searches course materials when answering questions
- LLM Quiz uses RAG to give the AI fair access to course content

### Conversation Memory
- Tracks conversation history per user per channel
- Quiz results, feedback, and user answers are logged
- Enables follow-up questions like "what was my answer?" or "how can I improve?"

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and add your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```
DISCORD_TOKEN=your_discord_bot_token
OPENROUTER_API_KEY=your_openrouter_api_key  # Optional, for fallback
ADMIN_CHANNEL_ID=your_admin_channel_id      # Optional, restricts admin commands
```

### 3. Configure the Bot

Edit `config.yaml` for LLM settings and `course.yaml` for your course content.

### 4. Set Up Ollama (Optional)

If using local LLM:
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.2
```

### 5. Run the Bot

```bash
python main.py
```

## Configuration

### config.yaml

```yaml
discord:
  sync_commands_on_startup: true

llm:
  primary:
    provider: "ollama"
    base_url: "http://localhost:11434"
    model: "llama3.2"
  fallback:
    provider: "openrouter"
    model: "meta-llama/llama-3.2-3b-instruct"

mastery:
  min_attempts_for_mastery: 3
  quality_threshold: 3.5
  correct_ratio_threshold: 0.7

# LLM Quiz Challenge settings
llm_quiz:
  target_wins_per_module: 3  # Wins needed to complete a module
  quiz_model: "openrouter/google/gemma-3-12b-it"  # Model that tries to answer
  evaluator_model: "openrouter/google/gemini-2.5-flash-lite"  # Model that judges
  base_url: "https://openrouter.ai/api/v1"

# RAG settings
rag:
  enabled: true
  chromadb_path: "data/chromadb"
  chunk_size: 500
  chunk_overlap: 50
  top_k: 5

# Similarity detection for LLM Quiz anti-cheat
similarity:
  enabled: true
  chromadb_path: "data/chromadb"
  similarity_threshold: 0.85  # Questions above this similarity are rejected
  embedding_model: "ollama"   # or "openrouter"
```

#### Getting the Admin Channel ID

1. Enable Developer Mode in Discord: **Settings** → **Advanced** → **Developer Mode**
2. Right-click your admin channel and select **Copy Channel ID**
3. Paste the ID into `.env` as `ADMIN_CHANNEL_ID`

### course.yaml

Define your course modules and concepts:

```yaml
course:
  name: "My Course"
  code: "CS101"

modules:
  - id: "m01"
    name: "Introduction"
    content_url: "https://example.com/module1.txt"
    concepts:
      - id: "concept-1"
        name: "Basic Concept"
        description: "Description of the concept"
        quiz_focus: "What to focus on for quizzes"
```

## Project Structure

```
discord-qa-agent/
├── main.py                # Entry point
├── config.yaml            # Bot configuration
├── course.yaml            # Course content
├── chibi/
│   ├── bot.py             # Discord bot class
│   ├── config.py          # Config loader
│   ├── constants.py       # Constants and error messages
│   ├── cogs/              # Discord slash commands
│   │   ├── quiz.py        # /quiz command
│   │   ├── llm_quiz.py    # /llm-quiz command
│   │   ├── status.py      # /status command
│   │   ├── modules.py     # /modules command
│   │   ├── admin.py       # Admin prefix commands (!help, !status, etc.)
│   │   └── utils.py       # Common utilities
│   ├── agent/             # LangGraph-based agent system
│   │   ├── graph.py       # Main agent graph
│   │   ├── state.py       # Agent state definitions
│   │   ├── memory.py      # Conversation memory
│   │   ├── context_manager.py  # RAG context retrieval
│   │   └── nodes/         # Agent nodes
│   │       ├── router.py      # Intent classification
│   │       └── dispatcher.py  # Tool dispatch
│   ├── tools/             # Tool implementations
│   │   ├── base.py        # Base tool class
│   │   ├── registry.py    # Tool registry
│   │   ├── assistant/     # General Q&A with ReAct
│   │   ├── quiz/          # Quiz generation tool
│   │   ├── llm_quiz/      # LLM Quiz Challenge tool
│   │   └── status/        # Status display tool
│   ├── ui/                # UI utilities
│   │   ├── formatters.py  # Progress bars, mastery display
│   │   └── embeds/        # Discord embed builders
│   ├── llm/               # LLM integration
│   │   ├── base.py        # Provider interface
│   │   ├── ollama_provider.py
│   │   ├── openrouter_provider.py
│   │   └── manager.py     # Fallback logic
│   ├── content/           # Course content
│   │   ├── course.py      # Data models
│   │   └── loader.py      # URL fetcher
│   ├── database/          # SQLite + ChromaDB storage
│   │   ├── connection.py
│   │   ├── models.py
│   │   └── repositories/
│   │       ├── user_repository.py
│   │       ├── quiz_repository.py
│   │       ├── mastery_repository.py
│   │       ├── llm_quiz_repository.py
│   │       ├── rag_repository.py       # ChromaDB for RAG
│   │       └── similarity_repository.py # ChromaDB for anti-cheat
│   ├── services/          # Business logic
│   │   ├── quiz_service.py
│   │   ├── llm_quiz_service.py
│   │   ├── rag_service.py          # RAG retrieval
│   │   ├── similarity_service.py   # Question similarity detection
│   │   ├── embedding_service.py    # Embedding generation
│   │   └── grade_service.py
│   ├── learning/
│   │   └── mastery.py
│   └── prompts/
│       └── templates.py
└── data/
    ├── chibi.db           # SQLite database
    └── chromadb/          # ChromaDB vector storage
```

## Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section and create a bot
4. Copy the bot token to your `.env` file
5. Go to "OAuth2" → "URL Generator"
6. Select scopes: `bot`, `applications.commands`
7. Select permissions: `Send Messages`, `Use Slash Commands`, `Embed Links`
8. Use the generated URL to invite the bot to your server

## License

MIT
