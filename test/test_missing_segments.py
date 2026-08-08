"""缺失价格段计算 `_missing_segments` 单测（只统计工作日，周末不算缺失）。"""
from datetime import date

from app.routers.price import _missing_segments

# 2026-03-02 是周一
MON = date(2026, 3, 2)
FRI = date(2026, 3, 6)


def test_no_gap():
    existing = {MON, date(2026, 3, 3), date(2026, 3, 4)}
    assert _missing_segments(existing, MON, date(2026, 3, 4)) == []


def test_full_week_single_segment():
    # 整周工作日缺失 → 一段
    assert _missing_segments(set(), MON, FRI) == [(MON, FRI)]


def test_weekend_not_counted():
    # 周五~周一：只缺周五、周一两天，周末不算
    nxt_mon = date(2026, 3, 9)
    assert _missing_segments(set(), FRI, nxt_mon) == [(FRI, FRI), (nxt_mon, nxt_mon)]


def test_partially_existing_splits_segments():
    # 周三已有，前后各一段
    wed = date(2026, 3, 4)
    segs = _missing_segments({wed}, MON, FRI)
    assert segs == [(MON, date(2026, 3, 3)), (date(2026, 3, 5), FRI)]


def test_start_after_existing_dates():
    # 区间内全部已有 → 无缺失
    existing = {MON, date(2026, 3, 3), date(2026, 3, 4), date(2026, 3, 5), FRI}
    assert _missing_segments(existing, MON, FRI) == []
