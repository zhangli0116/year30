"""场外基金复权净值（分红复投口径）计算。

免费数据源（东财 f10/lsjz、akshare fund_open_fund_info_em）只提供单位净值/累计净值，
没有直接"复权单位净值"。这里用「单位净值序列 + 分红明细（除息日/每份分红）」自己算：

    复权因子 F 从 1 起步，每遇一个除息日（每份分红 d、当日除权后单位净值 u）：
        F *= (1 + d / u)          # 假设分红按除权后净值再投
    复权净值_t = 单位净值_t × F

分红明细来自 akshare `fund_fh_em`（按年拉全市场分红表，按代码过滤），
调用走 `AkShareProvider._guarded`（限流 1~2s + 重试 + 并发护栏）。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.logger import logger


def _fetch_dividends(code: str, start_year: int, end_year: int) -> list[tuple[date, float]]:
    """按年拉全市场分红表，过滤出该基金的 (除息日, 每份分红)。"""
    from app.services.akshare import AkShareProvider, _ak

    ak = _ak()
    provider = AkShareProvider()
    divs: list[tuple[date, float]] = []
    for year in range(start_year, end_year + 1):
        try:
            df = provider._guarded(
                lambda y=year: ak.fund_fh_em(
                    year=str(y), typ="", rank="BZDM", sort="asc", page=-1
                )
            )
        except Exception:  # noqa: BLE001
            logger.warning(f"复权净值：拉取 {code} {year} 年分红明细失败，跳过")
            continue
        if df is None or df.empty or "基金代码" not in df.columns:
            continue
        sub = df[df["基金代码"].astype(str) == str(code)]
        for _, row in sub.iterrows():
            try:
                ex = date.fromisoformat(str(row["除息日期"]).strip())
            except ValueError:
                continue
            try:
                amt = float(row["分红"])
            except (TypeError, ValueError):
                continue
            if amt and amt > 0:
                divs.append((ex, amt))
    divs.sort(key=lambda x: x[0])
    logger.info(f"复权净值：{code} 共 {len(divs)} 笔分红：{divs}")
    return divs


def compute_adj_nav(
    unit_map: dict[date, Decimal], dividends: list[tuple[date, float]]
) -> dict[date, Decimal]:
    """纯函数：由单位净值序列 + 分红明细计算复权净值（分红复投）。

    - 分红落在净值日（除息日有单位净值）：用当日除权后单位净值折算再投
    - 分红日期无单位净值：顺延到下一个净值日结算（用该日单位净值近似）
    """
    div_by_date: dict[date, float] = {}
    for d, amt in dividends:
        div_by_date[d] = div_by_date.get(d, 0.0) + amt
    div_dates = sorted(div_by_date)
    di = 0
    factor = 1.0
    out: dict[date, Decimal] = {}
    for d in sorted(unit_map):
        u = float(unit_map[d])
        while di < len(div_dates) and div_dates[di] <= d:
            factor *= 1.0 + div_by_date[div_dates[di]] / u
            di += 1
        out[d] = Decimal(str(round(u * factor, 4)))
    return out


def backfill(db: Session, fund_id: int) -> int:
    """对某场外基金：拉分红明细 + 按 fund_nav.unit_nav 计算复权净值并写回 adj_nav。

    返回更新条数。无单位净值数据或计算失败返回 0。
    """
    fund = db.get(models.Fund, fund_id)
    if fund is None:
        raise ValueError(f"基金 {fund_id} 不存在")
    rows = list(
        db.scalars(
            select(models.FundNav)
            .where(models.FundNav.fund_id == fund_id, models.FundNav.unit_nav.is_not(None))
            .order_by(models.FundNav.trade_date)
        ).all()
    )
    if not rows:
        return 0
    unit_map = {r.trade_date: r.unit_nav for r in rows if r.unit_nav is not None}
    min_year = min(d.year for d in unit_map)
    max_year = max(d.year for d in unit_map)
    dividends = _fetch_dividends(fund.fund_code, min_year, max_year)
    adj = compute_adj_nav(unit_map, dividends)
    updated = 0
    for r in rows:
        if r.trade_date in adj:
            r.adj_nav = adj[r.trade_date]
            updated += 1
    db.commit()
    logger.info(f"复权净值：基金{fund.fund_code} 更新 {updated}/{len(rows)} 条")
    return updated
