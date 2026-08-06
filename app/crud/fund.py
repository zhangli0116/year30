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


def summarize_funds(db: Session) -> dict:
    """按基金汇总统计，并计算配置比例。

    现金目标比例 = 100 − 各基金目标比例之和；
    总资金 = 累计投入 ÷ (目标占比之和 ÷ 100)；
    真实比例 = 基金累计投入 ÷ 总资金 × 100。
    """
    rows = db.execute(
        select(
            models.Fund.id.label("fund_id"),
            models.Fund.fund_code,
            models.Fund.fund_name,
            models.Fund.target_ratio,
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
            # 累计投入 = 买入本金(不含手续费) − 卖出额
            func.sum(
                case(
                    (
                        models.PurchaseRecord.type == "sell",
                        -models.PurchaseRecord.total_amount,
                    ),
                    else_=models.PurchaseRecord.total_amount
                    - func.coalesce(models.PurchaseRecord.fee, 0),
                )
            ).label("total_cost"),
        )
        .outerjoin(
            models.PurchaseRecord,
            models.PurchaseRecord.fund_id == models.Fund.id,
        )
        .group_by(
            models.Fund.id,
            models.Fund.fund_code,
            models.Fund.fund_name,
            models.Fund.target_ratio,
        )
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
        if row.target_ratio is not None:
            has_target = True
            invested_target += row.target_ratio
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
                "target_ratio": row.target_ratio,
                "real_ratio": None,
            }
        )

    cash_ratio = None
    total_capital = None
    if has_target and invested_target > 0:
        # 目标比例之和达到 100% 时，全部资金由基金（含现金基金）表示，无独立现金桶
        if invested_target < Decimal("100"):
            cash_ratio = max(Decimal("0"), Decimal("100") - invested_target).quantize(
                Decimal("0.01")
            )
        if total_invested > 0:
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
