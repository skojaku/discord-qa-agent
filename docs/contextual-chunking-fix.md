# Contextual Chunking Issue - Root Cause and Fix

## Problem

Contextual chunking has <2% success rate. Only 1-2 chunks out of 50+ are successfully contextualized.

## Root Cause

The `openai/gpt-oss-20b` model configured for contextual retrieval **returns empty content**:
- API call succeeds (no error thrown)
- Tokens are consumed (73 tokens per request)
- Response content is blank

Test results (test_openrouter_models.py):
```
✓ openai/gpt-oss-120b - Returns empty content (73 tokens)
✓ openai/gpt-oss-20b - Returns empty content (73 tokens)
✓ meta-llama/llama-3-8b-instruct - Returns actual content ✓
```

## Why It Wasn't Caught

The old code didn't count empty responses as failures:
```python
if response and response.content:
    success += 1
# If response exists but content is empty → not counted at all!
```

## Solution

### Option 1: Switch to a working model (RECOMMENDED)

Edit `config.yaml` line 101:

```yaml
# Current (returns empty content):
model: "openrouter/openai/gpt-oss-20b"

# Recommended alternatives:
model: "openrouter/meta-llama/llama-3-8b-instruct"  # Fast, works well
# OR
model: "openrouter/openai/gpt-4o-mini"              # Higher quality
# OR
model: "openrouter/google/gemini-2.0-flash-001"     # Fast, cheap
```

### Option 2: Disable contextual retrieval

Edit `config.yaml` line 92:

```yaml
contextual_retrieval:
  enabled: false  # Changed from true
```

Contextual retrieval is optional - your bot will work fine without it.

## Model Naming Convention Clarification

**In this codebase:**
- Config uses `openrouter/model-path` format (e.g., `openrouter/meta-llama/llama-3-8b-instruct`)
- Code strips `openrouter/` prefix before passing to OpenRouterProvider
- OpenRouterProvider uses OpenAI SDK (not LiteLLM) with direct OpenRouter model paths

**Result:** `openrouter/meta-llama/llama-3-8b-instruct` → `meta-llama/llama-3-8b-instruct` (passed to API)

## Testing

After making changes:

```bash
# Test model accessibility
python test_openrouter_models.py

# Test full contextual chunking (with detailed logging)
python test_contextual_chunking.py

# Force reindex with new model
# (or just restart bot - it will reindex on first run)
```

## Improved Logging

The new logging (commit 3a226b9) now detects and logs:
- Empty content responses
- Both providers failing
- Per-document success rates (not just cumulative)

You should now see warnings like:
```
WARNING - LLM returned empty content (provider: openrouter, model: openai/gpt-oss-20b)
```

## Recommended Configuration

For cost-effective contextual chunking:

```yaml
contextual_retrieval:
  enabled: true
  model: "openrouter/meta-llama/llama-3-8b-instruct"
  base_url: "https://openrouter.ai/api/v1"
  max_context_tokens: 100
  batch_size: 5
  batch_delay_seconds: 0.5
  temperature: 0.3
```

Or for higher quality (slightly more expensive):

```yaml
contextual_retrieval:
  enabled: true
  model: "openrouter/openai/gpt-4o-mini"
  base_url: "https://openrouter.ai/api/v1"
  max_context_tokens: 100
  batch_size: 5
  batch_delay_seconds: 0.5
  temperature: 0.3
```
