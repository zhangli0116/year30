"""再平衡偏离判定纯逻辑单测（threshold_for / judge，离线）。"""
from app.services.rebalance import judge, threshold_for

# 默认参数：阈值% = clamp(目标% × 15%, 1%, 3%)
PARAMS = {"r_band": 15.0, "min_abs": 1.0, "max_abs": 3.0, "amount_floor": 300.0}


def test_threshold_clamps_low():
    # 目标 5% → 0.75%，被绝对底线 1% 抬升
    assert threshold_for(5.0, PARAMS) == 1.0


def test_threshold_clamps_high():
    # 目标 40% → 6%，被绝对上限 3% 压回
    assert threshold_for(40.0, PARAMS) == 3.0


def test_threshold_mid():
    # 目标 15% → 2.25%
    assert abs(threshold_for(15.0, PARAMS) - 2.25) < 1e-9


def test_judge_normal_within_threshold():
    assert judge(1.0, 2.0, 300.0, 500.0) == "normal"


def test_judge_above():
    assert judge(3.0, 2.0, 300.0, 500.0) == "above"


def test_judge_below():
    assert judge(-3.0, 2.0, 300.0, 500.0) == "below"


def test_judge_below_amount_floor():
    # 超阈值但偏离金额低于底线 → 不提示
    assert judge(3.0, 2.0, 300.0, 100.0) == "normal"
