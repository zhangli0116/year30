"""fund_symbol 代码→完整行情 symbol 解析单测（离线）。"""
from app.services.datasource import fund_symbol


def test_shanghai_exchange():
    assert fund_symbol("上交所", "513500") == "sh513500"


def test_shenzhen_exchange():
    assert fund_symbol("深交所", "159915") == "sz159915"


def test_heuristic_sh_5():
    assert fund_symbol(None, "513500") == "sh513500"


def test_heuristic_sh_6():
    assert fund_symbol(None, "600009") == "sh600009"


def test_heuristic_sz_1():
    assert fund_symbol(None, "159915") == "sz159915"
