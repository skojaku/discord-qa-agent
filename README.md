# Chibi - AI-Powered Discord Learning Bot

Chibi is an AI-powered Discord bot that helps students learn course material through interactive quizzes, natural conversation, and progress tracking. Built with RAG (Retrieval-Augmented Generation), LangGraph agents, and a hybrid mastery system.

---

## 🚀 Quick Setup (Recommended)

**The fastest way to set up Chibi is with AI assistance!** Use an AI coding assistant to guide you through the setup step-by-step:

### Using Claude Code (VS Code) - Recommended

1. Open this project in VS Code
2. Install [Claude Code extension](https://marketplace.visualstudio.com/items?itemName=Anthropic.claude-code)
3. Open Claude Code panel and paste:

```
I want to set up the Chibi Discord bot. Please read SETUP_GUIDE.md and guide me
through the setup process step-by-step. Ask me to confirm completion of each step
before moving to the next one. Help me troubleshoot any errors that occur.

Please help me with:
1. Creating Discord bot and getting token
2. Setting up Google Cloud OAuth credentials
3. Finding Discord channel IDs
4. Configuring environment files
5. Installing dependencies with uv
6. Running the bot for the first time
```

### Using Command Line AI (Gemini CLI, Aider, etc.)

```bash
Please read SETUP_GUIDE.md and guide me through setting up the Chibi Discord bot
step-by-step. Wait for me to confirm each step before proceeding. Help me with
Discord setup, Google Cloud OAuth, environment configuration, and first run.
```

### Using Web AI (ChatGPT, Claude.ai, Gemini, etc.)

1. Go to your AI assistant's website
2. Start a new conversation
3. Copy and paste this prompt:

```
I need help setting up a Discord bot called Chibi. I'll paste the setup guide below.
Please guide me through the setup interactively, one step at a time. After each step,
ask me to confirm completion before moving to the next one. If I encounter errors,
help me troubleshoot.

The setup includes:
- Creating a Discord bot application
- Setting up Google Cloud OAuth for Sheets export
- Configuring environment files (.env, config.yaml)
- Installing dependencies
- Running the bot

[Then paste the entire SETUP_GUIDE.md content here]

Let's start with Part 1: Discord Bot Setup. What should I do first?
```

**Why use AI?** Interactive guidance, instant troubleshooting, explanations adapted to your experience level, and help with errors as they occur.

**AI Assistant Tips:**
- **Best for beginners**: Claude Code or Claude.ai (can read files directly and execute commands)
- **Works with any AI**: ChatGPT, Gemini, Copilot - just paste SETUP_GUIDE.md
- **Pro tip**: Copy error messages directly to the AI for instant troubleshooting
- **Stay interactive**: Let the AI confirm each step before moving forward

**Prefer manual setup?** Continue reading below or see [SETUP_GUIDE.md](SETUP_GUIDE.md).

---

## Key Features

- **Natural Language Interface** - Students can @mention the bot, DM it, or chat in designated channels without commands
- **Interactive Quizzes** - AI-generated questions with contextual retrieval from course materials
- **LLM Quiz Challenge** - Students create questions to "stump the AI" and earn progress
- **Progress Tracking** - Hybrid mastery system combining LLM quality scores with accuracy ratios (Novice → Learning → Proficient → Mastered)
- **Attendance System** - Built-in attendance tracking with rotating codes and manual overrides
- **Google Sheets Backup** - Export/import all student data to Google Sheets for grading and backup
- **RAG with Contextual Retrieval** - Enhanced retrieval using Anthropic's Contextual Retrieval technique for better accuracy
- **Conversation Memory** - Per-user history enables follow-up questions and personalized guidance
- **Admin Dashboard** - Comprehensive slash commands for monitoring student progress and managing data

---

## Manual Installation

### Prerequisites

- Python 3.10+
- Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))
- Ollama (for local LLM) or OpenRouter API key (for cloud LLM)
- Optional: Google Cloud OAuth credentials for Sheets backup

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd discord-qa-agent

# Clone required dependency
git clone https://github.com/skojaku/llm-quiz.git

# Install dependencies with uv
uv pip install -r requirements.txt
# Or use: uv sync

# Configure environment
cp .env.example .env
# Edit .env with your Discord token and API keys

# Configure bot and course
# Edit config.yaml for bot settings
# Edit course.yaml for your course structure

