"""定投方案回测引擎。

模拟「每期定投 + 再平衡策略」从历史起始日到今天：
    每期入账 amount → 买入式平衡（低配补买、超配不卖，仅当现金充足）
    每年最后一个交易日 → 卖出式完全再平衡（超配卖出回现金 → 低配买入到目标）
指标：XIRR 年化（主，资金加权）、TWR（策略期间收益）、最大回撤/当前回撤（TWR 净值口径）、
      基准对比（归一化曲线 + CAGR）。
撮合规则与真实系统完全一致：整手=100份、买入收盘价、非交易日顺延下一交易日、
手续费 max(5, 本金×费率)（买0.03%/卖0.07%，复用 crud/purchase 常量）。
"""
from __future__ import annotations

from bisect import bisect_right
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.crud.purchase import MIN_FEE, _calc_fee
from app.services.xirr import xirr

_HANDS = 100  # 一手 = 100 份


def run_backtest(
    db: Session,
    plan: models.DcaPlan,
    start_date: date,
    end_date: date | None = None,
    amount: Decimal | None = None,
    benchmark_symbols: list[str] | None = None,
    year_end_rebalance: bool = True,
    unlisted_mode: str = "park",
) -> dict:
    """执行回测，返回结构化的结果 dict（供 router 组装 schema）。

    unlisted_mode：方案内标的「当时未上市/无历史价」时的处理——
        park（默认）       ：现金停泊，缺席标的的份额趴在现金里，上市后再补买
        redistribute       ：比例重分配，缺席标的的份额按比例分给已有标的（现金保持目标），
                             上市后切回原目标（会产生一次调仓）
    """
    today = end_date or date.today()
    benchmark_symbols = benchmark_symbols or []
    amount = amount if amount is not None else Decimal(str(plan.amount or 0))
    interval = plan.interval_days or 0
    warnings: list[str] = []
    cash_target_pct = Decimal(str(plan.cash_ratio or 0))

    # ---- 方案标的（排除现金虚拟基金）----
    plan_funds = db.execute(
        select(
            models.Fund.id,
            models.Fund.fund_code,
            models.Fund.fund_name,
            models.PlanFund.target_ratio,
        )
        .join(models.PlanFund, models.PlanFund.fund_id == models.Fund.id)
        .where(models.PlanFund.plan_id == plan.id)
        .order_by(models.Fund.fund_code)
    ).all()
    funds = [
        {
            "fund_id": fid,
            "fund_code": code,
            "fund_name": name,
            "target_ratio": Decimal(str(tr)),
        }
        for fid, code, name, tr in plan_funds
        if code != "000000"
    ]
    if not funds:
        warnings.append("方案未配置任何标的，无法回测")
    if amount <= 0:
        warnings.append("每期金额为 0，仅估算仓位，不产生投入")

    # ---- 数据装载（一次性，主循环零 DB 访问）----
    price_map: dict[int, dict[date, Decimal]] = {}
    all_dates: set[date] = set()
    for f in funds:
        rows = db.execute(
            select(models.FundPrice.trade_date, models.FundPrice.close_price)
            .where(
                models.FundPrice.fund_id == f["fund_id"],
                models.FundPrice.trade_date >= start_date,
                models.FundPrice.trade_date <= today,
            )
            .order_by(models.FundPrice.trade_date)
        ).all()
        pd = {td: Decimal(str(close)) for td, close in rows if close is not None}
        if not pd:
            warnings.append(f"基金 {f['fund_code']} 在区间内无历史价，无法参与回测")
        price_map[f["fund_id"]] = pd
        all_dates.update(pd.keys())
    trade_days = sorted(all_dates)
    if not trade_days:
        return _empty(plan, warnings, amount, start_date, today, unlisted_mode)

    eff_start = max(start_date, trade_days[0])
    last_day = trade_days[-1]
    span_days = (last_day - eff_start).days

    # 年末最后交易日
    year_ends: dict[int, date] = {}
    for y in {d.year for d in trade_days}:
        year_ends[y] = max(d for d in trade_days if d.year == y)

    # 定投计划日（严格按起始日 + k×间隔，忽略容错；非交易日顺延到下一交易日执行）
    schedule: list[date] = []
    if interval > 0:
        k = 0
        while True:
            sd = eff_start + timedelta(days=k * interval)
            if sd > last_day:
                break
            schedule.append(sd)
            k += 1

    # 每只基金前向填充价格函数：给定交易日返回最近已知收盘价（当日无价用上一价）
    price_dates: dict[int, list[date]] = {}
    price_vals: dict[int, list[Decimal]] = {}
    for fid, pd in price_map.items():
        price_dates[fid] = sorted(pd)
        price_vals[fid] = [pd[d] for d in price_dates[fid]]

    def price_fwd(fid: int, d: date) -> Decimal | None:
        ds = price_dates.get(fid)
        if not ds:
            return None
        idx = bisect_right(ds, d) - 1
        if idx < 0:
            return None
        return price_vals[fid][idx]

    # ---- 状态 ----
    cash = Decimal("0")
    shares: dict[int, int] = {}  # 份额
    deposits: list[tuple[date, Decimal]] = []
    trades: list[dict] = []
    points: list[dict] = []

    def prices_at(d: date) -> dict[int, Decimal]:
        return {fid: price_fwd(fid, d) for fid in price_dates}

    def target_pct_for(f: dict, d: date) -> Decimal:
        """某日某标的的有效目标占比。

        默认（park）：固定用方案原始占比（缺席标的无价时被跳过，现金吸收）。
        redistribute：缺席标的（当日无价）占比为 0；可用标的按比例放大，
            使「可用标的 + 现金」= 100%（现金保持目标），满仓运作；全部可用则回到原始占比。
        """
        if unlisted_mode != "redistribute":
            return f["target_ratio"]
        available = [g for g in funds if price_fwd(g["fund_id"], d) is not None]
        if not available or len(available) == len(funds):
            return f["target_ratio"]
        if price_fwd(f["fund_id"], d) is None:
            return Decimal("0")  # 缺席不交易
        avail_sum = sum(g["target_ratio"] for g in available)
        if avail_sum <= 0:
            return f["target_ratio"]
        scale = (Decimal("100") - cash_target_pct) / avail_sum
        return f["target_ratio"] * scale

    def buy_side(d: date, p: dict[int, Decimal], reason: str) -> None:
        nonlocal cash
        total = cash + sum(shares.get(fid, 0) * p[fid] for fid in p if p[fid] is not None)
        for f in funds:
            fid = f["fund_id"]
            price = p.get(fid)
            if price is None:
                continue  # 当日停牌/未上市，不买
            mv = shares.get(fid, 0) * price
            gap = total * target_pct_for(f, d) / Decimal("100") - mv
            if gap <= 0:
                continue  # 超配/达标 → 不卖
            lot = price * _HANDS
            hands = int(gap // lot)
            if hands <= 0:
                continue
            principal = hands * lot
            fee = _calc_fee(principal, None, None, is_sell=False)
            if principal + fee > cash:
                hands = int((cash - MIN_FEE) // lot)
                if hands <= 0:
                    continue
                principal = hands * lot
                fee = _calc_fee(principal, None, None, is_sell=False)
            cash -= principal + fee
            shares[fid] = shares.get(fid, 0) + hands * _HANDS
            trades.append(
                {
                    "date": d,
                    "fund_code": f["fund_code"],
                    "fund_name": f["fund_name"],
                    "side": "buy",
                    "hands": hands,
                    "price": price,
                    "principal": principal,
                    "fee": fee,
                    "total_amount": principal + fee,
                    "reason": reason,
                }
            )

    def annual_rebalance(d: date, p: dict[int, Decimal]) -> None:
        nonlocal cash
        total = cash + sum(shares.get(fid, 0) * p[fid] for fid in p if p[fid] is not None)
        # ① 先卖超配（整手，回现金扣卖费）
        for f in funds:
            fid = f["fund_id"]
            price = p.get(fid)
            if price is None:
                warnings.append(f"{f['fund_code']} 年末再平衡当日无价，跳过该基金")
                continue
            mv = shares.get(fid, 0) * price
            target_mv = total * target_pct_for(f, d) / Decimal("100")
            if mv <= target_mv:
                continue
            lot = price * _HANDS
            hands = int((mv - target_mv) // lot)
            if hands <= 0:
                continue
            principal = hands * lot
            fee = _calc_fee(principal, None, None, is_sell=True)
            cash += principal - fee
            shares[fid] = shares.get(fid, 0) - hands * _HANDS
            trades.append(
                {
                    "date": d,
                    "fund_code": f["fund_code"],
                    "fund_name": f["fund_name"],
                    "side": "sell",
                    "hands": hands,
                    "price": price,
                    "principal": principal,
                    "fee": fee,
                    "total_amount": principal,
                    "reason": "annual",
                }
            )
        # ② 再买低配（卖出现金回流，填到目标）
        for f in funds:
            fid = f["fund_id"]
            price = p.get(fid)
            if price is None or cash <= 0:
                continue
            mv = shares.get(fid, 0) * price
            target_mv = total * target_pct_for(f, d) / Decimal("100")
            if mv >= target_mv:
                continue
            lot = price * _HANDS
            gap = target_mv - mv
            hands = min(int(gap // lot), int((cash - MIN_FEE) // lot))
            if hands <= 0:
                continue
            principal = hands * lot
            fee = _calc_fee(principal, None, None, is_sell=False)
            cash -= principal + fee
            shares[fid] = shares.get(fid, 0) + hands * _HANDS
            trades.append(
                {
                    "date": d,
                    "fund_code": f["fund_code"],
                    "fund_name": f["fund_name"],
                    "side": "buy",
                    "hands": hands,
                    "price": price,
                    "principal": principal,
                    "fee": fee,
                    "total_amount": principal + fee,
                    "reason": "annual",
                }
            )

    # ---- 主循环（按交易日，非逐日历日）----
    nav = 1.0
    peak = 1.0
    max_dd = 0.0
    peak_date: date | None = None
    max_peak_date: date | None = None  # 最大回撤对应峰值的日期（回撤发生时冻结）
    trough_date: date | None = None
    prev_V: Decimal | None = None
    invested = Decimal("0")
    i = 0
    for d in trade_days:
        dep_t = Decimal("0")
        while i < len(schedule) and d >= schedule[i]:
            cash += amount
            deposits.append((d, amount))
            dep_t += amount
            invested += amount
            i += 1
        p = prices_at(d)
        if dep_t > 0:
            buy_side(d, p, "period")
        if year_end_rebalance and d == year_ends.get(d.year):
            annual_rebalance(d, p)
        equity = sum(shares.get(fid, 0) * p[fid] for fid in p if p[fid] is not None)
        V = cash + equity
        dd = 0.0
        if prev_V is not None and prev_V > 0:
            r = float(V - prev_V - dep_t) / float(prev_V)
            nav *= 1.0 + r
            if nav > peak:
                peak = nav
                peak_date = d
            dd = nav / peak - 1.0
            if dd < max_dd:
                max_dd = dd
                max_peak_date = peak_date  # 冻结该回撤发生时对应的峰值日期
                trough_date = d
        points.append(
            {
                "date": d,
                "asset": V,
                "equity": equity,
                "cash": cash,
                "invested": invested,
                "nav": nav,
                "drawdown": dd,
            }
        )
        prev_V = V

    # ---- 指标 ----
    terminal = float(prev_V) if prev_V is not None else 0.0
    flows = [(d, -float(amt)) for d, amt in deposits]
    if prev_V is not None:
        flows.append((last_day, terminal))
    xirr_val = xirr(flows) if len(flows) >= 2 else None

    twr = nav - 1.0
    twr_annualized = None
    if twr > -1.0 and span_days > 0:
        twr_annualized = (1.0 + twr) ** (365.0 / span_days) - 1.0

    current_drawdown = nav / peak - 1.0 if peak > 0 else 0.0
    gain = terminal - float(invested)
    gain_pct = gain / float(invested) * 100 if invested > 0 else None

    # ---- 基准对比 ----
    benchmarks_out = (
        _benchmark_series(db, benchmark_symbols, trade_days, eff_start, last_day, warnings)
        if benchmark_symbols
        else []
    )

    return {
        "plan_id": plan.id,
        "plan_name": plan.name,
        "params": {
            "start_date": start_date,
            "end_date": today,
            "amount": amount,
            "interval_days": interval,
            "rebalance_strategy": plan.rebalance_strategy,
            "year_end_rebalance": year_end_rebalance,
            "unlisted_mode": unlisted_mode,
        },
        "metrics": {
            "xirr": xirr_val,
            "twr": twr,
            "twr_annualized": twr_annualized,
            "span_days": span_days,
            "start_date": eff_start,
            "end_date": last_day,
            "max_drawdown": max_dd,
            "max_drawdown_start": max_peak_date,
            "max_drawdown_end": trough_date,
            "current_drawdown": current_drawdown,
            "invested": invested,
            "current_value": Decimal(str(round(terminal, 2))),
            "gain": Decimal(str(round(gain, 2))),
            "gain_pct": round(gain_pct, 4) if gain_pct is not None else None,
            "deposit_count": len(deposits),
        },
        "points": points,
        "trades": trades,
        "benchmarks": benchmarks_out,
        "warnings": warnings,
    }


def _benchmark_series(
    db: Session,
    symbols: list[str],
    trade_days: list[date],
    eff_start: date,
    last_day: date,
    warnings: list[str],
) -> list[dict]:
    """对齐 trade_days 生成各基准归一化净值序列（t0 前为 None），返回 CAGR 与 total_return。"""
    from app import crud

    out: list[dict] = []
    for symbol in symbols:
        bm = crud.benchmark.get_by_symbol(db, symbol)
        if bm is None:
            warnings.append(f"基准 {symbol} 不存在，已跳过")
            continue
        rows = db.execute(
            select(models.BenchmarkPrice.trade_date, models.BenchmarkPrice.close_price)
            .where(
                models.BenchmarkPrice.benchmark_id == bm.id,
                models.BenchmarkPrice.trade_date >= eff_start,
                models.BenchmarkPrice.trade_date <= last_day,
            )
            .order_by(models.BenchmarkPrice.trade_date)
        ).all()
        if not rows:
            warnings.append(f"基准 {bm.name} 在回测区间无数据，已跳过（可先在基准页同步）")
            continue
        bmap = {td: float(close) for td, close in rows if close is not None}
        bdates = sorted(bmap)
        t0 = bdates[0]
        base = bmap[t0]
        series: list[dict] = []
        prev_b: float | None = None
        bi = 0
        for d in trade_days:
            while bi < len(bdates) and bdates[bi] <= d:
                prev_b = bmap[bdates[bi]]
                bi += 1
            series.append({"date": d, "nav": round(prev_b / base, 6) if prev_b is not None else None})
        total_return = series[-1]["nav"] - 1.0
        # 年化按基准自身数据跨度（t0 → last_day），而非完整回测跨度（基准可能数据不全）
        bench_span = (last_day - t0).days
        cagr = None
        if total_return > -1.0 and bench_span > 0:
            cagr = (1.0 + total_return) ** (365.0 / bench_span) - 1.0
        out.append(
            {
                "symbol": bm.symbol,
                "name": bm.name,
                "cagr": cagr,
                "total_return": round(total_return, 6),
                "nav_series": series,
            }
        )
    return out


def run_coverage(
    db: Session,
    plan_id: int,
    start_date: date,
    end_date: date,
    benchmark_symbols: list[str] | None = None,
) -> dict:
    """数据覆盖检查：各方案基金 + 所选基准在 [start, end] 的**真实缺失**情况。

    判定口径（修复"节假日/今天未收盘"被误报为缺口的问题）：
      - 「全局交易日」= 窗口内所有标的数据日期的并集（剔除周末；节假日无人有数据，天然排除）
      - 每标的「真实缺失」= 全局交易日中它没有的日期 → 才是真正会失真/需补的缺口
      - covers_window = 数据起点 ≤ start 且 数据终点 ≥ 全局最后交易日 且 无真实缺失
      - actionable = 存在数据起点之后的真实缺失（内部/尾部可补），或窗口内完全没数据；
                     纯「数据起点晚于 start」（fund 多为上市晚）只提示不标可补；
                     基准（指数历史长）起点晚视为没同步 → 可补
    """
    from app import crud

    raw: list[dict] = []
    fund_rows = db.execute(
        select(
            models.Fund.id, models.Fund.fund_code, models.Fund.fund_name
        )
        .join(models.PlanFund, models.PlanFund.fund_id == models.Fund.id)
        .where(models.PlanFund.plan_id == plan_id)
        .order_by(models.Fund.fund_code)
    ).all()
    for fid, code, name in fund_rows:
        if code == "000000":
            continue
        dates = set(
            db.scalars(
                select(models.FundPrice.trade_date).where(models.FundPrice.fund_id == fid)
            ).all()
        )
        raw.append(_raw_item("fund", fid, code, name, dates))
    for symbol in (benchmark_symbols or []):
        bm = crud.benchmark.get_by_symbol(db, symbol)
        if bm is None:
            continue
        dates = set(
            db.scalars(
                select(models.BenchmarkPrice.trade_date).where(
                    models.BenchmarkPrice.benchmark_id == bm.id
                )
            ).all()
        )
        raw.append(_raw_item("benchmark", bm.id, symbol, bm.name, dates))

    # 窗口内全局交易日（并集）
    trading_days = sorted(
        {d for it in raw for d in it["dates"] if start_date <= d <= end_date}
    )
    if not trading_days:
        # 窗口内无任何数据 → 全部视为可补（需同步）
        items = [
            {
                "kind": it["kind"],
                "id": it["id"],
                "code": it["code"],
                "name": it["name"],
                "first_date": it["first_date"],
                "last_date": it["last_date"],
                "missing_days": 0,
                "segments": [],
                "covers_window": False,
                "actionable": True,
            }
            for it in raw
        ]
        return {
            "items": items,
            "start_date": start_date,
            "end_date": end_date,
            "ready": False,
        }

    coverage_end = trading_days[-1]  # 有效覆盖终点（容忍"今天未收盘"的尾部 1 天）
    items = [
        _finalize_item(
            it,
            start_date,
            coverage_end,
            [d for d in trading_days if d not in it["dates"]],
        )
        for it in raw
    ]
    ready = bool(items) and all(it["covers_window"] for it in items)
    return {
        "items": items,
        "start_date": start_date,
        "end_date": end_date,
        "ready": ready,
    }


def _raw_item(kind: str, id_: int, code: str, name: str, dates: set[date]) -> dict:
    return {
        "kind": kind,
        "id": id_,
        "code": code,
        "name": name,
        "dates": dates,
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
    }


def _finalize_item(
    it: dict,
    start_date: date,
    coverage_end: date | None,
    missing: list[date],
) -> dict:
    """按全局交易日口径生成覆盖条目（missing 为升序真实缺失交易日）。"""
    first = it["first_date"]
    last = it["last_date"]
    covers_window = (
        first is not None
        and last is not None
        and coverage_end is not None
        and first <= start_date
        and last >= coverage_end
        and not missing
    )
    internal = [d for d in missing if first is not None and d >= first]
    if first is None:
        actionable = True  # 窗口内完全没数据 → 需同步
    elif internal:
        actionable = True  # 数据起点之后的真实缺口（内部/尾部）→ 可补
    elif missing and it["kind"] == "benchmark":
        actionable = True  # 基准（指数）历史长，缺失全在数据起点前 → 多为没同步
    else:
        actionable = False  # fund 纯起点晚 → 多为上市晚，仅提示
    return {
        "kind": it["kind"],
        "id": it["id"],
        "code": it["code"],
        "name": it["name"],
        "first_date": first,
        "last_date": last,
        "missing_days": len(missing),
        "segments": _segments(missing),
        "covers_window": covers_window,
        "actionable": actionable,
    }


def _segments(days: list[date]) -> list[dict]:
    """连续缺失交易日 → 时间段。"""
    if not days:
        return []
    out: list[dict] = []
    s = prev = days[0]
    for d in days[1:]:
        if (d - prev).days > 1:
            out.append({"start": s, "end": prev})
            s = d
        prev = d
    out.append({"start": s, "end": prev})
    return out


def _empty(plan, warnings, amount, start_date, today, unlisted_mode="park") -> dict:
    return {
        "plan_id": plan.id,
        "plan_name": plan.name,
        "params": {
            "start_date": start_date,
            "end_date": today,
            "amount": amount,
            "interval_days": plan.interval_days or 0,
            "rebalance_strategy": plan.rebalance_strategy,
            "year_end_rebalance": True,
            "unlisted_mode": unlisted_mode,
        },
        "metrics": {
            "xirr": None,
            "twr": None,
            "twr_annualized": None,
            "span_days": 0,
            "start_date": None,
            "end_date": None,
            "max_drawdown": 0.0,
            "max_drawdown_start": None,
            "max_drawdown_end": None,
            "current_drawdown": 0.0,
            "invested": Decimal("0"),
            "current_value": Decimal("0"),
            "gain": Decimal("0"),
            "gain_pct": None,
            "deposit_count": 0,
        },
        "points": [],
        "trades": [],
        "benchmarks": [],
        "warnings": warnings,
    }
