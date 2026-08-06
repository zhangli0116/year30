"""XIRR 资金加权年化收益率（纯 Python，无第三方依赖）。

现金流符号约定（与 Excel XIRR 一致）：
    投入/存入 = 负数；回收/当前价值 = 正数。
    xirr 求解 Σ amount_i / (1+r)^(days_i/365) = 0 的 r。
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.services.quote import fetch_quotes


def xnpv(rate: float, flows: list[tuple[date, float]]) -> float:
    """净现值：以最早现金流日期为基准折算。"""
    if not flows:
        return 0.0
    t0 = min(d for d, _ in flows)
    return sum(
        amt / (1.0 + rate) ** ((d - t0).days / 365.0) for d, amt in flows
    )


def xirr(flows: list[tuple[date, float]], guess: float = 0.1) -> float | None:
    """求解内部收益率。收敛失败或数据不足时返回 None。

    先牛顿迭代，失败则在整个可行域粗扫找变号区间再二分，覆盖负收益/极端情形。
    注：持有期很短时年化会被放大（如 6 天亏 0.4% → 年化 -21%），前端会标注"基于 N 天"。
    """
    flows = [(d, float(a)) for d, a in flows if a]  # 忽略 0 金额
    if len(flows) < 2:
        return None
    if all(a > 0 for _, a in flows) or all(a < 0 for _, a in flows):
        return None  # 无正负号变化，无内部收益率
    t0 = min(d for d, _ in flows)
    ys = [(d - t0).days / 365.0 for d, _ in flows]
    amts = [a for _, a in flows]

    def f(r: float) -> float:
        return sum(a / (1.0 + r) ** y for y, a in zip(ys, amts))

    def df(r: float) -> float:
        return sum(-a * y / (1.0 + r) ** (y + 1) for y, a in zip(ys, amts))

    # ---- 牛顿迭代 ----
    r = guess
    converged = False
    for _ in range(200):
        if r <= -1 or r > 1e6:
            break
        try:
            fx, dx = f(r), df(r)
        except (OverflowError, ZeroDivisionError, ValueError):
            break
        if not (math.isfinite(fx) and math.isfinite(dx)) or dx == 0:
            break
        nr = r - fx / dx
        if abs(nr - r) < 1e-9:
            r = nr
            converged = abs(f(nr)) < 1e-4
            break
        r = nr

    if converged and math.isfinite(r) and -1 < r:
        return r

    # ---- 二分兜底：粗扫找变号区间 ----
    def scan(lo: float, hi: float) -> float | None:
        prev_r, prev_f = lo, f(lo)
        if abs(prev_f) < 1e-8:
            return prev_r
        r = lo
        while r < hi:
            if r >= 0:
                r = min(r * 1.6 + 0.02, hi)
            else:
                r += 0.05
            fr = f(r)
            if not (math.isfinite(fr) and math.isfinite(prev_f)):
                prev_r, prev_f = r, fr
                continue
            if abs(fr) < 1e-8:
                return r
            if (prev_f > 0) != (fr > 0):
                a, b = prev_r, r
                fa = prev_f
                for _ in range(100):
                    m = (a + b) / 2
                    fm = f(m)
                    if abs(fm) < 1e-8:
                        return m
                    if (fa > 0) == (fm > 0):
                        a, fa = m, fm
                    else:
                        b = m
                return (a + b) / 2
            prev_r, prev_f = r, fr
        return None

    found = scan(-0.9999, 1.0)
    if found is None:
        found = scan(1.0, 1e6)
    return found


def twr_plan(db: Session, plan_id: int, today: date | None = None) -> dict | None:
    """时间加权收益率（期间，非年化）：剥离投入时点，衡量策略本身表现。

    每日组合价值 V = 权益 + 现金：
      - 权益用「购买记录累计份额 × 该基金最近收盘价(前向填充)」重建（不依赖 fund_holding_daily，
        避免买入发生在非交易日时权益晚现造成假尖峰）
      - 现金取 fund_cash_daily
    外部现金流 = 方案季度预算入账。每日子收益率 r_t = (V_t − V_{t−1} − 入账_t) / V_{t−1}；
    TWR = Π(1+r_t) − 1。数据不足（<2 个可算日）返回 None。短期不被年化放大。
    """
    from app import crud

    today = today or date.today()
    purchases = list(
        db.scalars(
            select(models.PurchaseRecord)
            .where(models.PurchaseRecord.plan_id == plan_id)
            .order_by(models.PurchaseRecord.purchase_date)
        ).all()
    )
    if not purchases:
        return None
    fund_ids = {p.fund_id for p in purchases}
    # 每只基金价格序列 [(date, close)] 升序
    price_series: dict[int, list] = {}
    for fid in fund_ids:
        price_series[fid] = db.execute(
            select(models.FundPrice.trade_date, models.FundPrice.close_price)
            .where(models.FundPrice.fund_id == fid)
            .order_by(models.FundPrice.trade_date)
        ).all()
    # 每日现金
    cash_map = {
        d: float(c)
        for d, c in db.execute(
            select(models.FundCashDaily.trade_date, models.FundCashDaily.cash_amount)
            .where(models.FundCashDaily.plan_id == plan_id)
            .order_by(models.FundCashDaily.trade_date)
        ).all()
    }
    # 外部现金流：季度预算入账
    deposits: dict[date, float] = {}
    for q in crud.quarter.list_quarters(db, plan_id):
        if q.start_date:
            deposits[q.start_date] = deposits.get(q.start_date, 0.0) + float(q.budget)
    if not cash_map:
        return None

    start = min(p.purchase_date for p in purchases)
    if cash_map:
        start = min(start, min(cash_map))
    day = start
    shares: dict[int, int] = {}
    pi = 0
    price_idx = {fid: 0 for fid in fund_ids}
    prev_v = 0.0
    twr = 1.0
    count = 0
    while day <= today:
        while pi < len(purchases) and purchases[pi].purchase_date <= day:
            p = purchases[pi]
            sign = -1 if p.type == "sell" else 1
            shares[p.fund_id] = shares.get(p.fund_id, 0) + sign * p.hands * p.shares_per_hand
            pi += 1
        # 权益 = Σ 份额 × 最近收盘价（前向填充）
        equity = 0.0
        for fid in fund_ids:
            s = price_series[fid]
            while price_idx[fid] < len(s) and s[price_idx[fid]][0] <= day:
                price_idx[fid] += 1
            if price_idx[fid] > 0:
                equity += shares.get(fid, 0) * float(s[price_idx[fid] - 1][1])
        cash = cash_map.get(day)
        if cash is None:
            day += timedelta(days=1)
            continue
        v = equity + cash
        dep = deposits.get(day, 0.0)
        if prev_v > 0:
            r = (v - prev_v - dep) / prev_v
            twr *= 1 + r
            count += 1
        prev_v = v
        day += timedelta(days=1)
    if count < 2:
        return None
    return {"twr": round(twr - 1, 6), "span_days": (today - start).days}


def _price_map(db: Session, codes: list[str]) -> dict[str, float]:
    """批量现价：优先实时行情，缺失/失败回退最新历史收盘价。"""
    prices: dict[str, float] = {}
    try:
        quotes = fetch_quotes(codes)
        for q in quotes:
            if q.get("last") is not None:
                prices[q["code"]] = float(q["last"])
    except Exception:  # noqa: BLE001
        quotes = []
    missing = [c for c in codes if c not in prices]
    if missing:
        # 基金 id -> 代码，用于回退查询最新收盘价
        fund_codes = dict(
            db.execute(
                select(models.Fund.id, models.Fund.fund_code).where(
                    models.Fund.fund_code.in_(missing)
                )
            ).all()
        )
        fund_prices = db.execute(
            select(models.FundPrice.fund_id, models.FundPrice.trade_date, models.FundPrice.close_price)
            .where(models.FundPrice.fund_id.in_(fund_codes.keys()))
            .order_by(models.FundPrice.trade_date)
        ).all()
        best: dict[int, tuple[date, float]] = {}
        for fid, td, close in fund_prices:
            if close is None:
                continue
            if fid not in best or td > best[fid][0]:
                best[fid] = (td, float(close))
        for fid, (_, close) in best.items():
            code = fund_codes.get(fid)
            if code:
                prices[code] = close
    return prices


def _funds_with_shares(db: Session, plan_id: int | None = None) -> list[dict]:
    """每只有购买记录的真实基金：代码/名称/累计份额（买入−卖出，排除现金基金）。

    plan_id 提供时只统计该方案下的购买记录；None 回退全账户（兼容旧行为）。
    已全部卖出的基金（份额=0）也保留——其收益已由卖出现金流体现。
    """
    from sqlalchemy import case, func

    join_cond = models.PurchaseRecord.fund_id == models.Fund.id
    if plan_id is not None:
        join_cond = join_cond & (models.PurchaseRecord.plan_id == plan_id)

    rows = db.execute(
        select(
            models.Fund.id.label("fund_id"),
            models.Fund.fund_code,
            models.Fund.fund_name,
            func.coalesce(
                func.sum(
                    case(
                        (
                            models.PurchaseRecord.type == "sell",
                            -(
                                models.PurchaseRecord.hands
                                * models.PurchaseRecord.shares_per_hand
                            ),
                        ),
                        else_=models.PurchaseRecord.hands
                        * models.PurchaseRecord.shares_per_hand,
                    )
                ),
                0,
            ).label("total_shares"),
            func.count(models.PurchaseRecord.id).label("rec_count"),
        )
        .outerjoin(models.PurchaseRecord, join_cond)
        .where(models.Fund.fund_code != "000000")
        .group_by(models.Fund.id, models.Fund.fund_code, models.Fund.fund_name)
        .having(func.count(models.PurchaseRecord.id) > 0)
        .order_by(models.Fund.fund_code)
    ).all()
    return [
        {
            "fund_id": row.fund_id,
            "fund_code": row.fund_code,
            "fund_name": row.fund_name,
            "total_shares": int(row.total_shares or 0),
        }
        for row in rows
    ]


def account_xirr(
    db: Session,
    plan_id: int | None = None,
    prices: dict[str, float] | None = None,
) -> dict:
    """全账户资金加权年化：预算到账为投入，今日总资产（权益市值+现金）为终值。

    plan_id 提供时按方案统计（该方案季度预算 + 该方案购买记录）；None 回退全账户。
    """
    from app import crud

    quarters = crud.quarter.list_quarters(db, plan_id)
    flows: list[tuple[date, float]] = []
    invested = 0.0
    start_date: date | None = None
    for q in quarters:
        if not q.budget or q.budget <= 0:
            continue
        flow_date = q.start_date
        if flow_date is None:
            # 回退：该季度最早购买日
            rec = db.scalars(
                select(models.PurchaseRecord.purchase_date)
                .where(models.PurchaseRecord.quarter_id == q.id)
                .order_by(models.PurchaseRecord.purchase_date)
                .limit(1)
            ).first()
            flow_date = rec
        if flow_date is None:
            continue  # 无日期可标注，跳过该季预算
        flows.append((flow_date, -float(q.budget)))
        invested += float(q.budget)
        start_date = flow_date if start_date is None else min(start_date, flow_date)

    funds = _funds_with_shares(db, plan_id)
    if prices is None:
        codes = [f["fund_code"] for f in funds]
        prices = _price_map(db, codes) if codes else {}
    equity = sum(
        f["total_shares"] * prices[f["fund_code"]]
        for f in funds
        if f["fund_code"] in prices
    )
    cash = sum(float(q.cash_amount or 0) for q in quarters)
    current_value = equity + cash

    if not flows:
        return {
            "xirr": None,
            "invested": invested,
            "current_value": current_value,
            "gain": current_value - invested,
            "gain_pct": None,
            "start_date": None,
        }
    flows.append((date.today(), current_value))
    rate = xirr(flows)
    gain = current_value - invested
    span_days = (date.today() - start_date).days if start_date else 0
    return {
        "xirr": rate,
        "invested": round(invested, 2),
        "current_value": round(current_value, 2),
        "gain": round(gain, 2),
        "gain_pct": round(gain / invested * 100, 2) if invested > 0 else None,
        "start_date": start_date.isoformat() if start_date else None,
        "span_days": span_days,
    }


def fund_xirr(
    db: Session,
    fund_id: int,
    plan_id: int | None = None,
    price: float | None = None,
) -> dict:
    """单基金资金加权年化：买卖现金流 + 期末市值（可按方案过滤）。"""
    fund = db.get(models.Fund, fund_id)
    if fund is None:
        return {"fund_id": fund_id, "xirr": None, "current_mv": 0.0, "invested": 0.0, "flows_count": 0}
    stmt = select(models.PurchaseRecord).where(models.PurchaseRecord.fund_id == fund_id)
    if plan_id is not None:
        stmt = stmt.where(models.PurchaseRecord.plan_id == plan_id)
    records = list(db.scalars(stmt.order_by(models.PurchaseRecord.purchase_date)).all())
    flows: list[tuple[date, float]] = []
    invested = 0.0
    shares = 0
    for rec in records:
        amt = float(rec.total_amount)
        if rec.type == "sell":
            flows.append((rec.purchase_date, amt - float(rec.fee or 0)))
            shares -= rec.hands * rec.shares_per_hand
        else:
            flows.append((rec.purchase_date, -amt))
            invested += amt
            shares += rec.hands * rec.shares_per_hand
    current_mv = 0.0
    if price is None:
        codes = [fund.fund_code]
        price = _price_map(db, codes).get(fund.fund_code)
    if shares > 0 and price is not None:
        current_mv = shares * price
        flows.append((date.today(), current_mv))
    rate = xirr(flows) if len(flows) >= 2 else None
    span_days = 0
    if records:
        span_days = (date.today() - min(r.purchase_date for r in records)).days
    return {
        "fund_id": fund_id,
        "xirr": rate,
        "current_mv": round(current_mv, 2),
        "invested": round(invested, 2),
        "flows_count": len(flows),
        "span_days": span_days,
    }
