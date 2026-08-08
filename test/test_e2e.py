"""集成回归测试（依赖 DB 与真实数据，需 MySQL 在跑）。

这些不是离线单测，而是把本会话反复手工验证过的关键点固化下来，防止回测/因子/复权/stock 类型回归。
默认被跳过（pyproject `addopts = -m 'not integration'`），显式运行：
    uv run pytest -m integration
"""
import pytest

from app.database import SessionLocal
from app.services import datasource
from app.services.backtest import _merge_strategy, run_backtest
from app.services.price import FUND_TYPE_STOCK

pytestmark = pytest.mark.integration


@pytest.fixture()
def db():
    with SessionLocal() as session:
        yield session


def _first_plan(db):
    from app import crud

    plans = [p for p in crud.plan.list_plans(db) if p.active and p.start_date]
    assert plans, "无带起始日的 active 方案"
    return plans[0]


def test_backtest_structure(db):
    """回测结果结构不变量：有指标/有点；水下≤0、水上≥0；每日持仓占比合计≈100。"""
    plan = _first_plan(db)
    data = run_backtest(db, plan, start_date=plan.start_date)
    m, pts = data["metrics"], data["points"]
    assert m["xirr"] is not None or m["twr"] is not None
    assert len(pts) > 0
    assert all(p["drawdown"] <= 1e-9 for p in pts)  # 水下恒≤0
    assert all(p["drawup"] > -1 for p in pts)  # 近N日滚动涨幅 > -100%（净值恒正，可为负）
    for p in pts:
        total = sum(p["allocations"].values())
        assert abs(total - 100) < 0.5, f"{p['date']} 持仓占比合计 {total}"


def test_backtest_default_strategy_identity(db):
    """默认策略（strategy=None）与显式 _merge_strategy(None) 结果一致（重构回归）。"""
    plan = _first_plan(db)
    a = run_backtest(db, plan, start_date=plan.start_date)
    b = run_backtest(db, plan, start_date=plan.start_date, strategy=_merge_strategy(None))
    assert a["metrics"]["xirr"] == b["metrics"]["xirr"]
    assert len(a["points"]) == len(b["points"])


def test_backtest_factors_scale_amount(db):
    """动态金额因子：必命中档 → 每期金额 = 基准×Σ乘数，period 成交 amount_mult 一致。"""
    plan = _first_plan(db)
    strategy = {
        "amount": {
            "base": 1000,
            "factors": [
                {"id": "f1", "type": "drawdown", "enabled": True, "bands": [{"max": 0, "mult": 1.2}]},
                {"id": "f2", "type": "drawup", "enabled": True, "window": 20, "bands": [{"max": 100, "mult": 0.85}]},
            ],
        }
    }
    data = run_backtest(db, plan, start_date=plan.start_date, strategy=strategy)
    period = [t for t in data["trades"] if t["reason"] == "period"]
    assert period, "无 period 成交"
    assert all(abs((t["amount_mult"] or 0) - 1.02) < 1e-9 for t in period)


def test_get_provider_stock_default(db):
    """stock 类型默认数据源为 tencent。"""
    assert datasource.get_provider(db, FUND_TYPE_STOCK).name == "tencent"


def test_datasource_three_types(db):
    """设置页数据源配置含 etf/stock/otc 三组。"""
    types = datasource.list_type_configs(db)
    labels = {t["fund_type"] for t in types}
    assert {"etf", "stock", "otc"} <= labels
