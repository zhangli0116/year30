"""复权净值计算纯函数单测（分红复投口径）。"""
from datetime import date
from decimal import Decimal

from app.services.adjnav import compute_adj_nav


def test_no_dividend_equals_unit():
    unit = {date(2026, 1, 1): Decimal("1.0"), date(2026, 1, 2): Decimal("1.05")}
    adj = compute_adj_nav(unit, [])
    assert adj[date(2026, 1, 1)] == Decimal("1.0000")
    assert adj[date(2026, 1, 2)] == Decimal("1.0500")


def test_single_dividend_reinvestment():
    # 1.0 → 1.1 → 除息 0.1（除权后单位=1.0）→ 1.05
    unit = {
        date(2026, 1, 1): Decimal("1.0"),
        date(2026, 1, 2): Decimal("1.1"),
        date(2026, 1, 3): Decimal("1.0"),  # 除息日单位净值
        date(2026, 1, 4): Decimal("1.05"),
    }
    adj = compute_adj_nav(unit, [(date(2026, 1, 3), 0.1)])
    # 除息日: F=1×(1+0.1/1.0)=1.1 → adj=1.0×1.1=1.1；后续 1.05×1.1=1.155
    assert abs(float(adj[date(2026, 1, 3)]) - 1.1) < 1e-9
    assert abs(float(adj[date(2026, 1, 4)]) - 1.155) < 1e-9


def test_multiple_dividends_compounding():
    unit = {
        date(2026, 1, 1): Decimal("1.0"),
        date(2026, 1, 2): Decimal("1.0"),  # 除息日1：分红 0.1
        date(2026, 1, 3): Decimal("1.0"),  # 除息日2：分红 0.1
    }
    adj = compute_adj_nav(unit, [(date(2026, 1, 2), 0.1), (date(2026, 1, 3), 0.1)])
    # F: 1/2→1.1；1/3→1.1×(1+0.1/1.0)=1.21 → adj=1.21
    assert abs(float(adj[date(2026, 1, 3)]) - 1.21) < 1e-9


def test_dividend_date_missing_unit_uses_next():
    # 分红日无单位净值 → 顺延到下一净值日结算
    unit = {date(2026, 1, 1): Decimal("1.0"), date(2026, 1, 4): Decimal("1.05")}
    adj = compute_adj_nav(unit, [(date(2026, 1, 2), 0.05)])
    # 1/4: F=1×(1+0.05/1.05)=1.047619 → adj=1.05×1.047619≈1.1
    assert abs(float(adj[date(2026, 1, 4)]) - 1.1) < 1e-6
