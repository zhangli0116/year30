from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import models, schemas


def list_plans(db: Session) -> list[models.DcaPlan]:
    return list(db.scalars(select(models.DcaPlan).order_by(models.DcaPlan.id)).all())


def get_plan(db: Session, plan_id: int) -> models.DcaPlan | None:
    return db.get(models.DcaPlan, plan_id)


def get_plan_by_name(db: Session, name: str) -> models.DcaPlan | None:
    return db.scalar(select(models.DcaPlan).where(models.DcaPlan.name == name))


def _replace_funds(db: Session, plan_id: int, funds: list[schemas.PlanFundIn]) -> None:
    db.execute(delete(models.PlanFund).where(models.PlanFund.plan_id == plan_id))
    for f in funds:
        db.add(
            models.PlanFund(
                plan_id=plan_id, fund_id=f.fund_id, target_ratio=f.target_ratio
            )
        )


def validate_ratio(funds: list[schemas.PlanFundIn], cash_ratio: Decimal) -> None:
    """方案内 Σ标的 + 现金 = 100 校验，不满仓策略落地。"""
    total = sum((f.target_ratio for f in funds), Decimal("0")) + cash_ratio
    if abs(total - Decimal("100")) > Decimal("0.01"):
        raise ValueError(f"方案内 Σ标的({sum((f.target_ratio for f in funds), Decimal('0'))}) + 现金({cash_ratio}) = {total} ≠ 100")


def create_plan(db: Session, payload: schemas.PlanCreate) -> models.DcaPlan:
    validate_ratio(payload.funds, payload.cash_ratio)
    plan = models.DcaPlan(
        name=payload.name,
        start_date=payload.start_date,
        interval_days=payload.interval_days,
        tolerance_days=payload.tolerance_days,
        amount=payload.amount,
        rebalance_strategy=payload.rebalance_strategy,
        cash_ratio=payload.cash_ratio,
        active=payload.active,
    )
    db.add(plan)
    db.flush()
    _replace_funds(db, plan.id, payload.funds)
    db.commit()
    db.refresh(plan)
    return plan


def update_plan(
    db: Session, plan: models.DcaPlan, payload: schemas.PlanUpdate
) -> models.DcaPlan:
    data = payload.model_dump(exclude_unset=True)
    data.pop("funds", None)  # funds 用 payload.funds（Pydantic 对象），model_dump 出来的是 dict
    if payload.funds is not None:
        validate_ratio(payload.funds, data.get("cash_ratio", plan.cash_ratio))
    for field, value in data.items():
        setattr(plan, field, value)
    if payload.funds is not None:
        _replace_funds(db, plan.id, payload.funds)
    db.commit()
    db.refresh(plan)
    return plan


def delete_plan(db: Session, plan: models.DcaPlan) -> bool:
    """删除方案；已有 quarter/purchase 归属时拒绝（防级联误删数据）。"""
    has_quarter = db.scalar(
        select(models.Quarter.id).where(models.Quarter.plan_id == plan.id).limit(1)
    )
    has_purchase = db.scalar(
        select(models.PurchaseRecord.id).where(models.PurchaseRecord.plan_id == plan.id).limit(1)
    )
    if has_quarter or has_purchase:
        return False
    db.delete(plan)
    db.commit()
    return True


def next_due(plan: models.DcaPlan, today=None) -> dict | None:
    """下次定投窗口：以 start_date 为基准，第 k 期计划日 = start + k×interval_days，窗口 = 计划日 ± tolerance。

    status: upcoming(未到) / due(窗口内，该投了) / overdue(已过窗口，逾期)。
    """
    if not plan.start_date or plan.interval_days <= 0:
        return None

    today = today or date.today()
    s = plan.start_date
    iv = plan.interval_days
    tol = plan.tolerance_days
    days = (today - s).days
    if days < 0:
        k = 0  # 还没到起始日期
    else:
        k = (days + iv) // iv  # 下一个 >= today 的期数
    scheduled = s + timedelta(days=k * iv)
    window_start = scheduled - timedelta(days=tol)
    window_end = scheduled + timedelta(days=tol)
    status = "due" if window_start <= today <= window_end else (
        "overdue" if today > window_end else "upcoming"
    )
    return {
        "scheduled": scheduled,
        "window_start": window_start,
        "window_end": window_end,
        "status": status,
    }


def plan_out(db: Session, plan: models.DcaPlan) -> dict:
    """组装 PlanOut：方案 + 标的明细（含基金代码/名称）+ 下次定投窗口。"""
    from app.crud.fund import get_fund

    funds = []
    for pf in db.scalars(
        select(models.PlanFund).where(models.PlanFund.plan_id == plan.id).order_by(models.PlanFund.fund_id)
    ).all():
        fund = get_fund(db, pf.fund_id)
        if fund is None:
            continue
        funds.append(
            {
                "fund_id": pf.fund_id,
                "fund_code": fund.fund_code,
                "fund_name": fund.fund_name,
                "target_ratio": pf.target_ratio,
            }
        )
    return {
        "id": plan.id,
        "name": plan.name,
        "start_date": plan.start_date,
        "interval_days": plan.interval_days,
        "tolerance_days": plan.tolerance_days,
        "amount": plan.amount,
        "rebalance_strategy": plan.rebalance_strategy,
        "cash_ratio": plan.cash_ratio,
        "active": plan.active,
        "next_due": next_due(plan),
        "funds": funds,
    }
