"""定投方案回测引擎。

模拟「每期定投 + 再平衡策略」从历史起始日到今天：
    每期入账 amount → buy_rebalance 开：买入式平衡（低配补买、超配不卖）；
                       关：纯按目标比例定投（不修正偏离，让漂移可见）
    每年最后一个交易日 → sell_rebalance 开：超配卖出回现金；buy_rebalance 开：低配买入到目标
    两个开关可独立组合（都开/都关/单开）
指标：XIRR 年化（主，资金加权）、TWR（策略期间收益）、最大回撤/当前回撤（TWR 净值口径）、
      基准对比（归一化曲线 + CAGR）、各标的持仓占比时间序列（含现金）。
撮合规则与真实系统完全一致：整手=100份、买入收盘价、
定投日排除非交易日——每日定投只在交易日投（非交易日不投、不累积）；
周/月/季的计划日落在非交易日时顺延到下一交易日执行。
手续费 max(5, 本金×费率)（买0.03%/卖0.07%，复用 crud/purchase 常量）。
"""
from __future__ import annotations

from bisect import bisect_right
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services import prices as price_svc
from app.services.rebalance import get_params, judge, threshold_for
from app.services.xirr import xirr

DRAWUP_WINDOW = 20  # 水上曲线：近 N 个交易日的滚动涨幅（约 1 个月），正=近期涨多→回调风险

# 回测策略默认配置：所有旋钮显式化，可整体传入 strategy 覆盖
DEFAULT_STRATEGY = {
    "buy_rebalance": True,  # 买入式再平衡（每期低配补买、超配不卖）
    "sell_rebalance": True,  # 卖出式再平衡（年末超配卖出回现金）
    "unlisted_mode": "park",  # 未上市标的处理：park=现金停泊 / redistribute=比例重分配
    "hands": 100,  # 一手份数
    "drawup_window": DRAWUP_WINDOW,  # 水上曲线近 N 交易日滚动涨幅窗口
    "fees": {"buy_rate": 0.03, "sell_rate": 0.07, "min_fee": 5.0},  # 费率(%)
    # 年末卖出式判定阈值：空=用 app_setting（体检页保存的那套）
    "rb": {},
    "amount": {"base": None, "factors": []},  # 每期基准金额 + 动态金额因子
}

# 因子类型：drawdown=组合水下(nav/peak−1)；drawup=近 window 交易日滚动涨幅
FACTOR_TYPES = ("drawdown", "drawup")


def _merge_strategy(strategy: dict | None) -> dict:
    """合入默认策略；嵌套 dict 浅合并（fees/rb/amount.factors 由外层整体替换或逐键覆盖）。"""
    merged = deepcopy(DEFAULT_STRATEGY)
    if not strategy:
        return merged
    for k, v in strategy.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k].update(v)
        else:
            merged[k] = v
    return merged


def _band_multiplier(bands: list[dict], sig: float) -> float:
    """分档查找：取第一个 min≤sig≤max（None=开区间）的乘数，未命中默认 1.0。"""
    for b in bands:
        lo = b.get("min")
        hi = b.get("max")
        if lo is not None and sig < lo:
            continue
        if hi is not None and sig > hi:
            continue
        return float(b.get("mult", 1.0))
    return 1.0


def _factor_multiplier(factors, nav: float, peak: float, nav_history: list[float], default_window: int) -> float:
    """每期金额乘数 = Π 各启用因子的 band 乘数（基于"前一日"组合状态，无前视）。"""
    mult = 1.0
    for f in factors:
        if not f.get("enabled", True):
            continue
        ftype = f.get("type")
        if ftype == "drawdown":
            sig = nav / peak - 1.0 if peak > 0 else 0.0
        elif ftype == "drawup":
            window = int(f.get("window") or default_window or DRAWUP_WINDOW)
            sig = nav / nav_history[-window - 1] - 1.0 if len(nav_history) > window else 0.0
        else:
            continue
        mult *= _band_multiplier(f.get("bands") or [], sig)
    return mult


