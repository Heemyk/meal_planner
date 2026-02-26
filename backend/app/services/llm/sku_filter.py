import json
import re
from typing import List

import dspy

from app.services.llm.dspy_client import run_with_logging
from app.services.llm.prompts import SKU_FILTER_PROMPT_VERSION, SKU_FILTER_TEMPLATE


def _parse_selected(raw: str | list) -> list[dict]:
    """Parse LLM output: may be JSON string (optionally wrapped in ```json ... ```) or list."""
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if not isinstance(raw, str):
        return []
    s = raw.strip()
    # Strip markdown code fence if present (closing ``` may be missing if truncated)
    m = re.search(r"```(?:json)?\s*([\s\S]*?)(?:```|$)", s)
    if m:
        s = m.group(1).strip()
    # Also try extracting [...] if it looks like raw JSON array
    for candidate in (s, re.sub(r"^[^[]*", "", s)):
        if not candidate.strip().startswith("["):
            continue
        try:
            out = json.loads(candidate)
            result = [x for x in (out if isinstance(out, list) else []) if isinstance(x, dict)]
            if result:
                return result
        except json.JSONDecodeError:
            pass
    return []


class SKUFilterSignature(dspy.Signature):
    """Filter SKU search results for relevance."""

    query: str = dspy.InputField()
    candidates: str = dspy.InputField(desc="JSON list of candidate objects")
    prompt_template: str = dspy.InputField()
    selected: List[dict] = dspy.OutputField(desc="subset of candidates that match query")


class SKUFilter(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.Predict(SKUFilterSignature)

    def forward(self, query: str, candidates: List[dict]) -> dspy.Prediction:
        candidates_text = json.dumps(candidates)
        return self.predict(
            query=query,
            candidates=candidates_text,
            prompt_template=SKU_FILTER_TEMPLATE,
        )


def filter_skus(query: str, candidates: List[dict]) -> list[dict]:
    sku_filter = SKUFilter()
    prediction = run_with_logging(
        prompt_name="sku_filter",
        prompt_version=SKU_FILTER_PROMPT_VERSION,
        fn=sku_filter.forward,
        query=query,
        candidates=candidates,
    )
    return _parse_selected(prediction.selected)
