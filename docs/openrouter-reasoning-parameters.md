# OpenRouter Reasoning Parameters Guide

This guide explains how to configure OpenRouter reasoning models (like gpt-oss-20b, gpt-oss-120b) that require special API parameters.

## What are Reasoning Models?

Reasoning models (similar to OpenAI's o1 series) use step-by-step thinking to solve problems. They require special `reasoning` parameters in the API request to function properly. Without these parameters, they return empty responses (while still charging tokens).

## Supported Models

Known reasoning models on OpenRouter:
- `openai/gpt-oss-20b` - **Requires `max_tokens` format** (see Important Note below)
- `openai/gpt-oss-120b` - **Requires `max_tokens` format** (see Important Note below)

**IMPORTANT:** gpt-oss models do NOT work with `effort` parameter. They require `max_tokens` format.

## Configuration

### Option 1: Standard Model (No Special Config Needed)

For most use cases, use a standard model that doesn't require reasoning parameters:

```yaml
llm:
  fallback:
    provider: "openrouter"
    base_url: "https://openrouter.ai/api/v1"
    model: "meta-llama/llama-3-8b-instruct"
    timeout: 90
    max_retries: 1
```

### Option 2: GPT-OSS Reasoning Model (Requires max_tokens Format)

**CRITICAL:** gpt-oss models (20b, 120b) require `max_tokens` format, NOT `effort`:

```yaml
llm:
  primary:
    provider: "openrouter"
    base_url: "https://openrouter.ai/api/v1"
    model: "openai/gpt-oss-20b"
    timeout: 120
    max_retries: 1
    reasoning:
      max_tokens: 2000  # REQUIRED: Use max_tokens format
```

**Why max_tokens?** These models have mandatory reasoning enabled and return empty responses with `effort` parameters. Only `max_tokens` works correctly.

## Reasoning Parameters

### `reasoning.enabled`
- **Type:** boolean
- **Description:** Enable reasoning mode with default settings
- **Example:** `enabled: true`

### `reasoning.effort`
- **Type:** string
- **Options:** `"xhigh"`, `"high"`, `"medium"`, `"low"`, `"minimal"`, `"none"`
- **Description:** Controls how much reasoning the model performs
  - `"xhigh"`: Maximum reasoning (highest cost, slowest)
  - `"high"`: High reasoning
  - `"medium"`: Balanced reasoning
  - `"low"`: Minimal reasoning (fastest, cheapest) - **RECOMMENDED**
  - `"minimal"`: Very minimal reasoning
  - `"none"`: No reasoning (not recommended for reasoning models)
- **Example:** `effort: "low"`
- **Trade-offs:**
  - Higher effort = better quality but slower and more expensive
  - Lower effort = faster and cheaper but less reasoning depth

### `reasoning.max_tokens`
- **Type:** integer
- **Description:** Maximum tokens to use for reasoning (mutually exclusive with `effort`)
- **Example:** `max_tokens: 1000`
- **Note:** Cannot be used together with `effort`

### `reasoning.exclude`
- **Type:** boolean
- **Description:** Use reasoning internally but don't include reasoning steps in the response
- **Example:** `exclude: true`
- **Default:** `false`

## Advanced: Provider Preferences

You can also configure provider routing preferences:

```yaml
llm:
  fallback:
    provider: "openrouter"
    base_url: "https://openrouter.ai/api/v1"
    model: "openai/gpt-oss-120b"
    reasoning:
      enabled: true
      effort: "low"
    provider_preferences:
      require_parameters: true     # Only use providers supporting all params
      allow_fallbacks: true         # Allow backup providers
      data_collection: "deny"       # Opt out of data collection
```

## Health Check

The bot automatically validates LLM endpoints on startup. If you configure a reasoning model without reasoning parameters, you'll see:

```
================================================================================
LLM HEALTH CHECK FAILED
================================================================================

[openrouter] Model: openai/gpt-oss-120b
Status: UNHEALTHY
Error: Model returned empty response

Troubleshooting:
OpenRouter accepted the request but the model 'openai/gpt-oss-120b' returned no content.

To fix this issue:
1. Check if this is a reasoning model that needs special parameters
2. Verify the model name is correct: https://openrouter.ai/models
3. Try a different model like 'meta-llama/llama-3-8b-instruct'
4. Check your OpenRouter credits: https://openrouter.ai/credits
5. If using reasoning models (gpt-oss-20b), ensure reasoning parameters are set
--------------------------------------------------------------------------------
```

## Recommendations

### For Production Use
- **Use standard models** like `meta-llama/llama-3-8b-instruct`
- Simpler configuration, lower cost, faster responses
- No special parameters needed

### For Reasoning Tasks
- Use reasoning models with `effort: "low"`
- This provides reasoning benefits at minimal cost
- Monitor token usage carefully (reasoning uses extra tokens)

### Cost Considerations
- Reasoning models charge for:
  - Input tokens
  - Output tokens
  - **Reasoning tokens** (the internal thinking)
- `effort: "low"` uses ~20% of tokens for reasoning
- `effort: "high"` can use 100%+ of tokens for reasoning

## Testing

Test your reasoning configuration:

```bash
python test_reasoning_config.py
```

This validates that reasoning parameters are correctly loaded from config.yaml and passed to the OpenRouter provider.

## Example Configurations

### Minimal (Recommended for most cases)
```yaml
llm:
  fallback:
    provider: "openrouter"
    base_url: "https://openrouter.ai/api/v1"
    model: "meta-llama/llama-3-8b-instruct"
    timeout: 90
    max_retries: 1
```

### With Fast Reasoning
```yaml
llm:
  fallback:
    provider: "openrouter"
    base_url: "https://openrouter.ai/api/v1"
    model: "openai/gpt-oss-20b"
    timeout: 120
    max_retries: 1
    reasoning:
      enabled: true
      effort: "low"
```

### With High-Quality Reasoning
```yaml
llm:
  fallback:
    provider: "openrouter"
    base_url: "https://openrouter.ai/api/v1"
    model: "openai/gpt-oss-120b"
    timeout: 180
    max_retries: 1
    reasoning:
      enabled: true
      effort: "medium"
```

## Troubleshooting

### Empty Responses from gpt-oss Models
**Problem:** `gpt-oss-20b` or `gpt-oss-120b` returns empty responses
**Root Cause:** These models have mandatory reasoning and only work with `max_tokens` format
**Solution:** Use `reasoning: { max_tokens: 2000 }` NOT `reasoning: { effort: "low" }`

**Verified Working Config:**
```yaml
model: "openai/gpt-oss-20b"
reasoning:
  max_tokens: 2000
```

**Known NOT Working:**
- `reasoning: { effort: "low" }` - Returns empty ❌
- `reasoning: { enabled: true, effort: "low" }` - Returns empty ❌
- No reasoning params - Returns empty ❌

### Empty Responses from Other Models
**Problem:** Other reasoning models return no content but charge tokens
**Solution:** Check model-specific format (Anthropic/Gemini use max_tokens, OpenAI o-series use effort)

### Slow Responses
**Problem:** Reasoning models are taking too long
**Solution:** Lower the effort level from "high" to "low"

### High Costs
**Problem:** Token usage is higher than expected
**Solution:** Use `effort: "low"` or switch to a standard model

### Health Check Fails
**Problem:** Health check reports model as unhealthy
**Solution:** Check the troubleshooting message - it will guide you to the specific issue

## References

- OpenRouter API Documentation: https://openrouter.ai/docs
- OpenRouter Models: https://openrouter.ai/models
- OpenRouter Reasoning Models: https://openrouter.ai/docs/reasoning
