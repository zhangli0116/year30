from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

CASH_FUND_CODE = "000000"


def generate(db: Session, plan_id: int, start_date: date, end_date: date) -> int:
    """生成每日现金流：按日历日累计（按方案拆分）。

    每日增量 = 方案周期预算入账(quarter.start_date, +budget)
             − 买入支出(−(buy total_amount + fee)，total_amount 为不含手续费的买入本金)
             ＋ 卖出回笼(+sell total_amount)
             − 卖出手续费(−sell fee)
    现金基金(000000)的记录不计入（其本身是现金，不是真实买卖）。
    对整个 [start_date, end_date] 重算（含已存在行）：日期上新增季度/购买记录后旧行会过期，
    必须覆盖而非只补缺失（否则增量生成会留下过期数据，如 Q3 预算/买入漏进现金流）。
    """
    # 现金基金 id
    cash_fund_id = db.scalar(
        select(models.Fund.id).where(models.Fund.fund_code == CASH_FUND_CODE)
    )

    # 1) 事件表：date -> 当日增量（只统计该方案）
    events: dict[date, Decimal] = {}
    # 预算入账：周期开始日
    quarters = list(
        db.scalars(
            select(models.Quarter).where(models.Quarter.plan_id == plan_id)
        ).all()
    )
    for q in quarters:
        if q.start_date:
            events[q.start_date] = events.get(q.start_date, Decimal("0")) + q.budget
    # 买卖：购买记录（排除现金基金）
    purchases = list(
        db.scalars(
            select(models.PurchaseRecord).where(
                models.PurchaseRecord.plan_id == plan_id,
                models.PurchaseRecord.purchase_date <= end_date,
            )
        ).all()
    )
    for p in purchases:
        if cash_fund_id is not None and p.fund_id == cash_fund_id:
            continue  # 现金记录本身即现金，不计入
        d = p.purchase_date
        if p.type == "sell":
            events[d] = events.get(d, Decimal("0")) + p.total_amount - p.fee
        else:
            events[d] = events.get(d, Decimal("0")) - (p.total_amount + p.fee)

    if not events:
        return 0

    # 2) 从 start_date 与最早事件日之间的更早者开始按日历日累计，只在 [start, end] 内落行
    #    事件首日之前的日历日也要落行（increment=0、cash_amount=0，首个入账前现金为 0），
    #    否则 check_missing 会把 [start_date, 事件首日) 计为缺失且永远补不上。
    day = min(start_date, min(events.keys()))
    cash = Decimal("0")
    existing = {
        r.trade_date: r
        for r in db.scalars(
            select(models.FundCashDaily).where(models.FundCashDaily.plan_id == plan_id)
        ).all()
    }
    count = 0
    while day <= end_date:
        cash += events.get(day, Decimal("0"))
        if day >= start_date:
            row = existing.get(day)
            if row is None:
                row = models.FundCashDaily(plan_id=plan_id, trade_date=day)
                db.add(row)
            row.increment = events.get(day, Decimal("0"))
            row.cash_amount = cash
            count += 1
        day += timedelta(days=1)
    db.commit()
    return count


def list_cash(
    db: Session, plan_id: int, start_date: date, end_date: date
) -> list[models.FundCashDaily]:
    return list(
        db.scalars(
            select(models.FundCashDaily)
            .where(
                models.FundCashDaily.plan_id == plan_id,
                models.FundCashDaily.trade_date >= start_date,
                models.FundCashDaily.trade_date <= end_date,
            )
            .order_by(models.FundCashDaily.trade_date)
        ).all()
    )


def check_missing(
    db: Session,
    plan_id: int,
    start_date: date,
    end_date: date,
) -> tuple[int, date | None, date | None]:
    """区间内缺失的日历日（未生成现金流的天数）。"""
    existing = set(
        db.scalars(
            select(models.FundCashDaily.trade_date).where(
                models.FundCashDaily.plan_id == plan_id,
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