def run_backtest(
    db: Session,
    plan: models.DcaPlan,
    start_date: date,
    end_date: date | None = None,
    strategy: dict | None = None,
    benchmark_symbols: list[str] | None = None,
) -> dict:
    """执行回测，返回结构化的结果 dict（供 router 组装 schema）。

    strategy：回测策略配置（见 DEFAULT_STRATEGY）——买入/卖出式、费率、每手份数、
        年末判定阈值、未上市处理、动态金额因子等全部旋钮可在此手动设置。
    """
    s = _merge_strategy(strategy)
    buy_rebalance = bool(s["buy_rebalance"])
    sell_rebalance = bool(s["sell_rebalance"])
    unlisted_mode = s["unlisted_mode"]
    per_hand = int(s["hands"])
    drawup_window = int(s["drawup_window"])
    fee_buy = Decimal(str(s["fees"]["buy_rate"]))
    fee_sell = Decimal(str(s["fees"]["sell_rate"]))
    min_fee = Decimal(str(s["fees"]["min_fee"]))
    amount_cfg = s["amount"]
    base_amount = (
        Decimal(str(amount_cfg["base"]))
        if amount_cfg.get("base") is not None
        else Decimal(str(plan.amount or 0))
    )
    factors = amount_cfg.get("factors") or []

    today = end_date or date.today()
    amount = base_amount  # 每期基准金额
    interval = plan.interval_days or 0
    warnings: list[str] = []
    cash_target_pct = Decimal(str(plan.cash_ratio or 0))
    # 年末卖出式判定阈值：app_setting 为底，strategy.rb 逐项覆盖（策略页实验室式调参，不改 app_setting）
    rb_params = get_params(db)
    rb_params.update({k: float(v) for k, v in (s["rb"] or {}).items() if v is not None})

    def calc_fee(principal: Decimal, is_sell: bool) -> Decimal:
        rate = fee_sell if is_sell else fee_buy
        return max(min_fee, (principal * rate / Decimal("100")).quantize(Decimal("0.01")))

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
        # 按 fund_type 取 fund_price 收盘价或 fund_nav 净值；场外用累计净值（分红再投口径，避免分红误差）
        pd = {
            td: price
            for td, price in price_svc.series(db, f["fund_id"], start_date, today, accum=True)
        }
        if not pd:
            warnings.append(f"基金 {f['fund_code']} 在区间内无历史价，无法参与回测")
        price_map[f["fund_id"]] = pd
        all_dates.update(pd.keys())
    trade_days = sorted(all_dates)
    if not trade_days:
        return _empty(plan, warnings, base_amount, start_date, today, s)

    eff_start = max(start_date, trade_days[0])
    last_day = trade_days[-1]
    span_days = (last_day - eff_start).days

    # 年末最后交易日
    year_ends: dict[int, date] = {}
    for y in {d.year for d in trade_days}:
        year_ends[y] = max(d for d in trade_days if d.year == y)

    # 定投计划日：排除非交易日（非交易日不进行定投）
    #   interval==1（每日）：直接在交易日上逐日定投，非交易日跳过、不累积到下一交易日
    #   interval>1（周/月/季）：按起始日 + k×间隔生成计划日；落在非交易日的计划日
    #       由主循环 `while d >= schedule[i]` 顺延到下一交易日执行（一次一个周期，不叠加）
    schedule: list[date] = []
    if interval == 1:
        schedule = list(trade_days)
    elif interval > 0:
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
    ever_available: set[int] = set()  # 出现过的有价标的（判"新上市"用）

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
            lot = price * per_hand
            hands = int(gap // lot)
            if hands <= 0:
                continue
            principal = hands * lot
            fee = calc_fee(principal, False)
            if principal + fee > cash:
                hands = int((cash - min_fee) // lot)
                if hands <= 0:
                    continue
                principal = hands * lot
                fee = calc_fee(principal, False)
            cash -= principal + fee
            shares[fid] = shares.get(fid, 0) + hands * per_hand
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
                    "total_amount": principal,
                    "reason": reason,
                    "amount_mult": period_mult,  # 动态金额因子缩放系数（本期）
                }
            )

    def dca_buy(d: date, p: dict[int, Decimal], budget: Decimal, reason: str) -> None:
        """纯定投（买入式平衡关闭）：只用本期入账金额，按各标的有效目标占比买入。

        有效占比经 target_pct_for 换算，尊重 park/redistribute：
        park 下未上市标的的份额留在现金（不重分配）；redistribute 下可用标的按比例放大。
        新上市标的一次性用停泊现金补到目标（"上市后再补买"，park 语义），之后按每期入账定投。
        """
        nonlocal cash
        if budget <= 0 or cash <= 0:
            return
        total_now = cash + sum(
            shares.get(f["fund_id"], 0) * p.get(f["fund_id"])
            for f in funds
            if p.get(f["fund_id"]) is not None
        )
        for f in funds:
            fid = f["fund_id"]
            price = p.get(fid)
            if price is None:
                continue  # 未上市/无价 → 该标的份额留在现金（park）
            eff = target_pct_for(f, d)
            if eff <= 0:
                continue
            newly = fid not in ever_available
            ever_available.add(fid)
            lot = price * per_hand
            if newly and unlisted_mode == "park":
                # 新上市（仅 park 有停泊现金）：一次补到目标占比
                gap = total_now * eff / Decimal("100") - shares.get(fid, 0) * price
            else:
                # 常规定投 / redistribute 新上市：本期入账按目标比例
                gap = budget * eff / Decimal("100")
            hands = int(gap // lot)
            if hands <= 0:
                continue
            principal = hands * lot
            fee = calc_fee(principal, False)
            if principal + fee > cash:
                hands = int((cash - min_fee) // lot)
                if hands <= 0:
                    continue
                principal = hands * lot
                fee = calc_fee(principal, False)
            cash -= principal + fee
            shares[fid] = shares.get(fid, 0) + hands * per_hand
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
                    "total_amount": principal,
                    "reason": reason,
                    "amount_mult": period_mult,  # 动态金额因子缩放系数（本期）
                }
            )

    def _should_rebalance(f: dict, d: date, total: Decimal, mv: Decimal, price: Decimal) -> tuple[bool, str]:
        """按「再平衡体检」判定参数判断该基金年末是否需要调：
        阈值(%) = clamp(目标% × R, 底线, 上限)；|偏离%| > 阈值 且 偏离金额 ≥ 金额底线 → 调。
        返回 (是否调, above/below/normal)。
        """
        target_pct = target_pct_for(f, d)
        target_mv = total * target_pct / Decimal("100")
        deviation_pct = float((mv - target_mv) / total * 100) if total > 0 else 0.0
        threshold = threshold_for(float(target_pct), rb_params)
        deviation_amount = abs(deviation_pct) / 100 * float(total)
        status = judge(deviation_pct, threshold, rb_params["amount_floor"], deviation_amount)
        return status != "normal", status

    def annual_rebalance(d: date, p: dict[int, Decimal]) -> None:
        nonlocal cash
        total = cash + sum(shares.get(fid, 0) * p[fid] for fid in p if p[fid] is not None)
        # ① 先卖超配（整手，回现金扣卖费）；只调「体检判定为超配」的基金；sell_rebalance 关则跳过
        if sell_rebalance:
            for f in funds:
                fid = f["fund_id"]
                price = p.get(fid)
                if price is None:
                    warnings.append(f"{f['fund_code']} 年末再平衡当日无价，跳过该基金")
                    continue
                mv = shares.get(fid, 0) * price
                need, status = _should_rebalance(f, d, total, mv, price)
                if not need or status != "above":
                    continue
                target_mv = total * target_pct_for(f, d) / Decimal("100")
                lot = price * per_hand
                hands = int((mv - target_mv) // lot)
                if hands <= 0:
                    continue
                principal = hands * lot
                fee = calc_fee(principal, True)
                cash += principal - fee
                shares[fid] = shares.get(fid, 0) - hands * per_hand
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
        # ② 再买低配（卖出现金回流，填到目标）；只调「体检判定为低配」的基金；buy_rebalance 关则跳过
        if buy_rebalance:
            for f in funds:
                fid = f["fund_id"]
                price = p.get(fid)
                if price is None or cash <= 0:
                    continue
                mv = shares.get(fid, 0) * price
                need, status = _should_rebalance(f, d, total, mv, price)
                if not need or status != "below":
                    continue
                target_mv = total * target_pct_for(f, d) / Decimal("100")
                lot = price * per_hand
                gap = target_mv - mv
                hands = min(int(gap // lot), int((cash - min_fee) // lot))
                if hands <= 0:
                    continue
                principal = hands * lot
                fee = calc_fee(principal, False)
                cash -= principal + fee
                shares[fid] = shares.get(fid, 0) + hands * per_hand
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
                        "total_amount": principal,
                        "reason": "annual",
                    }
                )

    # ---- 主循环（按交易日，非逐日历日）----
    nav = 1.0
    peak = 1.0  # 净值运行最高点（水下曲线参考）
    nav_history: list[float] = []  # 逐日净值序列（水上滚动涨幅用）
    max_dd = 0.0
    max_du = 0.0
    peak_date: date | None = None
    max_peak_date: date | None = None  # 最大回撤对应峰值的日期（回撤发生时冻结）
    trough_date: date | None = None
    prev_V: Decimal | None = None
    invested = Decimal("0")
    i = 0
    period_mult = 1.0  # 本期金额缩放系数（动态金额因子乘积），记录到 period 成交
    for d in trade_days:
        # 动态金额：用"前一日"组合状态算因子乘数（决策时看不到当日收盘，无前视）
        if factors:
            period_mult = _factor_multiplier(factors, nav, peak, nav_history, drawup_window)
        else:
            period_mult = 1.0
        amt = (base_amount * Decimal(str(period_mult))).quantize(Decimal("0.01"))
        dep_t = Decimal("0")
        while i < len(schedule) and d >= schedule[i]:
            if amt > 0:
                cash += amt
                deposits.append((d, amt))
                dep_t += amt
                invested += amt
            i += 1
        p = prices_at(d)
        if dep_t > 0:
            if buy_rebalance:
                buy_side(d, p, "period")
            else:
                dca_buy(d, p, dep_t, "period")
        if d == year_ends.get(d.year) and (sell_rebalance or buy_rebalance):
            annual_rebalance(d, p)
        equity = sum(shares.get(fid, 0) * p[fid] for fid in p if p[fid] is not None)
        V = cash + equity
        dd = 0.0
        du = 0.0
        if prev_V is not None and prev_V > 0:
            r = float(V - prev_V - dep_t) / float(prev_V)
            nav *= 1.0 + r
            if nav > peak:
                peak = nav
                peak_date = d
            dd = nav / peak - 1.0  # 水下：距峰值跌幅（恒 ≤0）
            if dd < max_dd:
                max_dd = dd
                max_peak_date = peak_date  # 冻结该回撤发生时对应的峰值日期
                trough_date = d
        # 水上：近 drawup_window 个交易日的滚动涨幅（正=近期涨多→回调风险）
        nav_history.append(nav)
        if len(nav_history) > drawup_window:
            du = nav / nav_history[-drawup_window - 1] - 1.0
        if du > max_du:
            max_du = du
        # 各标的持仓占比（%），现金以 000000 键承载（与真实系统口径一致）
        alloc = {}
        for f in funds:
            fid = f["fund_id"]
            pv = p.get(fid)
            alloc[f["fund_code"]] = (
                round(float(shares.get(fid, 0) * pv) / float(V) * 100, 2)
                if (pv is not None and V > 0)
                else 0.0
            )
        alloc["000000"] = round(float(cash) / float(V) * 100, 2) if V > 0 else 0.0
        points.append(
            {
                "date": d,
                "asset": V,
                "equity": equity,
                "cash": cash,
                "invested": invested,
                "nav": nav,
                "drawdown": dd,
                "drawup": du,
                "allocations": alloc,
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
    current_drawup = (
        nav / nav_history[-drawup_window - 1] - 1.0
        if len(nav_history) > drawup_window
        else 0.0
    )
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
            "buy_rebalance": buy_rebalance,
            "sell_rebalance": sell_rebalance,
            "unlisted_mode": unlisted_mode,
            "drawup_window": drawup_window,
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
            "max_drawup": max_du,
            "current_drawup": current_drawup,
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
        dates = price_svc.existing_dates(db, fid)
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


def _empty(plan, warnings, amount, start_date, today, s: dict) -> dict:
    return {
        "plan_id": plan.id,
        "plan_name": plan.name,
        "params": {
            "start_date": start_date,
            "end_date": today,
            "amount": amount,
            "interval_days": plan.interval_days or 0,
            "rebalance_strategy": plan.rebalance_strategy,
            "buy_rebalance": bool(s["buy_rebalance"]),
            "sell_rebalance": bool(s["sell_rebalance"]),
            "unlisted_mode": s["unlisted_mode"],
            "drawup_window": int(s["drawup_window"]),
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
            "max_drawup": 0.0,
            "current_drawup": 0.0,
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
