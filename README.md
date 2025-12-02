# Chibi - Discord Quiz Bot for Lecture Content

Chibi is an AI-powered Discord bot that helps students learn course material through quizzes. It uses Ollama (local) or OpenRouter (cloud) for LLM capabilities and tracks student progress with a mastery system.

## Features

### Student Commands
- **`/quiz [module]`** - Get quiz questions to test your knowledge
- **`/status [module]`** - Track your learning progress and concept mastery

### Admin Commands
Admin commands are hidden from students and only visible to server administrators in the configured admin channel.

- **`/_show_grade [module]`** - Generate CSV report of student grades
- **`/_status <student> [module]`** - View a specific student's learning progress

### Quiz Format
- Free Form (open-ended questions with AI-evaluated responses)

### Mastery System
- Tracks quiz performance per concept
- Hybrid evaluation: LLM quality scores + accuracy ratio
- Four levels: Novice → Learning → Proficient → Mastered

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
│   ├── cogs/              # Discord commands
│   │   ├── quiz.py        # /quiz command
│   │   ├── status.py      # /status command
│   │   ├── admin.py       # /show_grade, /_status commands
│   │   └── utils.py       # Common utilities
│   ├── llm/               # LLM integration
│   │   ├── base.py        # Provider interface
│   │   ├── ollama_provider.py
│   │   ├── openrouter_provider.py
│   │   └── manager.py     # Fallback logic
│   ├── content/           # Course content
│   │   ├── course.py      # Data models
│   │   └── loader.py      # URL fetcher
│   ├── database/          # SQLite storage
│   │   ├── connection.py
│   │   ├── models.py
│   │   ├── mappers.py     # Row-to-model mappers
│   │   └── repository.py
│   ├── learning/          # Learning profile
│   │   └── mastery.py
│   └── prompts/
│       └── templates.py   # Chibi persona
└── data/
    └── chibi.db           # SQLite database
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
