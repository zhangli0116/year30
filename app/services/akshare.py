"""AKShare（非官方）数据源。

AKShare 是社区开源库，爬取东财/新浪等公开页面，**非官方**：接口可能变动、有反爬/限流风险。
因此加调用限制（模块级，线程安全）：
    - 限流：每次请求距上一次至少 `random.uniform(1, 2)` 秒
    - 重试：失败最多 `MAX_RETRIES=3` 次，指数+抖动退避
    - 并发：`BoundedSemaphore(4)` 护栏（3~5 区间取 4；当前链路单线程，主要为将来并行兜底）
所有 akshare 调用统一走 `_guarded()`。

能力（按 fund_type）：
    etf：`fetch_daily` 用新浪系 `fund_etf_hist_sina`（东财 push2his 系在本环境不稳）；
         指数（供基准用）用 `stock_zh_index_daily`；`fetch_quotes` 用 `fund_etf_spot_em`
         （全市场表，仅买1/卖1；一次约十几秒，加 30s TTL 缓存）。
    otc：`fetch_nav` 用 `fund_open_fund_info_em`（单位净值 + 累计净值走势）。
akshare 库 lazy import（方法内），避免拖慢启动；未安装时抛清晰错误。
"""
from __future__ import annotations

import random
import threading
import time
from datetime import date

from app.logger import logger
from app.services.price import DataProvider, DailyBar, NavBar

# ---- 调用限制参数（可按需调整）----
MIN_INTERVAL = (1.0, 2.0)  # 每次请求最小间隔（秒，随机 1~2）
MAX_CONCURRENCY = 4  # 并发上限（3~5 区间取 4）
MAX_RETRIES = 3  # 失败重试次数
RETRY_BASE = 0.5  # 退避基数（秒），叠加抖动
SPOT_CACHE_TTL = 30.0  # 全市场实时表缓存秒数（fund_etf_spot_em 拉取较慢）

_AK = None  # 惰性缓存的 akshare 模块


def _ak():
    global _AK
    if _AK is None:
        try:
            import akshare
        except ImportError as e:
            raise RuntimeError("未安装 akshare，请先 `uv add akshare` 再使用该数据源") from e
        _AK = akshare
    return _AK


def _strip_market(symbol: str) -> str:
    """sh513500/sz159915 → 513500；纯数字原样返回。"""
    return symbol[2:] if symbol[:2] in ("sh", "sz") else symbol


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


