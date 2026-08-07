"""场外基金净值 CRUD（fund_nav 表）。模式对齐 crud/price.py。"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


def list_navs(
    db: Session,
    fund_id: int,
    start_date: date,
    end_date: date,
) -> list[models.FundNav]:
    """查询某场外基金在日期区间的净值（按日期升序）。"""
    return list(
        db.scalars(
            select(models.FundNav)
            .where(
                models.FundNav.fund_id == fund_id,
                models.FundNav.trade_date >= start_date,
                models.FundNav.trade_date <= end_date,
            )
            .order_by(models.FundNav.trade_date)
        ).all()
    )


def existing_dates(db: Session, fund_id: int) -> set[date]:
    return set(
        db.scalars(
            select(models.FundNav.trade_date).where(models.FundNav.fund_id == fund_id)
        ).all()
    )


def upsert_navs(
    db: Session,
    fund_id: int,
    navs: list,
    source: str,
) -> tuple[int, int]:
    """写入净值；已存在的日期跳过。返回 (插入条数, 已有条数)。"""
    existing = existing_dates(db, fund_id)
    inserted = 0
    existing_count = 0
    for b in navs:
        if b.trade_date in existing:
            existing_count += 1
            continue
        db.add(
            models.FundNav(
                fund_id=fund_id,
                trade_date=b.trade_date,
                unit_nav=Decimal(str(b.unit_nav)) if b.unit_nav is not None else Decimal("0"),
                accum_nav=Decimal(str(b.accum_nav)) if b.accum_nav is not None else None,
                source=source,
            )
        )
        inserted += 1
    db.commit()
    return inserted, existing_count
