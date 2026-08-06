"""基金历史价格数据源抽象层。

新增数据源时：继承 PriceSource，实现 fetch_daily，并注册进 SOURCES。
前端通过「数据源」下拉指定 source，后端按名称取对应实现。
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from app.logger import logger

# 日线数据：一天一根 K 线（OHLC + 成交量）
@dataclass
class DailyBar:
    trade_date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None


class PriceSource(ABC):
    """价格数据源抽象基类。"""

    name: str = "base"
    label: str = "默认数据源"

    @abstractmethod
    def fetch_daily(self, fund_code: str, start: date, end: date) -> list[DailyBar]:
        """拉取指定基金在 [start, end] 区间内的日线数据（含起止日，不含停牌日）。"""

    def __str__(self) -> str:
        return f"{self.name}({self.label})"


class TencentPriceSource(PriceSource):
    """腾讯行情日线（前复权），公开免费接口。"""

    name = "tencent"
    label = "腾讯行情（前复权）"
    _URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

    def fetch_daily(self, fund_code: str, start: date, end: date) -> list[DailyBar]:
        # 统一按上交所前缀取数（本项目基金都在上交所）
        symbol = f"sh{fund_code}"
        param = f"{symbol},day,{start.isoformat()},{end.isoformat()},1000,qfq"
        url = f"{self._URL}?param={urllib.parse.quote(param)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"数据源[{self.name}]拉取日线失败 {fund_code} {start}~{end}：{e}")
            return []
        try:
            data = json.loads(text).get("data", {}).get(symbol, {})
        except Exception:
            logger.warning(f"数据源[{self.name}]返回解析失败 {fund_code}")
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
        logger.debug(f"数据源[{self.name}]拉取 {fund_code} {start}~{end}：原始{len(bars)} 区间内{len(filtered)}")
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


# 数据源注册表：前端按名称选择
SOURCES: dict[str, PriceSource] = {
    src.name: src for src in [TencentPriceSource()]
}


def list_sources() -> list[dict]:
    return [{"name": s.name, "label": s.label} for s in SOURCES.values()]


def get_source(name: str | None) -> PriceSource | None:
    if not name:
        return SOURCES.get("tencent")
    return SOURCES.get(name)
