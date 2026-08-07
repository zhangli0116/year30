"""数据源抽象与腾讯 Provider。

统一抽象：`DataProvider` 提供两类取数——
    历史日线 `fetch_daily(symbol, start, end)`（基金或指数，symbol=完整行情代码）
    实时行情 `fetch_quotes(symbols)`（含五档盘口）
注册表与「当前数据源」管理见 `app/services/datasource.py`；本项目所有外部取数统一走它。

新增数据源：继承 `DataProvider` 实现两个方法，注册进 `datasource._registry()`。
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.logger import logger

# 标的类型：etf=场内(ETF/LOF，交易所K线+盘口) / otc=场外基金(只有净值)
FUND_TYPE_ETF = "etf"
FUND_TYPE_OTC = "otc"

# 日线数据：一天一根 K 线（OHLC + 成交量）
@dataclass
class DailyBar:
    trade_date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None


# 场外基金净值：一天一个单位净值（+累计净值），无 OHLC
@dataclass
class NavBar:
    trade_date: date
    unit_nav: float | None = None
    accum_nav: float | None = None


class DataProvider(ABC):
    """统一数据源抽象：历史日线 + 实时行情（+ 场外净值）。"""

    name: str = "base"
    label: str = "默认数据源"
    # 该数据源可服务的 fund_type（etf / otc）。空 = 不限制。
    fund_types: tuple[str, ...] = ()

    @abstractmethod
    def fetch_daily(self, symbol: str, start: date, end: date) -> list[DailyBar]:
        """拉取 [start, end] 历史日线（基金或指数，含起止日，不含停牌日）。"""

    @abstractmethod
    def fetch_quotes(self, symbols: list[str]) -> list[dict]:
        """实时行情（含五档盘口）。标准键：
        code/name/last/price/prev_close/change/change_pct/bid[5]/ask[5]/bid_vol[5]/ask_vol[5]/time"""

    def fetch_nav(self, code: str, start: date, end: date) -> list[NavBar]:
        """场外基金净值（otc 数据源实现）；etf 数据源抛 NotImplementedError。"""
        raise NotImplementedError(f"数据源[{self.name}]不支持场外基金净值")

    def __str__(self) -> str:
        return f"{self.name}({self.label})"


class TencentProvider(DataProvider):
    """腾讯行情：日线走 fqkline/get（前复权，窗口分页），实时走 qt.gtimg.cn（五档）。"""

    name = "tencent"
    label = "腾讯行情"
    fund_types = (FUND_TYPE_ETF,)
    _KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    _KLINE_COUNT = 2000  # 单次最大条数（实测 count>2000 返回 param error）
    _QUOTE_URL = "https://qt.gtimg.cn/q={symbols}"

    # 实时行情：qt.gtimg.cn 按 ~ 拆分的关键索引（买1..5/卖1..5 价与挂单量）
    _BID_IDX = [9, 11, 13, 15, 17]
    _BID_VOL_IDX = [10, 12, 14, 16, 18]
    _ASK_IDX = [19, 21, 23, 25, 27]
    _ASK_VOL_IDX = [20, 22, 24, 26, 28]
    _LINE_RE = re.compile(r'^v_(\w+)="(.*)"\s*;?\s*$')

    # ---- 实时行情 ----
    def fetch_quotes(self, symbols: list[str]) -> list[dict]:
        symbols = [s.strip() for s in symbols if s.strip()]
        if not symbols:
            return []
        url = self._QUOTE_URL.format(symbols=",".join(symbols))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"数据源[{self.name}]拉取实时行情失败 {symbols}：{e}")
            return []
        text = raw.decode("gbk", errors="ignore")
        quotes: list[dict] = []
        for line in text.splitlines():
            m = self._LINE_RE.match(line.strip())
            if not m:
                continue
            parts = m.group(2).split("~")
            if len(parts) < 31:
                continue
            last = _to_float(parts[3])
            if last is None:
                continue
            prev_close = _to_float(parts[4])
            change = last - prev_close if prev_close is not None else None
            change_pct = (
                round(change / prev_close * 100, 2)
                if change is not None and prev_close
                else None
            )
            quotes.append(
                {
                    "code": parts[2],
                    "name": parts[1],
                    "last": last,
                    "price": last,
                    "prev_close": prev_close,
                    "change": change,
                    "change_pct": change_pct,
                    "bid": [_to_float(parts[i]) for i in self._BID_IDX],
                    "ask": [_to_float(parts[i]) for i in self._ASK_IDX],
                    "bid_vol": [_to_float(parts[i]) for i in self._BID_VOL_IDX],
                    "ask_vol": [_to_float(parts[i]) for i in self._ASK_VOL_IDX],
                    "time": _format_time(parts[30]),
                }
            )
        logger.debug(f"数据源[{self.name}]拉取实时行情成功 {symbols}，返回 {len(quotes)} 条")
        return quotes

    # ---- 历史日线 ----
    def fetch_daily(self, symbol: str, start: date, end: date) -> list[DailyBar]:
        """窗口分页拉取 [start, end] 完整日线，返回升序去重。

        腾讯 K 线一次最多返回最近 2000 根；把结束日回退到上次首日前一天继续，
        直到覆盖到 start 为止（修复长区间静默丢数据的问题）。
        """
        bars: list[DailyBar] = []
        cur_end = end
        while cur_end >= start:
            page = self._fetch_page(symbol, start, cur_end)
            if not page:
                break
            bars.extend(page)
            first = page[0].trade_date
            if first <= start:
                break
            cur_end = first - timedelta(days=1)
        # 去重 + 升序 + 落在区间内
        seen: set[date] = set()
        out: list[DailyBar] = []
        for b in sorted(bars, key=lambda x: x.trade_date):
            if b.trade_date in seen or not (start <= b.trade_date <= end):
                continue
            seen.add(b.trade_date)
            out.append(b)
        return out

    def _fetch_page(self, symbol: str, start: date, end: date) -> list[DailyBar]:
        param = f"{symbol},day,{start.isoformat()},{end.isoformat()},{self._KLINE_COUNT},qfq"
        url = f"{self._KLINE_URL}?param={urllib.parse.quote(param)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"数据源[{self.name}]拉取日线失败 {symbol} {start}~{end}：{e}")
            return []
        try:
            data = json.loads(text).get("data", {}).get(symbol, {})
        except Exception:
            logger.warning(f"数据源[{self.name}]返回解析失败 {symbol}")
            return []
        rows = data.get("qfqday") or data.get("day") or []
        bars: list[DailyBar] = []
        for row in rows:
            if len(row) < 6:
                continue
            try:
                d = date.fromisoformat(row[0])
            except ValueError:
                continue
            bars.append(
                DailyBar(
                    trade_date=d,
                    open=_f(row[1]),
                    close=_f(row[2]),
                    high=_f(row[3]),
                    low=_f(row[4]),
                    volume=_i(row[5]),
                )
            )
        # 只保留落在区间内的
        filtered = [b for b in bars if start <= b.trade_date <= end]
        logger.debug(f"数据源[{self.name}]拉取 {symbol} {start}~{end}：原始{len(bars)} 区间内{len(filtered)}")
        return filtered


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


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_time(raw: str) -> str | None:
    """把 YYYYMMDDHHMMSS 转成 2026-08-06 14:15:20。"""
    if not raw or len(raw) < 14 or not raw.isdigit():
        return None
    try:
        dt = datetime.strptime(raw, "%Y%m%d%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
