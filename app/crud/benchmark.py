"""基准指数 CRUD：列表 / 查询 / 幂等写入基准日线。"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


def list_benchmarks(db: Session, active_only: bool = True) -> list[models.Benchmark]:
    stmt = select(models.Benchmark).order_by(models.Benchmark.id)
    if active_only:
        stmt = stmt.where(models.Benchmark.active.is_(True))
    return list(db.scalars(stmt).all())


def get_benchmark(db: Session, benchmark_id: int) -> models.Benchmark | None:
    return db.get(models.Benchmark, benchmark_id)


def get_by_symbol(db: Session, symbol: str) -> models.Benchmark | None:
    return db.scalar(select(models.Benchmark).where(models.Benchmark.symbol == symbol))


def existing_dates(db: Session, benchmark_id: int) -> set[date]:
    return set(
        db.scalars(
            select(models.BenchmarkPrice.trade_date).where(
                models.BenchmarkPrice.benchmark_id == benchmark_id
            )
        ).all()
    )


def upsert_bars(
    db: Session, benchmark_id: int, rows: list[tuple[date, Decimal]]
) -> tuple[int, int]:
    """写入基准日线；(日期, 收盘) 列表，已存在的日期跳过。返回 (插入, 已有)。"""
    existing = existing_dates(db, benchmark_id)
    inserted = 0
    existing_count = 0
    for td, close in rows:
        if td in existing:
            existing_count += 1
            continue
        db.add(
            models.BenchmarkPrice(
                benchmark_id=benchmark_id, trade_date=td, close_price=close
            )
        )
        inserted += 1
    db.commit()
    return inserted, existing_count


def list_prices(
    db: Session, benchmark_id: int, start_date: date, end_date: date
) -> list[models.BenchmarkPrice]:
    """查询某基准在日期区间的日线（按日期升序）。"""
    return list(
        db.scalars(
            select(models.BenchmarkPrice)
            .where(
                models.BenchmarkPrice.benchmark_id == benchmark_id,
                models.BenchmarkPrice.trade_date >= start_date,
                models.BenchmarkPrice.trade_date <= end_date,
            )
            .order_by(models.BenchmarkPrice.trade_date)
        ).all()
    )
