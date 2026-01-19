# Configuration Guide

Complete reference for configuring Chibi Bot through `config.yaml`, `course.yaml`, and `.env` files.

## Table of Contents

- [config.yaml Reference](#configyaml-reference)
- [course.yaml Reference](#courseyaml-reference)
- [Environment Variables (.env)](#environment-variables-env)
- [Best Practices](#best-practices)

---

## config.yaml Reference

Main bot configuration file with LLM settings, mastery thresholds, and feature toggles.

### Discord Settings

```yaml
discord:
  sync_commands_on_startup: true
```

**sync_commands_on_startup** - Whether to sync slash commands with Discord on bot startup
- **Type**: boolean
- **Default**: `true`
- **When to disable**: During development to avoid rate limits
- **Note**: Set to `false` if commands already synced, speeds up startup

---

### LLM Configuration

Controls primary and fallback LLM providers for all bot operations.

```yaml
llm:
  # Primary provider (Ollama - local)
  primary:
    provider: "ollama"
    base_url: "http://localhost:11434"
    model: "ministral-3:14b-cloud"
    timeout: 60
    max_retries: 2

  # Fallback provider (OpenRouter - cloud)
  fallback:
    provider: "openrouter"
    base_url: "https://openrouter.ai/api/v1"
    model: "openai/gpt-oss-120b"
    timeout: 90
    max_retries: 1

  # Shared LLM settings
  max_tokens: 1024
  temperature: 0.7
```

**Primary Provider:**
- **provider**: `"ollama"` or `"openrouter"`
- **base_url**: API endpoint URL
  - Ollama: `http://localhost:11434` (default)
  - OpenRouter: `https://openrouter.ai/api/v1`
- **model**: Model identifier
  - Ollama: Model name from `ollama list` (e.g., `"ministral-3:14b-cloud"`, `"llama3.2"`)
  - OpenRouter: Full model path (e.g., `"openai/gpt-oss-120b"`, `"meta-llama/llama-3-8b-instruct"`)
- **timeout**: Max seconds to wait for response (default: 60)
- **max_retries**: Number of retry attempts on failure (default: 2)

**Fallback Provider:**
- Used when primary provider fails or is unavailable
- Same configuration options as primary
- Typically uses cloud provider for reliability

**Shared Settings:**
- **max_tokens**: Maximum tokens to generate per response (default: 1024)
- **temperature**: Randomness in generation, 0-1 (default: 0.7)
  - Lower (0.2-0.4): More deterministic, factual
  - Higher (0.7-0.9): More creative, varied

**Recommended Models:**
- **Local (Ollama)**: `ministral-3:14b-cloud`, `llama3.2`, `glm-4.6:cloud`
- **Cloud (OpenRouter)**: `openai/gpt-oss-120b`, `meta-llama/llama-3-8b-instruct`

---

### Persona Settings

```yaml
persona:
  name: "Chibi"
  description: "Your friendly AI tutor for Applied Soft Computing"
```

**name** - Bot's display name in responses
**description** - Bot's role description (used in prompts)

---

### Mastery System

Controls how student progress is calculated using hybrid LLM quality + accuracy.

```yaml
mastery:
  min_attempts_for_mastery: 3
  quality_threshold: 3.5
  correct_ratio_threshold: 0.7
```

**min_attempts_for_mastery** - Minimum correct attempts needed for "Mastered" level
- **Type**: integer
- **Default**: 3
- **Range**: 1-10 recommended
- **Higher values**: Require more evidence of mastery

**quality_threshold** - Average LLM quality score needed for "Proficient" or higher
- **Type**: float
- **Default**: 3.5 (out of 5)
- **Range**: 1.0-5.0
- **Scoring**: LLM assigns 1-5 based on answer depth and correctness

**correct_ratio_threshold** - Percentage of correct attempts for "Proficient" or higher
- **Type**: float
- **Default**: 0.7 (70%)
- **Range**: 0.0-1.0
- **Example**: 0.7 means 7 out of 10 attempts must be correct

**Mastery Levels:**
- **Novice** ⬜ - Initial state
- **Learning** 🟨 - At least 1 correct attempt
- **Proficient** 🟦 - Meets quality AND correct ratio thresholds
- **Mastered** 🟩 - Proficient + min_attempts_for_mastery

---

### Database Settings

```yaml
database:
  path: "data/chibi.db"
```

**path** - SQLite database file path
- **Default**: `"data/chibi.db"`
- **Relative to**: Project root
- **Note**: Directory must exist (created automatically on first run)

---

### Backup Settings

Google Sheets export/import configuration (OAuth-based).

```yaml
backup:
  credentials_file: "credentials/google_oauth_credentials.json"
  token_file: "credentials/token.json"
  folder_name: "Chibi Bot Exports"
  scopes:
    - "https://www.googleapis.com/auth/spreadsheets"
    - "https://www.googleapis.com/auth/drive.file"
```

**credentials_file** - OAuth 2.0 credentials JSON from Google Cloud Console
- **Path**: Relative to project root
- **Required**: For `/export-progress` and `/import-progress` commands
- **Setup**: See [Google Sheets Setup Guide](google-sheets-setup.md)

**token_file** - OAuth refresh token (auto-generated)
- **Path**: Relative to project root
- **Auto-created**: After first OAuth authorization
- **Keep secure**: Contains access credentials

**folder_name** - Google Drive folder name for exports
- **Default**: `"Chibi Bot Exports"`
- **Auto-created**: Folder created if doesn't exist
- **Nested folders**: Use `/` separator (e.g., `"Exports/Fall 2025"`)
- **Empty string**: Save to Drive root instead

**scopes** - OAuth permission scopes
- **spreadsheets**: Create and read spreadsheets
- **drive.file**: Access only bot-created files
- **Do not modify**: Unless you know what you're doing

---

### LLM Quiz Challenge

Settings for the "Stump the LLM" game where students create questions.

```yaml
llm_quiz:
  target_wins_per_module: 3
  quiz_model: "openrouter/meta-llama/llama-3-8b-instruct"
  quiz_base_url: "https://openrouter.ai/api/v1"
  evaluator_model: "ollama/glm-4.6:cloud"
  evaluator_base_url: "http://localhost:11434"
```

**target_wins_per_module** - Required wins per module for completion
- **Type**: integer
- **Default**: 3
- **Range**: 1-10 recommended
- **Usage**: Shown in `/status module:X` as "LLM Quiz: 2/3 wins"

**quiz_model** - The LLM that students try to stump
- **Format**: `"provider/model"` (e.g., `"openrouter/meta-llama/llama-3-8b-instruct"`)
- **Strategy**: Use a weaker model than evaluator for fairness

**quiz_base_url** - API endpoint for quiz model

**evaluator_model** - The judge that evaluates both answers
- **Format**: `"provider/model"` (e.g., `"ollama/glm-4.6:cloud"`)
- **Strategy**: Use a strong, reliable model for consistent grading

**evaluator_base_url** - API endpoint for evaluator model

**Recommended Combinations:**
- **Quiz**: Smaller cloud models (8B-20B parameters)
- **Evaluator**: Larger local models or premium cloud models

---

### Similarity Detection

Anti-cheat system for LLM Quiz using embedding similarity.

```yaml
similarity:
  enabled: true
  similarity_threshold: 0.85
  top_k: 5
  embedding_model: "nomic-embed-text"
  ollama_base_url: "http://localhost:11434"
  fallback_enabled: true
  fallback_model: "openrouter/qwen/qwen3-embedding-8b"
  fallback_base_url: "https://openrouter.ai/api/v1"
  chromadb_path: "data/chromadb"
```

**enabled** - Turn similarity checking on/off
- **Type**: boolean
- **Default**: `true`
- **When to disable**: Testing, debugging, or if false positives occur

**similarity_threshold** - Cosine similarity above which questions are rejected
- **Type**: float (0-1)
- **Default**: 0.85
- **Range**: 0.8-0.95 recommended
- **Lower values**: Stricter (more rejections)
- **Higher values**: More lenient (fewer rejections)

**top_k** - Number of similar questions to retrieve for comparison
- **Type**: integer
- **Default**: 5
- **Range**: 3-10 recommended

**embedding_model** - Primary embedding model (Ollama)
- **Default**: `"nomic-embed-text"`
- **Alternatives**: Any Ollama embedding model

**ollama_base_url** - Ollama API endpoint

**fallback_enabled** - Use cloud embeddings if Ollama unavailable
- **Type**: boolean
- **Default**: `true`

**fallback_model** - Cloud embedding model (OpenRouter)
- **Default**: `"openrouter/qwen/qwen3-embedding-8b"`

**fallback_base_url** - OpenRouter API endpoint

**chromadb_path** - ChromaDB vector database path
- **Default**: `"data/chromadb"`
- **Relative to**: Project root

---

### Agent Settings

LangGraph-based natural language routing configuration.

```yaml
agent:
  enabled: true
  intent_confidence_threshold: 0.7
  max_conversation_history: 20
```

**enabled** - Enable natural language interface
- **Type**: boolean
- **Default**: `true`
- **When to disable**: Force slash commands only

**intent_confidence_threshold** - Minimum confidence for intent classification
- **Type**: float (0-1)
- **Default**: 0.7
- **Lower values**: More lenient (may misclassify)
- **Higher values**: Stricter (may fall back to default response)

**max_conversation_history** - Messages to retain per user/channel
- **Type**: integer
- **Default**: 20
- **Range**: 10-50 recommended
- **Note**: Affects memory for follow-up questions

**Auto-Response Channels:**
- Configured via `NL_ROUTING_CHANNELS` in `.env`
- In these channels, bot responds without @mention

---

### Contextual Retrieval

Enhanced RAG with LLM-generated context summaries for each chunk.

```yaml
contextual_retrieval:
  enabled: true
  max_context_tokens: 100
  batch_size: 5
  batch_delay_seconds: 0.5
  temperature: 0.3
  model: "openrouter/openai/gpt-oss-20b"
  base_url: "https://openrouter.ai/api/v1"
```

**enabled** - Use contextual retrieval for better RAG accuracy
- **Type**: boolean
- **Default**: `true`
- **Impact**: Improves retrieval accuracy by 20-30% but increases indexing time

**max_context_tokens** - Max tokens for LLM-generated context per chunk
- **Type**: integer
- **Default**: 100
- **Range**: 50-200 recommended
- **Higher values**: More detailed context but slower indexing

**batch_size** - Chunks to process concurrently
- **Type**: integer
- **Default**: 5
- **Range**: 3-10 recommended
- **Higher values**: Faster but more API load

**batch_delay_seconds** - Delay between batches (rate limiting)
- **Type**: float
- **Default**: 0.5
- **Purpose**: Avoid API rate limits

**temperature** - LLM temperature for context generation
- **Type**: float (0-1)
- **Default**: 0.3
- **Recommendation**: Keep low for consistent, factual summaries

**model** - Model for generating context summaries
- **"default"**: Use main LLM from `llm` section
- **Custom**: Specify `"provider/model"` (e.g., `"openrouter/openai/gpt-oss-20b"`)
- **Recommendation**: Use fast, cheap models for cost efficiency

**base_url** - API endpoint (leave empty for default)

**How It Works:**
1. Documents split into chunks (500 chars, 100 overlap)
2. LLM generates context summary for each chunk
3. Context prepended to chunk text before embedding
4. Improves retrieval by preserving document context

---

## course.yaml Reference

Defines course structure, modules, concepts, and content sources.

### Course Metadata

```yaml
course:
  name: "Applied Soft Computing: Modeling Complex Systems with Deep Learning"
  code: "APPLSOFTCOMP"
  description: "Master modern machine learning techniques for text, images, and graphs"
```

**name** - Full course name (shown in bot responses)
**code** - Short course code (shown in `/modules`)
**description** - Brief course summary

---

### Module Structure

Each module follows this format:

```yaml
modules:
  - id: "m01"
    name: "The Data Scientist's Toolkit"
    description: "Tools and principles of reproducible data science"
    content_urls:
      - "https://raw.githubusercontent.com/..."
      - "https://raw.githubusercontent.com/..."
    concepts:
      - id: "version-control"
        name: "Version Control with Git & GitHub"
        type: "practical"
        difficulty: 2
        description: "Version control tracks changes in code and data"
        quiz_focus: "Git commands, GitHub workflows, merge conflicts"
        prerequisites: []
```

**Module Fields:**

**id** - Unique module identifier
- **Format**: Alphanumeric, no spaces (e.g., `"m01"`, `"network-science"`)
- **Used in**: `/quiz module:m01`, `/status module:m01`

**name** - Human-readable module name

**description** - Brief module summary (1-2 sentences)

**content_urls** - List of URLs to course content
- **Format**: Must be publicly accessible
- **Best**: GitHub raw URLs, markdown files
- **Example**: `https://raw.githubusercontent.com/user/repo/master/lecture.md`
- **Purpose**: RAG system fetches and indexes these for quiz generation

---

### Concept Structure

**Concept Fields:**

**id** - Unique concept identifier within module
- **Format**: Kebab-case (e.g., `"version-control"`, `"cnn-building-blocks"`)

**name** - Human-readable concept name

**type** - Concept category
- **"theory"**: Conceptual understanding
- **"practical"**: Applied skills and techniques

**difficulty** - Complexity level (1-5)
- **1**: Introductory
- **2**: Basic
- **3**: Intermediate
- **4**: Advanced
- **5**: Expert

**description** - Brief concept explanation (1-2 sentences)

**quiz_focus** - Comma-separated topics for quiz generation
- **Purpose**: Guides LLM to generate relevant questions
- **Format**: Specific topics, techniques, or subtopics
- **Example**: `"Git commands, GitHub workflows, merge conflicts"`

**prerequisites** - List of prerequisite concept IDs
- **Format**: Array of concept IDs from same or other modules
- **Example**: `["version-control", "tidy-data"]`
- **Empty array**: No prerequisites

---

### Quiz Formats

Defined but only "free-form" currently implemented:

```yaml
quiz_formats:
  - id: "free-form"
    name: "Free Form"
    description: "Explain concepts in your own words"
```

**id** - Format identifier
**name** - Display name
**description** - Format explanation

**Available (not yet implemented):**
- `multiple-choice`
- `short-answer`
- `true-false`
- `fill-blank`

---

## Environment Variables (.env)

Sensitive credentials and channel IDs configured via environment variables.

### Required Variables

```bash
DISCORD_TOKEN=your_discord_bot_token_here
```

**DISCORD_TOKEN** - Discord bot token
- **Get from**: [Discord Developer Portal](https://discord.com/developers/applications)
- **Setup**: Create application → Bot → Copy Token
- **Security**: Never commit to git

---

### Optional Variables

```bash
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

**OPENROUTER_API_KEY** - OpenRouter API key
- **Get from**: [OpenRouter Keys](https://openrouter.ai/keys)
- **Required if**: Using OpenRouter as primary or fallback LLM
- **Free tier**: Available with rate limits

---

```bash
ADMIN_CHANNEL_ID=123456789
```

**ADMIN_CHANNEL_ID** - Channel ID for admin notifications
- **Purpose**: Where attendance codes are displayed (for projector)
- **Get ID**: Enable Developer Mode → Right-click channel → Copy Channel ID
- **Optional**: Bot works without it, but attendance needs it

---

```bash
ATTENDANCE_CHANNEL_ID=987654321
```

**ATTENDANCE_CHANNEL_ID** - Channel where students submit attendance
- **Purpose**: Where students use `/here code:ABC123`
- **Required for**: Attendance tracking feature
- **Get ID**: Same as admin channel

---

```bash
NL_ROUTING_CHANNELS=123456789,987654321
```

**NL_ROUTING_CHANNELS** - Auto-response channels (comma-separated)
- **Purpose**: Channels where bot responds without @mention
- **Format**: Comma-separated channel IDs (no spaces)
- **Example**: `123456789,987654321`
- **Optional**: Leave empty to require @mentions everywhere

---

## Best Practices

### Development vs Production

**Development:**
```yaml
discord:
  sync_commands_on_startup: false  # Faster startup

llm:
  primary:
    timeout: 30  # Shorter timeout for quick iteration
  max_tokens: 512  # Fewer tokens to reduce cost
```

**Production:**
```yaml
discord:
  sync_commands_on_startup: true  # Always sync

llm:
  primary:
    timeout: 60  # More patient
  max_tokens: 1024  # Higher quality responses
```

---

### Cost Optimization

**Use local models when possible:**
```yaml
llm:
  primary:
    provider: "ollama"  # Free local inference
    model: "ministral-3:14b-cloud"
  fallback:
    provider: "openrouter"  # Only when Ollama fails
```

**Choose efficient models:**
- Contextual retrieval: `"openrouter/openai/gpt-oss-20b"` (fast + cheap)
- Quiz model: Smaller models (8B-20B parameters)
- Evaluator: Use local Ollama when possible

---

### Performance Tuning

**Fast response times:**
```yaml
llm:
  timeout: 30
  max_tokens: 512

contextual_retrieval:
  batch_size: 10  # More concurrent requests
  batch_delay_seconds: 0.2  # Less delay
```

**Accuracy over speed:**
```yaml
llm:
  timeout: 90
  max_tokens: 2048
  temperature: 0.3  # More deterministic

mastery:
  min_attempts_for_mastery: 5  # More evidence needed
  quality_threshold: 4.0  # Higher standard
```

---

### Security

**Protect credentials:**
```bash
# .gitignore
.env
credentials/*.json
data/*.db
```

**Limit bot permissions:**
- Only grant necessary Discord permissions
- Use `drive.file` scope (not `drive` full access)
- Keep OAuth tokens secure

**Validate user input:**
- Date formats validated automatically
- Discord user picker prevents invalid users
- Module autocomplete prevents invalid modules

---

## Related Documentation

- [Setup Guide](../SETUP_GUIDE.md) - Initial setup instructions
- [Google Sheets Setup](google-sheets-setup.md) - OAuth configuration
- [Features Guide](features.md) - Feature explanations
- [Commands Reference](commands.md) - All available commands
