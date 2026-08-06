from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

CASH_FUND_CODE = "000000"


def generate(db: Session, start_date: date, end_date: date) -> int:
    """生成每日现金流：按日历日累计。

    每日增量 = 季度预算入账(quarter.start_date, +budget)
             − 买入支出(−buy total_amount，已含手续费)
             ＋ 卖出回笼(+sell total_amount)
             − 卖出手续费(−sell fee)
    现金基金(000000)的记录不计入（其本身是现金，不是真实买卖）。
    """
    # 现金基金 id
    cash_fund_id = db.scalar(
        select(models.Fund.id).where(models.Fund.fund_code == CASH_FUND_CODE)
    )

    # 1) 事件表：date -> 当日增量
    events: dict[date, Decimal] = {}
    # 预算入账：季度开始日
    quarters = list(db.scalars(select(models.Quarter)).all())
    for q in quarters:
        if q.start_date:
            events[q.start_date] = events.get(q.start_date, Decimal("0")) + q.budget
    # 买卖：购买记录（排除现金基金）
    purchases = list(
        db.scalars(
            select(models.PurchaseRecord)
            .where(models.PurchaseRecord.purchase_date <= end_date)
        ).all()
    )
    for p in purchases:
        if cash_fund_id is not None and p.fund_id == cash_fund_id:
            continue  # 现金记录本身即现金，不计入
        d = p.purchase_date
        if p.type == "sell":
            events[d] = events.get(d, Decimal("0")) + p.total_amount - p.fee
        else:
            events[d] = events.get(d, Decimal("0")) - p.total_amount

    if not events:
        return 0

    # 2) 从最早事件日开始按日历日累计，只在 [start, end] 内落行
    day = min(events.keys())
    cash = Decimal("0")
    existing = {
        r.trade_date: r
        for r in db.scalars(select(models.FundCashDaily)).all()
    }
    count = 0
    while day <= end_date:
        cash += events.get(day, Decimal("0"))
        if day >= start_date:
            row = existing.get(day)
            if row is None:
                row = models.FundCashDaily(trade_date=day)
                db.add(row)
            row.increment = events.get(day, Decimal("0"))
            row.cash_amount = cash
            count += 1
        day += timedelta(days=1)
    db.commit()
    return count


def list_cash(db: Session, start_date: date, end_date: date) -> list[models.FundCashDaily]:
    return list(
        db.scalars(
            select(models.FundCashDaily)
            .where(
                models.FundCashDaily.trade_date >= start_date,
                models.FundCashDaily.trade_date <= end_date,
            )
            .order_by(models.FundCashDaily.trade_date)
        ).all()
    )


def check_missing(
    db: Session,
    start_date: date,
    end_date: date,
) -> tuple[int, date | None, date | None]:
    """区间内缺失的日历日（未生成现金流的天数）。"""
    existing = set(
        db.scalars(
            select(models.FundCashDaily.trade_date).where(
                models.FundCashDaily.trade_date >= start_date,
                models.FundCashDaily.trade_date <= end_date,
            )
        ).all()
    )
    missing: list[date] = []
    day = start_date
    while day <= end_date:
        if day not in existing:
            missing.append(day)
        day += timedelta(days=1)
    if not missing:
        return 0, None, None
    return len(missing), missing[0], missing[-1]
