"""一键同步全部行情：历史日线 → 每日权益流水 → 每日现金流量。

供三种触发方式共用：
    1. 前端 POST /api/v1/sync/all
    2. 应用内 APScheduler 定时（run_scheduled_sync）
    3. scripts/sync_daily.py 独立脚本（Windows 任务计划）
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import crud, models
from app.logger import logger
from app.services import datasource

CASH_CODE = "000000"


def sync_all(db: Session) -> dict:
    """同步所有 active 方案的缺失日线并生成权益流水、现金流。幂等（重复执行插入为 0）。

    遍历每个 active 方案：同步该方案内基金缺失日线 → 生成该方案权益流水
    （holding.generate 带 plan_id）→ 生成该方案现金流（cash.generate 带 plan_id）。
    起点：该基金在该方案下最早购买日（无购买则跳过）；现金流起点：该方案最早季度开始日。
    """
    today = date.today()
    provider = datasource.get_provider(db)  # 跟随「当前数据源」（设置页切换）

    plans = [p for p in crud.plan.list_plans(db) if p.active]
    if not plans:
        return {
            "funds": 0,
            "prices_inserted": 0,
            "holdings_generated": 0,
            "cash_generated": 0,
            "failures": 0,
            "range_start": None,
            "range_end": today,
        }

    cash_fund_id = db.scalar(
        select(models.Fund.id).where(models.Fund.fund_code == CASH_CODE)
    )
    prices_inserted = 0
    holdings_generated = 0
    failures = 0
    cash_generated = 0
    range_start: date | None = None
    seen_funds: set[int] = set()

    for plan in plans:
        # 该方案下的真实基金：plan_fund 配置 ∪ 有购买记录的基金（排除现金基金）
        fund_ids = set(
            db.scalars(
                select(models.PlanFund.fund_id).where(models.PlanFund.plan_id == plan.id)
            ).all()
        )
        fund_ids |= set(
            db.scalars(
                select(models.PurchaseRecord.fund_id).where(
                    models.PurchaseRecord.plan_id == plan.id
                )
            ).all()
        )
        if cash_fund_id is not None:
            fund_ids.discard(cash_fund_id)

        plan_earliest: date | None = None
        for fund_id in fund_ids:
            earliest = db.scalar(
                select(func.min(models.PurchaseRecord.purchase_date)).where(
                    models.PurchaseRecord.plan_id == plan.id,
                    models.PurchaseRecord.fund_id == fund_id,
                )
            )
            if earliest is None:
                continue  # 该方案下无持仓记录，无需历史
            start = earliest if isinstance(earliest, date) else today
            plan_earliest = start if plan_earliest is None else min(plan_earliest, start)
            fund = db.get(models.Fund, fund_id)
            if fund is None:
                continue
            seen_funds.add(fund.id)
            try:
                symbol = datasource.fund_symbol(fund.exchange, fund.fund_code)
                bars = provider.fetch_daily(symbol, start, today)
                inserted, _existing = crud.price.upsert_bars(db, fund.id, bars, provider.name)
                prices_inserted += inserted
                # 重算 [start, today] 权益流水（含已存在行，避免新增购买后旧行过期）
                holdings_generated += crud.holding.generate(
                    db, plan.id, fund.id, start, today
                )
            except Exception as e:  # noqa: BLE001
                failures += 1
                logger.error(f"同步方案{plan.id}基金 {fund.fund_code} 失败：{e}")

        # 现金流：从该方案最早季度开始日累计
        q_start = db.scalar(
            select(func.min(models.Quarter.start_date)).where(
                models.Quarter.plan_id == plan.id
            )
        )
        cash_start = min(
            [d for d in (plan_earliest, q_start) if isinstance(d, date)] or [today]
        )
        # 重算 [cash_start, today] 现金流（含已存在行，避免新增季度/购买后旧行过期）
        cash_generated += crud.cash.generate(db, plan.id, cash_start, today)
        if range_start is None or cash_start < range_start:
            range_start = cash_start

    result = {
        "funds": len(seen_funds),
        "prices_inserted": prices_inserted,
        "holdings_generated": holdings_generated,
        "cash_generated": cash_generated,
        "failures": failures,
        "range_start": range_start,
        "range_end": today,
    }
    logger.info(f"一键同步完成：{result}")
    return result


def run_scheduled_sync() -> None:
    """供 APScheduler / 独立入口调用：自建会话执行一次全量同步。"""
    from app.database import SessionLocal

    try:
        with SessionLocal() as db:
            result = sync_all(db)
        logger.info(f"定时同步完成：{result}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"定时同步失败：{e}")