class AkShareProvider(DataProvider):
    """AKShare：非官方，限流/重试/并发控制。"""

    name = "akshare"
    label = "AKShare(非官方)"
    fund_types = ("etf", "otc")

    _semaphore = threading.BoundedSemaphore(MAX_CONCURRENCY)
    _lock = threading.Lock()
    _last_call = 0.0
    _spot_cache_ts = 0.0
    _spot_cache_df = None

    def _guarded(self, fn, *args, **kwargs):
        """限流 → 并发护栏 → 重试。所有 akshare 调用必须走这里。"""
        # 限流：距上次调用至少 random.uniform(1,2) 秒
        with self._lock:
            wait = random.uniform(*MIN_INTERVAL) - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
        with self._semaphore:
            for attempt in range(MAX_RETRIES):
                try:
                    return fn(*args, **kwargs)
                except Exception:  # noqa: BLE001
                    if attempt == MAX_RETRIES - 1:
                        raise
                    time.sleep((attempt + 1) * RETRY_BASE + random.uniform(0, 0.5))
        raise RuntimeError("unreachable")  # pragma: no cover

    # ---- 历史日线（etf；指数给基准用）----
    def fetch_daily(self, symbol: str, start: date, end: date) -> list[DailyBar]:
        """新浪系接口：fund_etf_hist_sina（ETF）/ stock_zh_index_daily（指数），均返回英文列。"""
        ak = _ak()
        code = _strip_market(symbol)
        if code[:1] in ("0", "3") and len(code) == 6:
            # 指数（如 000300/399006）：stock_zh_index_daily，全历史，按区间过滤
            df = self._guarded(lambda: ak.stock_zh_index_daily(symbol=symbol))
        else:
            # ETF：fund_etf_hist_sina，symbol 需带 sh/sz 前缀
            df = self._guarded(lambda: ak.fund_etf_hist_sina(symbol=symbol))
        if df is None or df.empty:
            return []
        bars: list[DailyBar] = []
        for _, row in df.iterrows():
            try:
                d = date.fromisoformat(str(row["date"]))
            except (ValueError, KeyError):
                continue
            if not (start <= d <= end):
                continue
            bars.append(
                DailyBar(
                    trade_date=d,
                    open=_f(row["open"]),
                    close=_f(row["close"]),
                    high=_f(row["high"]),
                    low=_f(row["low"]),
                    volume=_i(row["volume"]),
                )
            )
        bars.sort(key=lambda x: x.trade_date)
        logger.debug(f"数据源[{self.name}]拉取 {symbol} {start}~{end}：{len(bars)}根")
        return bars

    # ---- 实时行情（etf；全市场表 + 30s 缓存，仅买1/卖1）----
    def fetch_quotes(self, symbols: list[str]) -> list[dict]:
        ak = _ak()
        symbols = [s.strip() for s in symbols if s.strip()]
        if not symbols:
            return []
        wanted = {_strip_market(s): s for s in symbols}
        df = self._get_spot_df(ak)
        if df is None or df.empty:
            return []
        quotes: list[dict] = []
        for _, row in df.iterrows():
            code = str(row.get("代码", ""))
            if code not in wanted:
                continue
            last = _f(row.get("最新价"))
            if last is None:
                continue
            prev_close = _f(row.get("昨收"))
            change = last - prev_close if prev_close is not None else None
            change_pct = (
                round(change / prev_close * 100, 2)
                if change is not None and prev_close
                else None
            )
            bid1 = _f(row.get("买一"))
            ask1 = _f(row.get("卖一"))
            quotes.append(
                {
                    "code": code,
                    "name": str(row.get("名称", "")),
                    "last": last,
                    "price": last,
                    "prev_close": prev_close,
                    "change": change,
                    "change_pct": change_pct,
                    # 该接口只有买1/卖1，无五档（其余置 None，前端显示 '-'）
                    "bid": [bid1, None, None, None, None],
                    "ask": [ask1, None, None, None, None],
                    "bid_vol": [None] * 5,
                    "ask_vol": [None] * 5,
                    "time": None,
                }
            )
        logger.debug(f"数据源[{self.name}]拉取实时行情成功 {symbols}，返回 {len(quotes)} 条")
        return quotes

    def _get_spot_df(self, ak):
        """全市场 ETF 实时表（fund_etf_spot_em），30s TTL 缓存。

        拉取本身较慢（分页十几秒）；缓存避免每次报价都全表拉。锁外调用 _guarded 防死锁。
        """
        now = time.monotonic()
        with self._lock:
            if self._spot_cache_df is not None and now - self._spot_cache_ts <= SPOT_CACHE_TTL:
                return self._spot_cache_df
        df = self._guarded(lambda: ak.fund_etf_spot_em())
        with self._lock:
            self._spot_cache_ts = time.monotonic()
            self._spot_cache_df = df
        return df

    # ---- 场外基金净值（otc）----
    def fetch_nav(self, code: str, start: date, end: date) -> list[NavBar]:
        ak = _ak()
        unit = self._guarded(
            lambda: ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        )
        accum = self._guarded(
            lambda: ak.fund_open_fund_info_em(symbol=code, indicator="累计净值走势")
        )
        unit_map = self._nav_rows(unit, "单位净值")
        accum_map = self._nav_rows(accum, "累计净值")
        navs: list[NavBar] = []
        for d in sorted(set(unit_map) | set(accum_map)):
            if not (start <= d <= end):
                continue
            navs.append(
                NavBar(trade_date=d, unit_nav=unit_map.get(d), accum_nav=accum_map.get(d))
            )
        logger.debug(f"数据源[{self.name}]拉取 {code} {start}~{end}：{len(navs)}条净值")
        return navs

    @staticmethod
    def _nav_rows(df, val_col: str) -> dict[date, float | None]:
        """fund_open_fund_info_em 返回列：净值日期 / 指定指标列。"""
        out: dict[date, float | None] = {}
        if df is None or df.empty or "净值日期" not in df.columns:
            return out
        for _, row in df.iterrows():
            try:
                d = date.fromisoformat(str(row["净值日期"]))
            except (ValueError, KeyError):
                continue
            out[d] = _f(row.get(val_col))
        return out
