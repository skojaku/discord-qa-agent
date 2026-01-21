# Contextual Chunking Issue - Root Cause and Fix

## Problem

Contextual chunking has <2% success rate. Only 1-2 chunks out of 50+ are successfully contextualized.

## Root Cause ✅ SOLVED

The `openai/gpt-oss-20b` model is a **reasoning model** (like OpenAI's o1 series) that requires OpenRouter-specific parameters:
- **Requires:** `reasoning` parameter to enable reasoning mode
- **Without reasoning param:** Returns empty content (96 tokens charged, no text)
- **With reasoning param:** Returns actual content ✓

Test results (test_openrouter_reasoning.py):
```
❌ WITHOUT reasoning param: Empty content (96 tokens)
✓ WITH reasoning (enabled=true): "hello world" (173 tokens)
✓ WITH reasoning (effort='low'): Full summary (134 tokens)
✓ Per-call override: Works correctly
```

## Why It Wasn't Caught

1. **Reasoning models need special parameters**: The OpenRouterProvider didn't support OpenRouter-specific parameters
2. **Empty responses not counted**: The old code didn't count empty responses as failures:
```python
if response and response.content:
    success += 1
# If response exists but content is empty → not counted at all!
```

## Solution ✅ IMPLEMENTED

### Fixed: Added OpenRouter-Specific Parameter Support

The codebase now supports all OpenRouter-specific parameters:

**1. OpenRouterProvider Enhanced** (chibi/llm/openrouter_provider.py):
- Added `reasoning`, `provider`, `transforms` parameters to `__init__`
- Passes OpenRouter params via `extra_body` in API calls
- Supports per-call overrides and instance defaults
- Logs reasoning token usage

**2. Config Schema Updated** (chibi/config.py):
- Added `reasoning`, `provider`, `transforms` fields to `ContextualRetrievalConfig`
- Parses these from config.yaml

**3. Config File Updated** (config.yaml):
```yaml
contextual_retrieval:
  model: "openrouter/openai/gpt-oss-20b"
  reasoning:
    enabled: true  # Required for reasoning models
    effort: "low"  # 20% of tokens for reasoning (fast, cheap)
```

### Alternative: Switch to a Non-Reasoning Model

If you prefer not to use reasoning models:

```yaml
# Fast, simple, no special parameters needed:
model: "openrouter/meta-llama/llama-3-8b-instruct"
# reasoning: not needed
```

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
