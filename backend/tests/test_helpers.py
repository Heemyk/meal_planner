from app.api.optimize import _parse_size
from app.workers.tasks import _parse_price


def test_parse_size():
    assert _parse_size("12 fl oz") == 12.0
    assert _parse_size(None) == 1.0


def test_parse_price():
    assert _parse_price("$2.50") == 2.50
    assert _parse_price(None) is None
