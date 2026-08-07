from decimal import Decimal

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas


def get_fund(db: Session, fund_id: int) -> models.Fund | None:
    return db.get(models.Fund, fund_id)


def get_fund_by_code(db: Session, fund_code: str) -> models.Fund | None:
    return db.scalar(select(models.Fund).where(models.Fund.fund_code == fund_code))


def list_funds(
    db: Session,
    page: int,
    page_size: int,
    keyword: str | None = None,
) -> tuple[list[models.Fund], int]:
    stmt = select(models.Fund)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                models.Fund.fund_code.like(like),
                models.Fund.fund_name.like(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(models.Fund.fund_code)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def create_fund(db: Session, payload: schemas.FundCreate) -> models.Fund:
    fund = models.Fund(**payload.model_dump())
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


def update_fund(
    db: Session, fund: models.Fund, payload: schemas.FundUpdate
) -> models.Fund:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(fund, field, value)
    db.commit()
    db.refresh(fund)
    return fund


def delete_fund(db: Session, fund: models.Fund) -> None:
    db.delete(fund)
    db.commit()


def count_purchases(db: Session, fund_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(models.PurchaseRecord)
            .where(models.PurchaseRecord.fund_id == fund_id)
        )
        or 0
    )


def get_fund_with_purchases(db: Session, fund_id: int) -> models.Fund | None:
    """查询基金并预加载其全部购买记录（按日期升序）。"""
    fund = db.scalar(
        select(models.Fund)
        .options(selectinload(models.Fund.purchases))
        .where(models.Fund.id == fund_id)
    )
    if fund is not None:
        fund.purchases.sort(key=lambda p: (p.purchase_date, p.id))
    return fund


def summarize_funds(db: Session, plan_id: int | None = None) -> dict:
    """按方案汇总基金统计，并计算配置比例。

    plan_id 提供时：
        - 目标比例取 plan_fund（方案内 Σ+现金=100）
        - 现金目标比例取 plan.cash_ratio（显式，落实不满仓）
        - 份额/成本只统计该方案下的购买记录（基金可跨方案，按方案拆分）
    未提供 plan_id 时不返回目标比例（目标只存在方案内）。
    """
    # 方案目标配置
    plan = db.get(models.DcaPlan, plan_id) if plan_id else None
    target_map: dict[int, Decimal] = {}
    plan_cash_ratio: Decimal | None = None
    if plan is not None:
        for pf in db.scalars(
            select(models.PlanFund).where(models.PlanFund.plan_id == plan.id)
        ).all():
            target_map[pf.fund_id] = pf.target_ratio
        plan_cash_ratio = plan.cash_ratio

    join_cond = models.PurchaseRecord.fund_id == models.Fund.id
    if plan is not None:
        join_cond = join_cond & (models.PurchaseRecord.plan_id == plan.id)

    rows = db.execute(
        select(
            models.Fund.id.label("fund_id"),
            models.Fund.fund_code,
            models.Fund.fund_name,
            func.count(models.PurchaseRecord.id).label("buy_count"),
            # 份额 = 买入 − 卖出（卖出为负）
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
            ).label("total_shares"),
            # 累计投入 = 买入本金 − 卖出额（total_amount 统一为不含手续费的本金/成交额）
            func.sum(
                case(
                    (
                        models.PurchaseRecord.type == "sell",
                        -models.PurchaseRecord.total_amount,
                    ),
                    else_=models.PurchaseRecord.total_amount,
                )
            ).label("total_cost"),
        )
        .outerjoin(models.PurchaseRecord, join_cond)
        .group_by(models.Fund.id, models.Fund.fund_code, models.Fund.fund_name)
        # 持仓汇总只展示实际买过的基金；无购买记录的基金（如回测/基准用标的）不出现
        .having(func.count(models.PurchaseRecord.id) > 0)
        .order_by(models.Fund.fund_code)
    ).all()

    total_invested = Decimal("0")
    invested_target = Decimal("0")
    has_target = False

    funds = []
    for row in rows:
        total_shares = int(row.total_shares or 0)
        total_cost = row.total_cost or Decimal("0")
        total_invested += total_cost
        # 目标比例：只取方案内 plan_fund（基金自身不再存目标比例）
        target = target_map.get(row.fund_id)
        if target is not None:
            has_target = True
            invested_target += target
        avg_cost = None
        if total_shares:
            avg_cost = (total_cost / total_shares).quantize(Decimal("0.0001"))
        funds.append(
            {
                "fund_id": row.fund_id,
                "fund_code": row.fund_code,
                "fund_name": row.fund_name,
                "buy_count": row.buy_count,
                "total_shares": total_shares,
                "total_cost": total_cost,
                "avg_cost": avg_cost,
                "target_ratio": target,
                "real_ratio": None,
            }
        )

    cash_ratio = None
    total_capital = None
    if plan_cash_ratio is not None:
        cash_ratio = plan_cash_ratio.quantize(Decimal("0.01"))
        invested_target = (Decimal("100") - plan_cash_ratio).quantize(Decimal("0.01"))
    elif has_target and invested_target > 0:
        if invested_target < Decimal("100"):
            cash_ratio = max(Decimal("0"), Decimal("100") - invested_target).quantize(
                Decimal("0.01")
            )
    if invested_target > 0 and total_invested > 0:
        raw_capital = total_invested / (invested_target / Decimal("100"))
        total_capital = raw_capital.quantize(Decimal("0.01"))
        for f in funds:
            if f["total_cost"] > 0:
                f["real_ratio"] = (
                    f["total_cost"] / raw_capital * Decimal("100")
                ).quantize(Decimal("0.01"))

    return {
        "funds": funds,
        "total_invested": total_invested.quantize(Decimal("0.01")),
        "total_capital": total_capital,
        "cash_ratio": cash_ratio,
    }
