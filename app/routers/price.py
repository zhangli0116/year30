from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.logger import logger
from app.schemas import ApiResponse, error, success
from app.services import datasource, prices as price_svc
from app.services.price import FUND_TYPE_OTC

router = APIRouter(prefix="/api/v1/prices", tags=["prices"])


def _missing_segments(existing: set[date], start: date, end: date) -> list[tuple[date, date]]:
    """找出 [start, end] 内未被现有数据覆盖的连续时间段。

    只统计工作日（周一~周五）缺口，周末非交易日不算缺失；
    节假日会被包含在内（数量是上限，实际以数据源返回为准）。
    """
    segments: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() >= 5 or cursor in existing:
            cursor += timedelta(days=1)
            continue
        seg_start = cursor
        while cursor <= end and cursor.weekday() < 5 and cursor not in existing:
            cursor += timedelta(days=1)
        segments.append((seg_start, cursor - timedelta(days=1)))
    return segments


@router.get("/sources", response_model=ApiResponse[list[dict]])
def list_sources() -> ApiResponse:
    """列出可选的数据源（兼容旧接口，实际用 GET /api/v1/datasource）。"""
    return success(datasource.list_providers())


@router.get("", response_model=ApiResponse[list[schemas.PriceBarOut]])
def get_prices(
    fund_id: int = Query(..., description="基金ID"),
    start_date: date = Query(..., description="起始日期"),
    end_date: date = Query(..., description="结束日期"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    fund = db.get(models.Fund, fund_id)
    if fund is None:
        return error(40400, f"基金 {fund_id} 不存在")
    if fund.fund_type == FUND_TYPE_OTC:
        # 场外基金无 OHLC，把净值映射为 PriceBarOut（close=累计净值[分红再投口径]，其余空）
        rows = crud.nav.list_navs(db, fund_id, start_date, end_date)
        return success(
            [
                schemas.PriceBarOut(
                    fund_id=r.fund_id,
                    trade_date=r.trade_date,
                    open_price=None,
                    high_price=None,
                    low_price=None,
                    close_price=r.accum_nav if r.accum_nav is not None else r.unit_nav,
                    volume=None,
                    source=r.source,
                )
                for r in rows
            ]
        )
    return success(crud.price.list_prices(db, fund_id, start_date, end_date))


@router.post("/check", response_model=ApiResponse[schemas.PriceCheckOut])
def check_missing(
    payload: schemas.PriceSyncIn, db: Session = Depends(get_db)
) -> ApiResponse:
    """先确认：检查指定区间内哪些时间段缺失（未被现有数据覆盖），供前端确认后再同步。"""
    fund = db.get(models.Fund, payload.fund_id)
    if fund is None:
        return error(40400, f"基金 {payload.fund_id} 不存在")
    existing = price_svc.existing_dates(db, payload.fund_id)
    segments = _missing_segments(existing, payload.start_date, payload.end_date)
    missing_days = sum((e - s).days + 1 for s, e in segments)
    logger.info(f"检查缺失价格：基金{fund.fund_code} {payload.start_date}~{payload.end_date}，缺失{missing_days}天/{len(segments)}段")
    return success(
        schemas.PriceCheckOut(
            fund_id=payload.fund_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            missing_days=missing_days,
            segments=[schemas.PriceSegment(start=s, end=e) for s, e in segments],
        )
    )


@router.post("/sync", response_model=ApiResponse[schemas.PriceSyncOut])
def sync_prices(
    payload: schemas.PriceSyncIn, db: Session = Depends(get_db)
) -> ApiResponse:
    """按指定区间同步某基金的历史日线：未覆盖的日期调用数据源拉取并入库（幂等）。

    source 可传指定数据源（可选覆盖）；缺省用「当前数据源」（设置页切换）。
    """
    fund = db.get(models.Fund, payload.fund_id)
    if fund is None:
        return error(40400, f"基金 {payload.fund_id} 不存在")

    try:
        if fund.fund_type == FUND_TYPE_OTC:
            # 场外基金：无 K 线/盘口，取 otc 组数据源（东财/akshare），走 fetch_nav
            provider = datasource.get_provider(db, fund.fund_type)
            bars = provider.fetch_nav(fund.fund_code, payload.start_date, payload.end_date)
            inserted, existing = crud.nav.upsert_navs(
                db, payload.fund_id, bars, provider.name
            )
        else:
            if payload.source:
                provider = datasource.get_provider_by_name(payload.source)
                if provider is None or fund.fund_type not in provider.fund_types:
                    return error(
                        40006, f"未知数据源或不支持该标的类型：{payload.source}"
                    )
            else:
                provider = datasource.get_provider(db, fund.fund_type)
            symbol = datasource.fund_symbol(fund.exchange, fund.fund_code)
            bars = provider.fetch_daily(symbol, payload.start_date, payload.end_date)
            inserted, existing = crud.price.upsert_bars(
                db, payload.fund_id, bars, provider.name
            )
    except Exception as e:  # noqa: BLE001
        logger.error(f"同步价格失败：基金{fund.fund_code} 数据源{provider.name}：{e}")
        return error(50001, f"数据源拉取失败：{e}")
    logger.info(f"同步价格：基金{fund.fund_code} {payload.start_date}~{payload.end_date}，数据源{provider.name} 拉取{len(bars)} 新增{inserted} 已有{existing}")
    return success(
        schemas.PriceSyncOut(
            source=provider.name,
            fetched=len(bars),
            inserted=inserted,
            existing=existing,
            range_start=payload.start_date,
            range_end=payload.end_date,
        )
    )
