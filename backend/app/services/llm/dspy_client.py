import time
from typing import Any

import dspy

from app.config import settings
from app.logging import get_logger
from app.storage.db import get_session
from app.storage.repositories import log_llm_call

logger = get_logger(__name__)


def configure_dspy() -> None:
    if settings.llm_provider == "openai":
        lm = dspy.OpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_s,
            max_tokens=1024,  # Avoid truncation of JSON array output (e.g. sku_filter)
        )
    else:
        lm = dspy.OpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_s,
            max_tokens=1024,
        )
    dspy.settings.configure(lm=lm, trace=[])
    logger.info("llm.configure provider=%s model=%s", settings.llm_provider, settings.llm_model)


def run_with_logging(prompt_name: str, prompt_version: str, fn: Any, **kwargs: Any) -> Any:
    start = time.time()
    logger.info("llm.call.start name=%s version=%s", prompt_name, prompt_version)
    result = fn(**kwargs)
    latency_ms = int((time.time() - start) * 1000)
    with get_session() as session:
        log_llm_call(
            session=session,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            model=settings.llm_model,
            input_payload=str(kwargs),
            output_payload=str(result),
            latency_ms=latency_ms,
        )
    _log_last_prompt(prompt_name)
    logger.info("llm.call.end name=%s latency_ms=%s", prompt_name, latency_ms)
    return result


def _log_last_prompt(prompt_name: str) -> None:
    try:
        trace = getattr(dspy.settings, "trace", None)
        if isinstance(trace, list) and trace:
            last = trace[-1]
            logger.info("llm.prompt name=%s content=%s", prompt_name, last)
        else:
            logger.debug("llm.prompt.empty name=%s", prompt_name)
    except Exception as exc:  # noqa: BLE001 - avoid breaking runtime on inspection
        logger.warning("llm.prompt.inspect_failed name=%s error=%s", prompt_name, exc)
