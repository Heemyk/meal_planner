from contextlib import contextmanager

from app.services.llm.dspy_client import run_with_logging


def test_run_with_logging(monkeypatch):
    logged = {}

    def fake_log_llm_call(**kwargs):
        logged.update(kwargs)

    def dummy_fn(input_value):
        return {"output": input_value * 2}

    @contextmanager
    def fake_session():
        yield None

    monkeypatch.setattr(
        "app.services.llm.dspy_client.log_llm_call",
        lambda session, **kwargs: fake_log_llm_call(**kwargs),
    )
    monkeypatch.setattr("app.services.llm.dspy_client.get_session", fake_session)

    result = run_with_logging(
        prompt_name="unit_test",
        prompt_version="v1",
        fn=dummy_fn,
        input_value=2,
    )
    assert result == {"output": 4}
    assert logged["prompt_name"] == "unit_test"
