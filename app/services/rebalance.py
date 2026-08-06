"""再平衡偏离判定与分析。

判定模型（与前端 ui/src/utils/rebalance.js 保持同一公式）：
    阈值(%) = clamp(目标% × R, 底线%, 上限%)
    状态   = |偏离| > 阈值 且 偏离金额 ≥ 金额底线 → above/below；否则 normal

参数存 app_setting 表，缺省读 app/config.py 的 RB_* 默认值。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud, models
from app.config import settings

KEY_R_BAND = "rebalance.r_band"
KEY_MIN_ABS = "rebalance.min_abs"
KEY_MAX_ABS = "rebalance.max_abs"
KEY_AMOUNT_FLOOR = "rebalance.amount_floor"

_KEY_MAP = {
    "r_band": KEY_R_BAND,
    "min_abs": KEY_MIN_ABS,
    "max_abs": KEY_MAX_ABS,
    "amount_floor": KEY_AMOUNT_FLOOR,
}


def default_params() -> dict:
    return {
        "r_band": float(settings.RB_R_BAND),
        "min_abs": float(settings.RB_MIN_ABS),
        "max_abs": float(settings.RB_MAX_ABS),
        "amount_floor": float(settings.RB_AMOUNT_FLOOR),
    }


def get_params(db: Session) -> dict:
    """读取判定参数：app_setting 优先，缺省回退 config 默认。"""
    params = default_params()
    stored = crud.app_setting.get_all(db)
    for name, key in _KEY_MAP.items():
        if key in stored:
            try:
                params[name] = float(stored[key])
            except (TypeError, ValueError):
                pass
    return params


def save_params(db: Session, params: dict) -> dict:
    """保存判定参数（只写传入的非空字段），返回更新后的完整参数。"""
    for name, key in _KEY_MAP.items():
        if name in params and params[name] is not None:
            crud.app_setting.set_setting(db, key, str(params[name]))
    return get_params(db)


def threshold_for(target: float, params: dict) -> float:
    """阈值(%) = clamp(目标% × R, 底线, 上限)。"""
    return min(
        params["max_abs"],
        max(params["min_abs"], target * params["r_band"] / 100.0),
    )


def judge(
    deviation: float,
    threshold: float,
    amount_floor: float,
    deviation_amount: float | None,
) -> str:
    """above / below / normal：超阈值且偏离金额达底线才提示。"""
    if abs(deviation) <= threshold:
        return "normal"
    if deviation_amount is not None and abs(deviation_amount) < amount_floor:
        return "normal"
    return "above" if deviation > 0 else "below"


def _prices_for_funds(db: Session, codes: list[str]) -> dict[str, float]:
    """批量现价：实时行情优先，缺失回退最新历史收盘价。"""
    from app.services.xirr import _price_map

    return _price_map(db, codes) if codes else {}


def analyze(db: Session) -> dict:
    """再平衡体检分析：每只基金的目标/当前占比/偏离/偏离金额/阈值 + 现金行。

    只计算偏离与阈值，不做状态判定——判定由前端共享模块统一做。
    """
    from app.services.xirr import _funds_with_shares

    params = get_params(db)
    funds = [f for f in crud.fund.list_funds(db, 1, 100)[0] if f.fund_code != "000000"]
    target_map = {
        f.id: float(f.target_ratio) if f.target_ratio is not None else None
        for f in funds
    }
    # 现金目标比例：现金基金 target_ratio，缺失时 100 − Σ基金目标
    cash_fund = db.scalar(
        select(models.Fund).where(models.Fund.fund_code == "000000")
    )
    if cash_fund is not None and cash_fund.target_ratio is not None:
        cash_target = float(cash_fund.target_ratio)
    else:
        cash_target = max(
            0.0, 100.0 - sum(t for t in target_map.values() if t is not None)
        )

    funds_info = _funds_with_shares(db)
    prices = _prices_for_funds(db, [f["fund_code"] for f in funds_info])
    quarters = crud.quarter.list_quarters(db)
    cash = sum(float(q.cash_amount or 0) for q in quarters)

    mvs: dict[int, float] = {
        f["fund_id"]: f["total_shares"] * prices.get(f["fund_code"], 0.0)
        for f in funds_info
    }
    total = sum(mvs.values()) + cash

    fund_rows = []
    for f in funds_info:
        target = target_map.get(f["fund_id"])
        real = (mvs[f["fund_id"]] / total * 100) if total > 0 else 0.0
        deviation = real - target if target is not None else 0.0
        fund_rows.append(
            {
                "fund_id": f["fund_id"],
                "fund_code": f["fund_code"],
                "fund_name": f["fund_name"],
                "price": prices.get(f["fund_code"]),
                "target": round(target, 2) if target is not None else None,
                "real": round(real, 2),
                "deviation": round(deviation, 2),
                "deviation_amount": round(deviation / 100 * total, 2),
                "threshold": (
                    round(threshold_for(target, params), 2)
                    if target is not None
                    else None
                ),
            }
        )

    cash_real = (cash / total * 100) if total > 0 else 0.0
    cash_deviation = cash_real - cash_target
    cash_row = {
        "target": round(cash_target, 2),
        "real": round(cash_real, 2),
        "deviation": round(cash_deviation, 2),
        "deviation_amount": round(cash_deviation / 100 * total, 2),
        "threshold": round(threshold_for(cash_target, params), 2),
    }

    return {
        "params": params,
        "total": round(total, 2),
        "funds": fund_rows,
        "cash": cash_row,
    }
