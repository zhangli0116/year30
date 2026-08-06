from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app import models, schemas


def get_quarter(db: Session, quarter_id: int) -> models.Quarter | None:
    return db.get(models.Quarter, quarter_id)


def get_quarter_with_purchases(db: Session, quarter_id: int) -> models.Quarter | None:
    q = db.get(models.Quarter, quarter_id)
    if q is None:
        return None
    # 触发生成属性加载，避免懒加载在序列化时出错
    _ = q.purchases
    return q


def get_quarter_by_period(db: Session, period: str) -> models.Quarter | None:
    return db.scalar(select(models.Quarter).where(models.Quarter.period == period))


def list_quarters(db: Session) -> list[models.Quarter]:
    return list(
        db.scalars(
            select(models.Quarter).order_by(models.Quarter.period.desc())
        ).all()
    )


def create_quarter(db: Session, payload: schemas.QuarterCreate) -> models.Quarter:
    quarter = models.Quarter(
        period=payload.period,
        start_date=payload.start_date,
        end_date=payload.end_date,
        budget=payload.budget,
        equity_amount=Decimal("0.00"),
        total_fee=Decimal("0.00"),
        cash_amount=payload.budget,  # 初始时现金 = 预算（尚未录入购买记录）
        note=payload.note,
    )
    db.add(quarter)
    db.commit()
    db.refresh(quarter)
    return quarter


def update_quarter(
    db: Session, quarter: models.Quarter, payload: schemas.QuarterUpdate
) -> models.Quarter:
    """仅允许改 budget；改预算后 cash_amount 自动重算（= budget − equity − total_fee）。"""
    budget_changed = "budget" in payload.model_dump(exclude_unset=True)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(quarter, field, value)
    if budget_changed:
        quarter.cash_amount = quarter.budget - quarter.equity_amount - quarter.total_fee
    db.commit()
    db.refresh(quarter)
    return quarter


def recalc_quarter(db: Session, quarter_id: int) -> models.Quarter | None:
    """按该季度下的购买记录重算（现金基金记录不计入）：
    equity_amount = Σ(本金, 不含手续费)；total_fee = Σ手续费；cash_amount = budget − equity − total_fee。"""
    quarter = get_quarter(db, quarter_id)
    if quarter is None:
        return None
    cash_fund_id = db.scalar(
        select(models.Fund.id).where(models.Fund.fund_code == "000000")
    )
    # equity = Σ买入本金 − Σ卖出额；total_fee = Σ全部手续费
    stmt = select(
        func.coalesce(
            func.sum(
                case(
                    (
                        models.PurchaseRecord.type == "buy",
                        models.PurchaseRecord.total_amount
                        - func.coalesce(models.PurchaseRecord.fee, 0),
                    ),
                    else_=0,
                )
            ),
            0,
        ),
        func.coalesce(
            func.sum(
                case(
                    (models.PurchaseRecord.type == "sell", models.PurchaseRecord.total_amount),
                    else_=0,
                )
            ),
            0,
        ),
        func.coalesce(func.sum(models.PurchaseRecord.fee), 0),
    ).where(models.PurchaseRecord.quarter_id == quarter_id)
    if cash_fund_id is not None:
        stmt = stmt.where(models.PurchaseRecord.fund_id != cash_fund_id)
    buy_principal, sell_proceeds, total_fee = db.execute(stmt).one()
    buy_principal = Decimal(str(buy_principal))
    sell_proceeds = Decimal(str(sell_proceeds))
    total_fee = Decimal(str(total_fee))
    equity = buy_principal - sell_proceeds
    quarter.equity_amount = equity
    quarter.total_fee = total_fee
    quarter.cash_amount = quarter.budget - equity - total_fee
    db.commit()
    db.refresh(quarter)
    return quarter


def delete_quarter(db: Session, quarter: models.Quarter) -> None:
    db.delete(quarter)
    db.commit()
