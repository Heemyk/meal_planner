# LLMOps + MLOps Practices

## Prompt Management
- Versioned prompts in `app/services/llm/prompts.py`.
- Log inputs/outputs and latency to `llmcalllog`.

## Reliability
- DSPy orchestration for deterministic program interfaces.
- Low temperature for normalization tasks.
- Structured outputs validated by downstream code paths.

## Evaluation
- Create offline eval sets from historical recipes.
- Track accuracy of ingredient canonicalization and unit normalization.
- Compare SKU filtering precision/recall against labeled sets.

## Observability
- Store LLM call metadata (prompt, model, latency).
- Add trace IDs at request boundaries when integrating APM.

## Cost Controls
- Use small models first for parsing and normalization.
- Cache decisions by ingredient text + model + prompt version.
