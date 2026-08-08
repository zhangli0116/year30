"""策略实验室：因子 band 查找 / 乘数叠加 / 配置合并 单测（离线，不依赖 DB/网络）。"""
from app.services.backtest import _band_multiplier, _factor_multiplier, _merge_strategy


def test_band_open_low():
    bands = [{"min": None, "max": -0.15, "mult": 1.2}, {"min": -0.15, "max": 0, "mult": 1.0}]
    assert _band_multiplier(bands, -0.2) == 1.2  # 命中下限开区间
    assert _band_multiplier(bands, -0.1) == 1.0
    assert _band_multiplier(bands, 0.0) == 1.0  # 闭区间包含 0


def test_band_open_high():
    bands = [{"min": 0.08, "max": None, "mult": 0.85}, {"min": 0, "max": 0.08, "mult": 1.0}]
    assert _band_multiplier(bands, 0.1) == 0.85  # 命中上限开区间
    assert _band_multiplier(bands, 0.08) == 0.85  # 闭区间包含 0.08
    assert _band_multiplier(bands, 0.05) == 1.0


def test_band_out_of_range_default():
    bands = [{"min": 0, "max": 0.1, "mult": 0.9}]
    assert _band_multiplier(bands, 0.5) == 1.0  # 未命中 → 默认 1.0
    assert _band_multiplier([], 0.5) == 1.0


def test_factor_stacking():
    factors = [
        {"id": "f1", "type": "drawdown", "enabled": True, "bands": [{"max": 0, "mult": 1.2}]},
        {"id": "f2", "type": "drawup", "enabled": True, "window": 20, "bands": [{"max": 100, "mult": 0.85}]},
    ]
    nav_history = [1.0] * 25
    # 水下 sig = 0.9/1.0−1 = −0.1 → 1.2；水上 sig = 0.9/1.0−1 = −0.1 → 0.85 → 乘积
    mult = _factor_multiplier(factors, 0.9, 1.0, nav_history, 20)
    assert abs(mult - 1.2 * 0.85) < 1e-9


def test_factor_disabled_skipped():
    factors = [{"id": "f", "type": "drawdown", "enabled": False, "bands": [{"max": 0, "mult": 1.2}]}]
    assert _factor_multiplier(factors, 0.9, 1.0, [], 20) == 1.0


def test_factor_drawup_insufficient_history():
    # 历史不足 → 信号取 0 → 命中 {max:100} 档 → 0.5
    factors = [{"id": "f", "type": "drawup", "enabled": True, "window": 20, "bands": [{"max": 100, "mult": 0.5}]}]
    assert _factor_multiplier(factors, 1.0, 1.0, [1.0] * 5, 20) == 0.5


def test_merge_strategy_defaults():
    s = _merge_strategy(None)
    assert s["buy_rebalance"] is True
    assert s["fees"]["buy_rate"] == 0.03
    assert s["amount"]["factors"] == []


def test_merge_strategy_partial():
    s = _merge_strategy({"buy_rebalance": False, "fees": {"buy_rate": 0.1}})
    assert s["buy_rebalance"] is False
    assert s["fees"]["buy_rate"] == 0.1
    assert s["fees"]["sell_rate"] == 0.07  # 未覆盖保持默认
