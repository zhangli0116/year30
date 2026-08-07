"""统一价格访问层：屏蔽 fund_price（交易所 OHLC）与 fund_nav（场外净值）的差异。

按 `fund.fund_type` 分支取数：
    etf → fund_price.close_price
    otc → fund_nav.unit_nav
所有消费方（价格路由、持仓流水、XIRR、回测、基准代理、一键同步）
统一走这里的 `series / existing_dates / latest`，避免各处重复判断类型。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.price import FUND_TYPE_ETF, FUND_TYPE_OTC


def fund_type(db: Session, fund_id: int) -> str:
    """读取标的类型；未知/缺省回退 etf。"""
    fund = db.get(models.Fund, fund_id)
    return getattr(fund, "fund_type", None) or FUND_TYPE_ETF


def _is_otc(db: Session, fund_id: int) -> bool:
    return fund_type(db, fund_id) == FUND_TYPE_OTC


def series(
    db: Session,
    fund_id: int,
    start_date: date,
    end_date: date,
) -> list[tuple[date, Decimal]]:
    """某基金在 [start, end] 的价格序列 [(trade_date, price)] 升序。
    单位净值/收盘价统一作为 price 返回。"""
    if _is_otc(db, fund_id):
        rows = db.execute(
            select(models.FundNav.trade_date, models.FundNav.unit_nav)
            .where(
                models.FundNav.fund_id == fund_id,
                models.FundNav.trade_date >= start_date,
                models.FundNav.trade_date <= end_date,
            )
            .order_by(models.FundNav.trade_date)
        ).all()
        return [(td, Decimal(str(p))) for td, p in rows if p is not None]
    rows = db.execute(
        select(models.FundPrice.trade_date, models.FundPrice.close_price)
        .where(
            models.FundPrice.fund_id == fund_id,
            models.FundPrice.trade_date >= start_date,
            models.FundPrice.trade_date <= end_date,
        )
        .order_by(models.FundPrice.trade_date)
    ).all()
    return [(td, Decimal(str(p))) for td, p in rows if p is not None]


def existing_dates(db: Session, fund_id: int) -> set[date]:
    """该基金全部已有价格日期（按类型读对应表）。"""
    if _is_otc(db, fund_id):
        return set(
            db.scalars(
                select(models.FundNav.trade_date).where(models.FundNav.fund_id == fund_id)
            ).all()
        )
    return set(
        db.scalars(
            select(models.FundPrice.trade_date).where(models.FundPrice.fund_id == fund_id)
        ).all()
    )


def latest(db: Session, fund_id: int) -> Decimal | None:
    """最新价格（收盘价/单位净值）；无数据返回 None。"""
    rows = series(db, fund_id, date.min, date.max)
    return rows[-1][1] if rows else None