# Run the bot
uv run python main.py
```

**Detailed Setup:** See [SETUP_GUIDE.md](SETUP_GUIDE.md) for complete instructions including Ollama setup, channel configuration, and Google Sheets integration.

---

## Documentation

- **[Setup Guide](SETUP_GUIDE.md)** - Complete setup instructions for beginners
- **[Commands Reference](docs/commands.md)** - All student and admin commands
- **[Features Guide](docs/features.md)** - Detailed feature explanations
- **[Configuration Guide](docs/configuration.md)** - Complete config.yaml and course.yaml reference
- **[Architecture Guide](docs/architecture.md)** - Code structure and data flow
- **[Google Sheets Setup](docs/google-sheets-setup.md)** - OAuth setup for backup system

---

## Student Commands

| Command | Description |
|---------|-------------|
| `/quiz [module:]` | Get a quiz question to test your knowledge |
| `/llm-quiz module:` | Challenge the AI by creating questions |
| `/status [module:]` | View your learning progress and mastery |
| `/modules` | List all available course modules |
| `/guidance` | Get personalized study recommendations |
| `/register student_id: [student_name:]` | Link Discord to student ID for attendance |
| `/here code:` | Submit attendance with current code |

**See:** [Complete Command Reference](docs/commands.md)

---

## Admin Commands

| Command | Description |
|---------|-------------|
| `/admin-help` | Show admin commands and system stats |
| `/admin-status student: [module:]` | View a student's progress |
| `/admin-grade [module:]` | Export grades to CSV |
| `/admin-open-attendance` | Start attendance session with rotating codes |
| `/admin-close-attendance` | End session and save records |
| `/export-progress` | Export all data to Google Sheets |
| `/import-progress url: [mode:]` | Import data from Google Sheets |

**See:** [Complete Command Reference](docs/commands.md)

> **Note:** Legacy prefix commands (`!help`, `!status`, etc.) are deprecated. Please use slash commands.

---

## Configuration Files

### config.yaml

Main bot configuration for LLM providers, mastery thresholds, and features:

```yaml
llm:
  primary:
    provider: "ollama"
    model: "ministral-3:14b-cloud"
  fallback:
    provider: "openrouter"
    model: "openai/gpt-oss-120b"

mastery:
  min_attempts_for_mastery: 3
  quality_threshold: 3.5
  correct_ratio_threshold: 0.7

contextual_retrieval:
  enabled: true
  max_context_tokens: 100
```

**See:** [Configuration Guide](docs/configuration.md) for all options.

---

### course.yaml

Defines your course structure, modules, and concepts:

```yaml
course:
  name: "My Course"
  code: "CS101"

modules:
  - id: "m01"
    name: "Introduction"
    content_urls:
      - "https://raw.githubusercontent.com/..."
    concepts:
      - id: "basic-concept"
        name: "Basic Concept"
        description: "What this concept covers"
        quiz_focus: "Key aspects to test"
```

**Generate course.yaml with AI:** Use the prompt in [`prompts/generate_course_yaml.md`](prompts/generate_course_yaml.md)

**See:** [Configuration Guide](docs/configuration.md) for complete field reference.

---

## Environment Variables

Create a `.env` file from `.env.example`:

```bash
# Required
DISCORD_TOKEN=your_discord_bot_token

