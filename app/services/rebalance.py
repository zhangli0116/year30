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


def suggest(row: dict, total: float) -> str:
    """建议动作：低配→加仓、超配→减仓；现金行特殊。

    gap = (目标 − 当前) / 100 × 总市值，正数=需加仓、负数=需减仓。
    """
    if row.get("status") == "normal" or row.get("target") is None:
        return "—"
    gap = (row["target"] - row["real"]) / 100 * total
    abs_gap = abs(gap)
    if row.get("fund_code") == "000000":
        return "现金偏低，可减少基金买入" if gap > 0 else "现金偏多，可加仓低配基金"
    price = row.get("price")
    hand_price = (price * 100) if price else 0
    action = "加仓" if gap > 0 else "减仓"
    if hand_price > 0:
        hands = int(abs_gap // hand_price)
        if hands > 0:
            return f"建议{action}约 {hands} 手（¥{abs_gap:.0f}）"
    return f"建议{action}约 ¥{abs_gap:.0f}"


def analyze(db: Session, plan_id: int, params: dict | None = None) -> dict:
    """再平衡体检分析：某方案下每只基金的目标/当前占比/偏离/偏离金额/阈值/状态/建议动作 + 现金行。

    目标比例取该方案 plan_fund（fund_id→target），现金目标取 plan.cash_ratio；
    份额/市值只统计该方案下的购买记录；现金余额 = Σ 该方案 quarter.cash_amount。
    状态与建议动作都在后端统一计算（单一来源，便于后续接入大模型分析）。
    """
    from app.services.xirr import _funds_with_shares

    params = params if params is not None else get_params(db)
    plan = db.get(models.DcaPlan, plan_id)
    if plan is None:
        raise ValueError(f"方案 {plan_id} 不存在")
    # 现金目标比例：方案显式 cash_ratio（落实不满仓，Σ标的+现金=100）
    cash_target = float(plan.cash_ratio)

    # 方案配置的标的（含无持仓的，新方案也能看到目标占比）
    plan_funds = db.execute(
        select(
            models.Fund.id, models.Fund.fund_code, models.Fund.fund_name,
            models.PlanFund.target_ratio,
        )
        .join(models.PlanFund, models.PlanFund.fund_id == models.Fund.id)
        .where(models.PlanFund.plan_id == plan_id)
        .order_by(models.Fund.fund_code)
    ).all()
    funds_info = _funds_with_shares(db, plan_id)
    extra_codes = [
        f["fund_code"]
        for f in funds_info
        if f["fund_id"] not in {x[0] for x in plan_funds}
    ]
    prices = _prices_for_funds(db, [x[1] for x in plan_funds] + extra_codes)
    quarters = crud.quarter.list_quarters(db, plan_id)
    cash = sum(float(q.cash_amount or 0) for q in quarters)

    share_map = {f["fund_id"]: f["total_shares"] for f in funds_info}
    # 合并：方案配置标的优先，另加"有持仓但不在配置中"的（防御）
    fund_defs: list[tuple[int, str, str, float | None]] = [
        (x[0], x[1], x[2], float(x[3])) for x in plan_funds
    ]
    seen_ids = {x[0] for x in fund_defs}
    for f in funds_info:
        if f["fund_id"] not in seen_ids:
            fund_defs.append((f["fund_id"], f["fund_code"], f["fund_name"], None))

    mvs: dict[int, float] = {
        fid: share_map.get(fid, 0) * prices.get(code, 0.0)
        for fid, code, _, _ in fund_defs
    }
    total = sum(mvs.values()) + cash

    # 金额底线只对"已有组合"生效；新方案 total=0 时按纯比例判定（应显示低配需买入）
    dev_amount = lambda d: (round(d / 100 * total, 2) if total > 0 else None)

    fund_rows = []
    for fid, fcode, fname, target in fund_defs:
        real = (mvs[fid] / total * 100) if total > 0 else 0.0
        deviation = real - target if target is not None else 0.0
        row = {
            "fund_id": fid,
            "fund_code": fcode,
            "fund_name": fname,
            "price": prices.get(fcode),
            "target": round(target, 2) if target is not None else None,
            "real": round(real, 2),
            "deviation": round(deviation, 2),
            "deviation_amount": dev_amount(deviation),
            "threshold": (
                round(threshold_for(target, params), 2) if target is not None else None
            ),
        }
        row["status"] = (
            judge(deviation, row["threshold"], params["amount_floor"], row["deviation_amount"])
            if row["threshold"] is not None
            else "normal"
        )
        row["suggestion"] = (
            "尚未开始定投，请按方案执行" if total <= 0 else suggest(row, total)
        )
        fund_rows.append(row)

    cash_real = (cash / total * 100) if total > 0 else 0.0
    cash_deviation = cash_real - cash_target
    cash_row = {
        "target": round(cash_target, 2),
        "real": round(cash_real, 2),
        "deviation": round(cash_deviation, 2),
        "deviation_amount": dev_amount(cash_deviation),
        "threshold": round(threshold_for(cash_target, params), 2),
    }
    cash_row["status"] = judge(
        cash_deviation, cash_row["threshold"], params["amount_floor"], cash_row["deviation_amount"]
    )
    cash_row["suggestion"] = (
        "尚未开始定投，请按方案执行"
        if total <= 0
        else suggest({**cash_row, "fund_code": "000000"}, total)
    )

    return {
        "params": params,
        "total": round(total, 2),
        "funds": fund_rows,
        "cash": cash_row,
    }
