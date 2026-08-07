"""方案变动后的统一对账：把季度汇总、每日现金流、每日权益流水一次算齐。

购买记录 / 季度 的增删改（含计算器一键录入、临时再平衡、购买记录页）都走
purchase/quarter 的 crud 入口，这些入口统一调用 `reconcile_plan(db, plan_id)`，
避免「只重算季度、每日现金流/权益流水过期」的多套零散逻辑。

底层复用同一套 crud 生成函数（cash.generate / holding.generate / quarter.recalc_quarter），
与「每日现金流量」「每日权益流水」「同步全部行情」页面走的是同一实现，不重复开发。
"""
from datetime import date

from sqlalchemy import func, select

from app import models
from app.crud.cash import generate as generate_cash
from app.crud.holding import generate as generate_holding
from app.crud.quarter import list_quarters, recalc_quarter


def reconcile_plan(db, plan_id: int, today: date | None = None) -> None:
    """方案相关数据变动后，把该方案所有派生数据一次算齐：

    1) 季度汇总（equity_amount / total_fee / cash_amount）—— 重算全部季度
    2) 每日现金流 fund_cash_daily —— 最早季度开始日 → 今天
    3) 每日权益流水 fund_holding_daily —— 每只有购买的基金，最早购买日 → 今天
    """
    today = today or date.today()

    # 1) 季度汇总
    for q in list_quarters(db, plan_id):
        recalc_quarter(db, q.id)

    # 2) 每日现金流
    q_start = db.scalar(
        select(func.min(models.Quarter.start_date)).where(
            models.Quarter.plan_id == plan_id
        )
    )
    if isinstance(q_start, date):
        generate_cash(db, plan_id, q_start, today)

    # 3) 每日权益流水
    fund_ids = set(
        db.scalars(
            select(models.PurchaseRecord.fund_id).where(
                models.PurchaseRecord.plan_id == plan_id
            )
        ).all()
    )
    for fid in fund_ids:
        start = db.scalar(
            select(func.min(models.PurchaseRecord.purchase_date)).where(
                models.PurchaseRecord.plan_id == plan_id,
                models.PurchaseRecord.fund_id == fid,
            )
        )
        if isinstance(start, date):
            generate_holding(db, plan_id, fid, start, today)
