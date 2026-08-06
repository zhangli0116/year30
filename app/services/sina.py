"""新浪行情数据源。

实时行情：`hq.sinajs.cn`（GBK，需 Referer），返回五档盘口（指数无盘口，0 值需容错）。
历史日线：`quotes.sina.cn` CN_MarketDataService.getKLineData（JSONP）。

限制：新浪免费日线接口 `datalen` 上限 1023（约 4 年），只能取最近 N 根，无法翻页取更早历史。
更早的缺口由回测/覆盖检查提示，用户可切回腾讯补长历史。
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime

from app.logger import logger
from app.services.price import DailyBar, DataProvider

_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0",
}


class SinaProvider(DataProvider):
    """新浪行情：行情五档 + 历史日线（最近约 4 年）。"""

    name = "sina"
    label = "新浪行情"
    _QUOTE_URL = "https://hq.sinajs.cn/list={symbols}"
    _DAILY_URL = (
        "https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_=kl/"
        "CN_MarketDataService.getKLineData"
    )
    _DAILY_LEN = 1023  # 免费接口上限，约 4 年交易日

    # 实时行情字段（实测确认，`,` 拆分）
    _BID_IDX = [11, 13, 15, 17, 19]  # 买1..买5 价
    _BID_VOL_IDX = [10, 12, 14, 16, 18]  # 买1..买5 挂单量
    _ASK_IDX = [21, 23, 25, 27, 29]  # 卖1..卖5 价
    _ASK_VOL_IDX = [20, 22, 24, 26, 28]  # 卖1..卖5 挂单量
    _LINE_RE = re.compile(r'^var hq_str_(\w+)="(.*)"\s*;?\s*$')

    def fetch_quotes(self, symbols: list[str]) -> list[dict]:
        symbols = [s.strip() for s in symbols if s.strip()]
        if not symbols:
            return []
        url = self._QUOTE_URL.format(symbols=",".join(symbols))
        req = urllib.request.Request(url, headers=_HEADERS)
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
            symbol_key = m.group(1)
            parts = m.group(2).split(",")
            if len(parts) < 32:
                continue
            last = _f(parts[3])
            if last is None:
                continue
            prev_close = _f(parts[2])
            change = last - prev_close if prev_close is not None else None
            change_pct = (
                round(change / prev_close * 100, 2)
                if change is not None and prev_close
                else None
            )
            # code：基金取 6 位代码（与 fund_code 对齐），指数保留 symbol
            code = symbol_key[-6:] if symbol_key[-6:].isdigit() else symbol_key
            quotes.append(
                {
                    "code": code,
                    "name": parts[0],
                    "last": last,
                    "price": last,
                    "prev_close": prev_close,
                    "change": change,
                    "change_pct": change_pct,
                    "bid": [_f(parts[i]) for i in self._BID_IDX],
                    "ask": [_f(parts[i]) for i in self._ASK_IDX],
                    "bid_vol": [_f(parts[i]) for i in self._BID_VOL_IDX],
                    "ask_vol": [_f(parts[i]) for i in self._ASK_VOL_IDX],
                    "time": _sina_time(parts[30], parts[31]),
                }
            )
        logger.debug(f"数据源[{self.name}]拉取实时行情成功 {symbols}，返回 {len(quotes)} 条")
        return quotes

    def fetch_daily(self, symbol: str, start: date, end: date) -> list[DailyBar]:
        """拉取最近 datalen 根日线，只保留 [start, end]（受新浪约 4 年上限限制）。"""
        query = urllib.parse.urlencode(
            {"symbol": symbol, "scale": 240, "ma": "no", "datalen": self._DAILY_LEN}
        )
        url = f"{self._DAILY_URL}?{query}"
        req = urllib.request.Request(url, headers=_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"数据源[{self.name}]拉取日线失败 {symbol} {start}~{end}：{e}")
            return []
        try:
            rows = _parse_jsonp(text)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"数据源[{self.name}]返回解析失败 {symbol}：{e}")
            return []
        bars: list[DailyBar] = []
        for row in rows:
            try:
                d = date.fromisoformat(row.get("day", ""))
            except (ValueError, TypeError):
                continue
            if not (start <= d <= end):
                continue
            bars.append(
                DailyBar(
                    trade_date=d,
                    open=_f(row.get("open")),
                    close=_f(row.get("close")),
                    high=_f(row.get("high")),
                    low=_f(row.get("low")),
                    volume=_i(row.get("volume")),
                )
            )
        if bars and bars[0].trade_date > start:
            logger.debug(
                f"数据源[{self.name}] {symbol} 仅返回最近{len(bars)}根（起始 {bars[0].trade_date}），"
                f"早于 {start} 的历史受新浪接口限制"
            )
        logger.debug(f"数据源[{self.name}]拉取 {symbol} {start}~{end}：区间内{len(bars)}根")
        return bars


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


def _parse_jsonp(text: str) -> list[dict]:
    """去 /*...*/ 注释与 var _=fn([...]); 包装，取 JSON 数组。"""
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    return json.loads(text[start : end + 1])


def _sina_time(day: str, hms: str) -> str | None:
    """新浪时间分开在 [30]=日期(YYYY-MM-DD) [31]=时间(HH:MM:SS)，合并。"""
    if not day:
        return None
    try:
        if hms and len(hms) >= 8:
            return f"{day} {hms[:8]}"
        return f"{day} 00:00:00"
    except Exception:  # noqa: BLE001
        return None
