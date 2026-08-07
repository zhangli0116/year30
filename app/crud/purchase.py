from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.services.reconcile import reconcile_plan


def get_purchase(db: Session, purchase_id: int) -> models.PurchaseRecord | None:
    return db.get(models.PurchaseRecord, purchase_id)


def list_purchases(
    db: Session,
    page: int,
    page_size: int,
    fund_id: int | None = None,
    plan_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    exclude_cash: bool = True,
) -> tuple[list[models.PurchaseRecord], int]:
    """购买记录列表；plan_id 提供时按方案过滤；默认排除现金基金(000000)的记录，现金已由 quarter 表承载。"""
    stmt = select(models.PurchaseRecord)
    if plan_id is not None:
        stmt = stmt.where(models.PurchaseRecord.plan_id == plan_id)
    if exclude_cash:
        cash_fund_id = db.scalar(
            select(models.Fund.id).where(models.Fund.fund_code == "000000")
        )
        if cash_fund_id is not None:
            stmt = stmt.where(models.PurchaseRecord.fund_id != cash_fund_id)
    if fund_id is not None:
        stmt = stmt.where(models.PurchaseRecord.fund_id == fund_id)
    if start_date is not None:
        stmt = stmt.where(models.PurchaseRecord.purchase_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(models.PurchaseRecord.purchase_date <= end_date)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(
            models.PurchaseRecord.purchase_date.desc(),
            models.PurchaseRecord.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


# 手续费费率默认：买入 0.03%、卖出 0.07%；不足 5 元按 5 元
DEFAULT_FEE_RATE = Decimal("0.03")
DEFAULT_SELL_FEE_RATE = Decimal("0.07")
MIN_FEE = Decimal("5.00")


def _calc_fee(
    principal: Decimal,
    fee: Decimal | None,
    fee_rate: Decimal | None,
    is_sell: bool = False,
) -> Decimal:
    """手续费 = max(5, 金额 × 费率%)；fee 明确传入时直接用。卖出默认 0.07%。"""
    if fee is not None:
        return fee.quantize(Decimal("0.01"))
    rate = fee_rate if fee_rate is not None else (
        DEFAULT_SELL_FEE_RATE if is_sell else DEFAULT_FEE_RATE
    )
    return max(MIN_FEE, (principal * rate / Decimal("100")).quantize(Decimal("0.01")))


def _principal(data: dict) -> Decimal:
    return data["hands"] * data["shares_per_hand"] * data["price"]


def _total_amount(data: dict, principal: Decimal, fee: Decimal) -> Decimal:
    """金额（统一口径）：买/卖 total_amount 均为本金/成交额，不含手续费；手续费单独存 fee。"""
    return principal.quantize(Decimal("0.01"))


def create_purchase(
    db: Session, payload: schemas.PurchaseCreate
) -> models.PurchaseRecord:
    data = payload.model_dump()
    principal = _principal(data)
    data["fee"] = _calc_fee(
        principal, data.get("fee"), data.get("fee_rate"), is_sell=(data.get("type") == "sell")
    )
    data.pop("fee_rate", None)
    if data["total_amount"] is None:
        data["total_amount"] = _total_amount(data, principal, data["fee"])
    record = models.PurchaseRecord(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    # 统一对账：季度 + 每日现金流 + 每日权益流水
    reconcile_plan(db, record.plan_id)
    return record


def create_purchases(
    db: Session, items: list[schemas.PurchaseCreate]
) -> list[models.PurchaseRecord]:
    """批量创建购买记录（可含卖出），单事务提交；写完后重算涉及季度的权益/现金。"""
    records: list[models.PurchaseRecord] = []
    for payload in items:
        data = payload.model_dump()
        principal = _principal(data)
        data["fee"] = _calc_fee(
            principal, data.get("fee"), data.get("fee_rate"), is_sell=(data.get("type") == "sell")
        )
        data.pop("fee_rate", None)
        if data["total_amount"] is None:
            data["total_amount"] = _total_amount(data, principal, data["fee"])
        records.append(models.PurchaseRecord(**data))
    db.add_all(records)
    db.commit()
    for r in records:
        db.refresh(r)
    # 统一对账：涉及的方案各重算一次（季度 + 每日现金流 + 每日权益流水）
    for plan_id in {r.plan_id for r in records}:
        reconcile_plan(db, plan_id)
    return records


def update_purchase(
    db: Session,
    record: models.PurchaseRecord,
    payload: schemas.PurchaseUpdate,
) -> models.PurchaseRecord:
    old_plan = record.plan_id
    data = payload.model_dump(exclude_unset=True)
    # 传入 fee_rate 时重算手续费；fee 明确传入则直接用
    if "fee_rate" in data:
        new_principal = (
            data.get("hands", record.hands)
            * data.get("shares_per_hand", record.shares_per_hand)
            * data.get("price", record.price)
        )
        eff_type = data.get("type", record.type)
        data["fee"] = _calc_fee(
            new_principal, data.get("fee"), data.pop("fee_rate"), is_sell=(eff_type == "sell")
        )
    for field, value in data.items():
        setattr(record, field, value)
    # 未显式传 total_amount 时，按 买卖类型 重算
    if "total_amount" not in data:
        principal = record.hands * record.shares_per_hand * record.price
        record.total_amount = _total_amount(
            {"type": record.type}, principal, record.fee
        )
    db.commit()
    db.refresh(record)
    # 新旧方案都统一对账（跨方案移动时）
    for pid in {old_plan, record.plan_id}:
        reconcile_plan(db, pid)
    return record


def delete_purchase(db: Session, record: models.PurchaseRecord) -> None:
    plan = record.plan_id
    db.delete(record)
    db.commit()
    reconcile_plan(db, plan)
