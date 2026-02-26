import time
from typing import Any

import dspy

from app.config import settings
from app.logging import get_logger
from app.storage.db import get_session
from app.storage.repositories import log_llm_call
from app.utils.timing import _format_duration

logger = get_logger(__name__)


def _make_openai_lm(model: str, max_tokens: int = 1024) -> dspy.LM:
    return dspy.OpenAI(
        model=model,
        api_key=settings.llm_api_key,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_s,
        max_tokens=max_tokens,
    )


def configure_dspy() -> None:
    lm = _make_openai_lm(settings.llm_model)
    dspy.settings.configure(lm=lm, trace=[])
    logger.info("llm.configure provider=%s model=%s", settings.llm_provider, settings.llm_model)


def run_with_logging(
    prompt_name: str,
    prompt_version: str,
    fn: Any,
    *,
    model: str | None = None,
    **kwargs: Any,
) -> Any:
    return _run_llm_call(
        prompt_name,
        prompt_version,
        fn,
        model=model or settings.llm_model,
        use_custom_model=model is not None,
        **kwargs,
    )


def _run_llm_call(
    prompt_name: str,
    prompt_version: str,
    fn: Any,
    *,
    model: str,
    use_custom_model: bool = False,
    **kwargs: Any,
) -> Any:
    start = time.time()
    logger.info("[TIMING] llm.call.start name=%s version=%s model=%s", prompt_name, prompt_version, model)
    prev_lm = None
    if use_custom_model:
        prev_lm = dspy.settings.lm
        dspy.settings.configure(lm=_make_openai_lm(model), trace=getattr(dspy.settings, "trace", []))
    fn_kwargs = {k: v for k, v in kwargs.items() if k != "model"}
    try:
        result = fn(**fn_kwargs)
    finally:
        if prev_lm is not None:
            dspy.settings.configure(lm=prev_lm, trace=getattr(dspy.settings, "trace", []))
    latency_ms = int((time.time() - start) * 1000)
    with get_session() as session:
        log_llm_call(
            session=session,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            model=model,
            input_payload=str(kwargs),
            output_payload=str(result),
            latency_ms=latency_ms,
        )
    _log_last_prompt(prompt_name)
    logger.info(
        "[TIMING] llm.call.end name=%s latency_ms=%s (%s)",
        prompt_name,
        latency_ms,
        _format_duration(latency_ms),
    )
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
