"""AKShare Provider 纯工具单测（_strip_market，不触发网络调用）。"""
from app.services.akshare import _strip_market


def test_strip_market_sh():
    assert _strip_market("sh513500") == "513500"


def test_strip_market_sz():
    assert _strip_market("sz159915") == "159915"


def test_strip_market_bare_code():
    assert _strip_market("513500") == "513500"
