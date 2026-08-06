from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

HANDS = 100  # 每手份数


def generate(
    db: Session,
    plan_id: int,
    fund_id: int,
    start_date: date,
    end_date: date,
    only_missing: bool = False,
) -> int:
    """按天生成权益流水：某方案某基金在 [start, end] 内，每天累计持有份额 × 当日收盘价。

    - 累计份额 = Σ(该方案下买入 hand×份/手 − 卖出 hand×份/手)，按购买日期 ≤ 当日累计
    - 价格取 fund_price 当日收盘价（仅有交易日才生成行）
    - only_missing=True 时跳过已有日期（增量补缺失，不覆盖存量）
    """
    purchases = list(
        db.scalars(
            select(models.PurchaseRecord)
            .where(
                models.PurchaseRecord.plan_id == plan_id,
                models.PurchaseRecord.fund_id == fund_id,
                models.PurchaseRecord.purchase_date <= end_date,
            )
            .order_by(models.PurchaseRecord.purchase_date)
        ).all()
    )
    prices = list(
        db.scalars(
            select(models.FundPrice)
            .where(
                models.FundPrice.fund_id == fund_id,
                models.FundPrice.trade_date >= start_date,
                models.FundPrice.trade_date <= end_date,
            )
            .order_by(models.FundPrice.trade_date)
        ).all()
    )
    if not prices:
        return 0

    existing = {
        h.trade_date: h
        for h in db.scalars(
            select(models.FundHoldingDaily).where(
                models.FundHoldingDaily.plan_id == plan_id,
                models.FundHoldingDaily.fund_id == fund_id,
            )
        ).all()
    }

    cum_shares = 0
    p_idx = 0
    count = 0
    for bar in prices:
        while p_idx < len(purchases) and purchases[p_idx].purchase_date <= bar.trade_date:
            rec = purchases[p_idx]
            sign = -1 if rec.type == "sell" else 1
            cum_shares += sign * rec.hands * rec.shares_per_hand
            p_idx += 1
        total_shares = max(0, cum_shares)
        total_hands = total_shares // HANDS
        price = bar.close_price
        equity = (Decimal(total_shares) * price).quantize(Decimal("0.01"))

        if only_missing and bar.trade_date in existing:
            continue  # 增量模式：跳过已有日期，只补缺失
        row = existing.get(bar.trade_date)
        if row is None:
            row = models.FundHoldingDaily(
                plan_id=plan_id, fund_id=fund_id, trade_date=bar.trade_date
            )
            db.add(row)
        row.total_shares = total_shares
        row.total_hands = total_hands
        row.price = price
        row.equity_amount = equity
        count += 1
    db.commit()
    return count


def list_holdings(
    db: Session,
    plan_id: int,
    fund_id: int,
    start_date: date,
    end_date: date,
) -> list[models.FundHoldingDaily]:
    return list(
        db.scalars(
            select(models.FundHoldingDaily)
            .where(
                models.FundHoldingDaily.plan_id == plan_id,
                models.FundHoldingDaily.fund_id == fund_id,
                models.FundHoldingDaily.trade_date >= start_date,
                models.FundHoldingDaily.trade_date <= end_date,
            )
            .order_by(models.FundHoldingDaily.trade_date)
        ).all()
    )


def check_missing(
    db: Session,
    plan_id: int,
    fund_id: int,
    start_date: date,
    end_date: date,
) -> tuple[int, date | None, date | None]:
    """该区间内缺失的交易日：有历史价(fund_price)但无权益流水(holding)的天数。"""
    price_dates = set(
        db.scalars(
            select(models.FundPrice.trade_date).where(
                models.FundPrice.fund_id == fund_id,
                models.FundPrice.trade_date >= start_date,
                models.FundPrice.trade_date <= end_date,
            )
        ).all()
    )
    holding_dates = set(
        db.scalars(
            select(models.FundHoldingDaily.trade_date).where(
                models.FundHoldingDaily.plan_id == plan_id,
                models.FundHoldingDaily.fund_id == fund_id,
                models.FundHoldingDaily.trade_date >= start_date,
                models.FundHoldingDaily.trade_date <= end_date,
            )
        ).all()
    )
    missing = sorted(price_dates - holding_dates)
    if not missing:
        return 0, None, None
    return len(missing), missing[0], missing[-1]
