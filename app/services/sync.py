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
from app.services import price as price_service

CASH_CODE = "000000"


def sync_all(db: Session) -> dict:
    """同步所有真实基金的缺失日线并生成权益流水、现金流。幂等（重复执行插入为 0）。

    起点：该基金最早购买日（无购买则跳过）；现金流起点：最早季度开始日。
    """
    today = date.today()
    source = price_service.get_source("tencent")

    funds, _total = crud.fund.list_funds(db, page=1, page_size=100)
    real = [f for f in funds if f.fund_code != CASH_CODE]

    prices_inserted = 0
    holdings_generated = 0
    failures = 0
    earliest_start: date | None = None

    for fund in real:
        earliest = db.scalar(
            select(func.min(models.PurchaseRecord.purchase_date)).where(
                models.PurchaseRecord.fund_id == fund.id
            )
        )
        if earliest is None:
            continue  # 无持仓记录，无需历史
        start = earliest if isinstance(earliest, date) else today
        earliest_start = start if earliest_start is None else min(earliest_start, start)
        try:
            bars = source.fetch_daily(fund.fund_code, start, today)
            inserted, _existing = crud.price.upsert_bars(db, fund.id, bars, source.name)
            prices_inserted += inserted
            holdings_generated += crud.holding.generate(db, fund.id, start, today)
        except Exception as e:  # noqa: BLE001
            failures += 1
            logger.error(f"同步基金失败 {fund.fund_code}：{e}")

    # 现金流：从最早季度开始日累计
    q_start = db.scalar(select(func.min(models.Quarter.start_date)))
    cash_start = min(
        [d for d in (earliest_start, q_start) if isinstance(d, date)] or [today]
    )
    cash_generated = crud.cash.generate(db, cash_start, today)

    result = {
        "funds": len(real),
        "prices_inserted": prices_inserted,
        "holdings_generated": holdings_generated,
        "cash_generated": cash_generated,
        "failures": failures,
        "range_start": cash_start,
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
