from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


def list_prices(
    db: Session,
    fund_id: int,
    start_date: date,
    end_date: date,
) -> list[models.FundPrice]:
    """查询某基金在日期区间的日线（按日期升序）。"""
    return list(
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


def existing_dates(db: Session, fund_id: int) -> set[date]:
    return set(
        db.scalars(
            select(models.FundPrice.trade_date).where(models.FundPrice.fund_id == fund_id)
        ).all()
    )


def upsert_bars(
    db: Session,
    fund_id: int,
    bars: list,
    source: str,
) -> tuple[int, int]:
    """写入日线；已存在的日期跳过。返回 (插入条数, 已有条数)。"""
    existing = existing_dates(db, fund_id)
    inserted = 0
    existing_count = 0
    for b in bars:
        if b.trade_date in existing:
            existing_count += 1
            continue
        db.add(
            models.FundPrice(
                fund_id=fund_id,
                trade_date=b.trade_date,
                open_price=Decimal(str(b.open)) if b.open is not None else None,
                high_price=Decimal(str(b.high)) if b.high is not None else None,
                low_price=Decimal(str(b.low)) if b.low is not None else None,
                close_price=Decimal(str(b.close)) if b.close is not None else Decimal("0"),
                volume=b.volume,
                source=source,
            )
        )
        inserted += 1
    db.commit()
    return inserted, existing_count


def delete_prices(db: Session, fund_id: int) -> int:
    rows = db.scalars(
        select(models.FundPrice).where(models.FundPrice.fund_id == fund_id)
    ).all()
    for r in rows:
        db.delete(r)
    db.commit()
    return len(rows)