# Optional
OPENROUTER_API_KEY=your_openrouter_key
ADMIN_CHANNEL_ID=123456789
ATTENDANCE_CHANNEL_ID=987654321
NL_ROUTING_CHANNELS=123456789,987654321
```

**Getting Channel IDs:**
1. Enable Developer Mode: Discord Settings → Advanced → Developer Mode
2. Right-click channel → Copy Channel ID

**See:** [Configuration Guide](docs/configuration.md#environment-variables-env)

---

## How It Works

### Quiz System

1. Student runs `/quiz module:m01`
2. Bot retrieves relevant course content using RAG
3. LLM generates a question based on the concept
4. Student submits answer via modal
5. LLM evaluates answer for correctness and quality (1-5)
6. Progress tracked toward mastery levels

**See:** [Features Guide - Quiz System](docs/features.md#quiz-system)

---

### LLM Quiz Challenge

Students create questions to challenge the AI:

1. Student submits question + their answer
2. Quiz LLM attempts to answer (with RAG context)
3. Evaluator LLM judges both answers
4. Student wins if they're correct AND the LLM is wrong
5. Wins tracked toward module completion (default: 3/module)
6. Anti-cheat: Similarity detection prevents reusing questions

**See:** [Features Guide - LLM Quiz Challenge](docs/features.md#llm-quiz-challenge)

---

### Mastery System

Hybrid evaluation using LLM quality + accuracy ratio:

| Level | Icon | Requirements |
|-------|------|--------------|
| **Novice** | ⬜ | Initial state |
| **Learning** | 🟨 | At least 1 correct attempt |
| **Proficient** | 🟦 | ≥70% correct + avg quality ≥3.5 |
| **Mastered** | 🟩 | Proficient + 3+ correct attempts |

**See:** [Features Guide - Mastery System](docs/features.md#mastery-system)

---

## Architecture Overview

Chibi uses a layered architecture with LangGraph for natural language routing:

```
Discord Events → Agent Graph → Tools → Services → Repositories → Database
```

**Key Components:**

- **Agent System** (`agent/`) - LangGraph StateGraph for intent classification and tool dispatch
- **Tools** (`tools/`) - ReAct pattern tools (quiz, assistant, status, guidance)
- **Services** (`services/`) - Business logic (quiz generation, RAG, mastery calculation)
- **Repositories** (`database/repositories/`) - Data access layer (SQLite + ChromaDB)

**See:** [Architecture Guide](docs/architecture.md) for complete details.

---

## Testing

Run the test suite using pytest:

```bash
# Run all tests
uv run pytest tests/

# Run with coverage
uv run pytest tests/ --cov=chibi --cov-report=term-missing

# Run specific test file
uv run pytest tests/scenarios/test_quiz_scenarios.py -v
```

**Test Coverage:**
- Quiz generation and evaluation
- Mastery progression
- LLM Quiz Challenge
- Admin commands
- Agent routing
- Status display

---

## Google Sheets Backup

Export and import all student data to Google Sheets for backup or grading.

### Quick Setup

1. Enable Google Sheets API and Google Drive API in [Google Cloud Console](https://console.cloud.google.com/)
2. Create OAuth 2.0 credentials (Desktop app)
3. Download credentials and save as `credentials/google_oauth_credentials.json`
4. Run `/export-progress` in Discord (browser opens for authorization)
5. Future exports work automatically

### Commands

- `/export-progress` - Create new spreadsheet with all data
- `/import-progress url: [mode:]` - Import from spreadsheet
- `/list-exports [limit:]` - List recent exports

**See:** [Google Sheets Setup Guide](docs/google-sheets-setup.md) for detailed instructions and troubleshooting.

---

## Discord Bot Permissions

When inviting the bot to your server, grant these permissions:

- Send Messages
- Use Slash Commands
- Embed Links
- Read Message History
- Attach Files

**Invite URL:** Generate from Discord Developer Portal → OAuth2 → URL Generator

---

## Project Structure

```
discord-qa-agent/
├── main.py                    # Entry point
├── config.yaml                # Bot configuration
├── course.yaml                # Course structure
├── .env                       # Environment variables
├── SETUP_GUIDE.md             # Beginner-friendly setup
├── README.md                  # This file
├── chibi/                     # Main package
│   ├── bot.py                 # ChibiBot class
│   ├── agent/                 # LangGraph agent system
│   ├── cogs/                  # Discord commands
│   ├── tools/                 # Agent tools
│   ├── services/              # Business logic
│   ├── database/              # Data layer
│   ├── llm/                   # LLM providers
│   └── backup/                # Google Sheets export
├── docs/                      # Documentation
│   ├── commands.md            # Command reference
│   ├── features.md            # Feature guide
│   ├── configuration.md       # Config reference
│   ├── architecture.md        # Code structure
│   └── google-sheets-setup.md # Backup setup
├── tests/                     # Test suite
└── data/                      # Runtime data (gitignored)
    ├── chibi.db               # SQLite database
    └── chromadb/              # Vector store
```

**See:** [Architecture Guide](docs/architecture.md) for detailed component descriptions.

---

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

---

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

## Support

- **Documentation:** Start with [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **Issues:** Report bugs or request features via GitHub Issues
- **Questions:** Check [docs/](docs/) folder for detailed guides

---

## Credits

Built with:
- [Discord.py](https://github.com/Rapptz/discord.py) - Discord API wrapper
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent orchestration
- [ChromaDB](https://www.trychroma.com/) - Vector database for RAG
- [Ollama](https://ollama.ai/) - Local LLM runtime
- [OpenRouter](https://openrouter.ai/) - Cloud LLM API

Implements [Anthropic's Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) technique for enhanced RAG accuracy.
