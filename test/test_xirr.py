"""XIRR / NPV 纯算法单测（离线，不依赖 DB/网络）。"""
from datetime import date

from app.services.xirr import xirr, xnpv


def test_xnpv_empty_flows():
    assert xnpv(0.1, []) == 0.0


def test_xnpv_simple_rate():
    # 100 投入，1 年后 110，rate=0.1 → NPV≈0
    flows = [(date(2026, 1, 1), -100.0), (date(2027, 1, 1), 110.0)]
    assert abs(xnpv(0.1, flows)) < 1e-6


def test_xirr_simple_positive():
    flows = [(date(2026, 1, 1), -100.0), (date(2027, 1, 1), 110.0)]
    r = xirr(flows)
    assert r is not None
    assert abs(r - 0.1) < 1e-6


def test_xirr_negative_return():
    flows = [(date(2026, 1, 1), -100.0), (date(2027, 1, 1), 90.0)]
    r = xirr(flows)
    assert r is not None
    assert r < 0


def test_xirr_single_flow_none():
    assert xirr([(date(2026, 1, 1), -100.0)]) is None


def test_xirr_no_sign_change_none():
    # 全正无正负变化，无内部收益率
    flows = [(date(2026, 1, 1), 100.0), (date(2027, 1, 1), 110.0)]
    assert xirr(flows) is None
