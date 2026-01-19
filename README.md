# Chibi - AI-Powered Discord Learning Bot

AI-powered Discord bot for interactive learning through quizzes, natural conversation, and progress tracking. Built with RAG, LangGraph agents, and hybrid mastery system.

---

## 🚀 Quick Setup with AI Assistant (Recommended)

**Easiest way:** Use an AI coding assistant to guide you through setup interactively.

**Paste this into Claude Code, ChatGPT, Gemini, or any AI assistant:**

```
I want to set up the Chibi Discord bot. Please read SETUP_GUIDE.md and guide me
through the setup step-by-step. Ask me to confirm completion of each step before
moving to the next one. Help me troubleshoot any errors.
```

**Why?** Interactive guidance, instant troubleshooting, and step-by-step confirmation.

**Manual setup:** See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed instructions.

---

## Key Features

- **Interactive Quizzes** - AI-generated questions with RAG from course materials
- **LLM Quiz Challenge** - Students create questions to "stump the AI"
- **Progress Tracking** - Hybrid mastery: Novice → Learning → Proficient → Mastered
- **Natural Language** - @mention, DM, or chat in designated channels
- **Attendance System** - Rotating codes with manual overrides
- **Google Sheets Backup** - Export/import all student data
- **RAG with Contextual Retrieval** - Enhanced accuracy using Anthropic's technique
- **Admin Dashboard** - Monitor progress and manage data

**Details:** [Features Guide](docs/features.md)

---

## Quick Install

```bash
# Clone repository
git clone <your-repo-url>
cd discord-qa-agent

# Clone required dependency
git clone https://github.com/skojaku/llm-quiz.git

# Install dependencies
uv pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with Discord token and channel IDs

# Run
uv run python main.py
```

**Prerequisites:** Python 3.10+, Discord bot token, Ollama or OpenRouter API key

**Full setup:** [SETUP_GUIDE.md](SETUP_GUIDE.md) | [Configuration Guide](docs/configuration.md)

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Setup Guide](SETUP_GUIDE.md) | Step-by-step setup for beginners |
| [Commands](docs/commands.md) | All student and admin commands |
| [Features](docs/features.md) | Detailed feature explanations |
| [Configuration](docs/configuration.md) | config.yaml and course.yaml reference |
| [Architecture](docs/architecture.md) | Code structure and data flow |
| [Google Sheets](docs/google-sheets-setup.md) | OAuth setup for backup system |

---

## Commands

### Student Commands

- `/quiz [module:]` - Get quiz question
- `/llm-quiz module:` - Challenge the AI
- `/status [module:]` - View progress
- `/modules` - List all modules
- `/guidance` - Study recommendations
- `/register student_id:` - Link to student ID
- `/here code:` - Submit attendance

### Admin Commands

- `/admin-help` - Admin commands help
- `/admin-status student:` - View student progress
- `/admin-grade [module:]` - Export grades CSV
- `/admin-open-attendance` - Start attendance session
- `/admin-close-attendance` - End session
- `/export-progress` - Export to Google Sheets
- `/import-progress url:` - Import from Sheets

**Full reference:** [Commands Guide](docs/commands.md)

---

## Configuration

### config.yaml

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
```

### course.yaml

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
        description: "What this covers"
        quiz_focus: "Key aspects to test"
```

**Generate with AI:** Use [`prompts/generate_course_yaml.md`](prompts/generate_course_yaml.md)

**Complete reference:** [Configuration Guide](docs/configuration.md)

---

## Environment Variables

```bash
# Required
DISCORD_TOKEN=your_discord_bot_token

# Optional
OPENROUTER_API_KEY=your_key
ADMIN_CHANNEL_ID=123456789
ATTENDANCE_CHANNEL_ID=987654321
NL_ROUTING_CHANNELS=channel1,channel2
```

**Get Channel IDs:** Enable Developer Mode in Discord Settings → Advanced, then right-click channel → Copy Channel ID

---

## Architecture

```
Discord Events → Agent Graph → Tools → Services → Repositories → Database
```

**Components:**
- **Agent** (`agent/`) - LangGraph StateGraph for NL routing
- **Tools** (`tools/`) - ReAct pattern (quiz, assistant, status)
- **Services** (`services/`) - Business logic
- **Repositories** (`database/`) - SQLite + ChromaDB

**Details:** [Architecture Guide](docs/architecture.md)

---

## Testing

```bash
# Run all tests
uv run pytest tests/

# With coverage
uv run pytest tests/ --cov=chibi --cov-report=term-missing

# Specific test
uv run pytest tests/scenarios/test_quiz_scenarios.py -v
```

---

## Google Sheets Backup

Export/import student data for backup and grading.

**Quick Setup:**
1. Enable Google Sheets API + Drive API in [Google Cloud Console](https://console.cloud.google.com/)
2. Create OAuth 2.0 credentials (Desktop app)
3. Save as `credentials/google_oauth_credentials.json`
4. Run `/export-progress` (browser opens for auth)

**Commands:** `/export-progress`, `/import-progress url:`, `/list-exports`

**Full guide:** [Google Sheets Setup](docs/google-sheets-setup.md)

---

## Project Structure

```
discord-qa-agent/
├── main.py                # Entry point
├── config.yaml            # Bot config
├── course.yaml            # Course structure
├── .env                   # Environment variables
├── SETUP_GUIDE.md         # Setup instructions
├── chibi/                 # Main package
│   ├── agent/            # LangGraph agents
│   ├── cogs/             # Discord commands
│   ├── tools/            # Agent tools
│   ├── services/         # Business logic
│   ├── database/         # Data layer
│   ├── llm/              # LLM providers
│   └── backup/           # Google Sheets
├── docs/                  # Documentation
└── tests/                 # Test suite
```

---

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new features
4. Ensure tests pass
5. Submit pull request

---

## License

MIT License - See [LICENSE](LICENSE) file

---

## Support

- **Setup help:** [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **Documentation:** [docs/](docs/)
- **Issues:** GitHub Issues

---

## Credits

Built with [Discord.py](https://github.com/Rapptz/discord.py), [LangGraph](https://github.com/langchain-ai/langgraph), [ChromaDB](https://www.trychroma.com/), [Ollama](https://ollama.ai/), [OpenRouter](https://openrouter.ai/)

Implements [Anthropic's Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
