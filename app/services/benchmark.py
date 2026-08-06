"""基准指数服务：默认种子、按 symbol 拉取日线、幂等同步。

取数路径：
    直连型（fund_id 为 NULL）：调「当前数据源」DataProvider.fetch_daily(benchmark.symbol)
        （腾讯走 fqkline/get，指数返回 day 键无复权原始点位；新浪走 getKLineData）。
    代理型（fund_id 非空）：从 fund_price 按该基金拷贝收盘价
        （如 标普500→513500ETF，人民币口径与持仓一致，零外部接口）。
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud, models
from app.services import datasource

DEFAULT_BENCHMARKS = [
    {"symbol": "sh000300", "name": "沪深300", "fund_code": None},
    {"symbol": "sh000001", "name": "上证指数", "fund_code": None},
    {"symbol": "sz399006", "name": "创业板指", "fund_code": None},
    {"symbol": "sh513500", "name": "标普500(513500代理)", "fund_code": "513500"},
]


def ensure_seeded(db: Session) -> None:
    """首次调用时灌入默认基准（幂等：已存在则跳过，fund 缺失的代理基准跳过代理映射）。"""
    existing_symbols = {b.symbol for b in crud.benchmark.list_benchmarks(db)}
    for cfg in DEFAULT_BENCHMARKS:
        if cfg["symbol"] in existing_symbols:
            continue
        fund_id = None
        if cfg["fund_code"]:
            fund = db.scalar(
                select(models.Fund).where(models.Fund.fund_code == cfg["fund_code"])
            )
            fund_id = fund.id if fund else None
        db.add(
            models.Benchmark(
                symbol=cfg["symbol"],
                name=cfg["name"],
                source="tencent",
                fund_id=fund_id,
            )
        )
    db.commit()


def sync(
    db: Session, benchmark: models.Benchmark, start: date, end: date
) -> tuple[int, int, int]:
    """拉取并幂等写入基准 [start, end] 日线。返回 (拉取条数, 插入, 已有)。"""
    if benchmark.fund_id is not None:
        rows = _proxy_rows(db, benchmark.fund_id, start, end)
        fetched = len(rows)
    else:
        provider = datasource.get_provider(db)
        bars = provider.fetch_daily(benchmark.symbol, start, end)
        rows = [(b.trade_date, Decimal(str(b.close))) for b in bars if b.close is not None]
        fetched = len(rows)
    inserted, existing = crud.benchmark.upsert_bars(db, benchmark.id, rows)
    return fetched, inserted, existing


def _proxy_rows(
    db: Session, fund_id: int, start: date, end: date
) -> list[tuple[date, Decimal]]:
    """代理基准：从 fund_price 拷贝收盘价（与基金历史价完全一致）。"""
    rows = db.execute(
        select(models.FundPrice.trade_date, models.FundPrice.close_price)
        .where(
            models.FundPrice.fund_id == fund_id,
            models.FundPrice.trade_date >= start,
            models.FundPrice.trade_date <= end,
        )
        .order_by(models.FundPrice.trade_date)
    ).all()
    return [(td, close) for td, close in rows if close is not None]
