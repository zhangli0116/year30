"""东方财富场外基金净值数据源。

取数路径：`api.fund.eastmoney.com/f10/lsjz`（天天基金历史净值接口，需 Referer）。
只服务场外基金（`fund_type='otc'`）的净值 `fetch_nav(code, start, end)`，
无交易所 K 线/盘口——`fund_types=("otc",)`，在数据源配置里作为 otc 组的选项之一。

接口说明（实测）：
    - 需 Header `Referer: http://fundf10.eastmoney.com/`，否则 403
    - `pageSize` 传大值无效，每页固定返回 20 条；按 pageIndex 翻页
    - `startDate`/`endDate` 参数有效；返回按日期降序
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date

from app.logger import logger
from app.services.price import DataProvider, DailyBar, NavBar

_URL = "https://api.fund.eastmoney.com/f10/lsjz"
_PAGE_SIZE = 20  # 接口固定每页 20 条（传更大值也无效）


class EastMoneyNavProvider(DataProvider):
    """东财场外基金净值：只提供 fetch_nav，无 K 线/盘口。"""

    name = "eastmoney"
    label = "东财净值"
    fund_types = ("otc",)

    def fetch_daily(self, symbol, start, end):  # noqa: ARG002
        raise NotImplementedError("东财净值仅服务场外基金净值，无 K 线（fetch_daily 不可用）")

    def fetch_quotes(self, symbols):  # noqa: ARG002
        raise NotImplementedError("东财净值仅服务场外基金净值，无实时盘口（fetch_quotes 不可用）")

    def __init__(self) -> None:
        self._req_headers = {
            "Referer": "http://fundf10.eastmoney.com/",
            "User-Agent": "Mozilla/5.0",
        }

    def fetch_nav(self, code: str, start: date, end: date) -> list[NavBar]:
        """拉取场外基金 [start, end] 每日净值，升序去重。

        东财按日期降序分页（每页 20 条）；从 pageIndex=1 翻页直到
        任一页返回 <20 条或最早日期 ≤ start（已覆盖区间开头）为止。
        """
        navs: list[NavBar] = []
        page = 1
        while True:
            rows = self._fetch_page(code, start, end, page)
            if not rows:
                break
            navs.extend(rows)
            first = rows[0].trade_date
            if len(rows) < _PAGE_SIZE or first <= start:
                break
            page += 1
            if page > 5000:  # 防御：净值历史最多约 20 年，不应超过
                logger.warning(f"数据源[{self.name}] {code} 翻页超过 5000 页，强制停止")
                break
        # 去重 + 升序 + 落在区间内
        seen: set[date] = set()
        out: list[NavBar] = []
        for b in sorted(navs, key=lambda x: x.trade_date):
            if b.trade_date in seen or not (start <= b.trade_date <= end):
                continue
            seen.add(b.trade_date)
            out.append(b)
        logger.debug(f"数据源[{self.name}]拉取 {code} {start}~{end}：区间内{len(out)}条")
        return out

    def _fetch_page(self, code: str, start: date, end: date, page: int) -> list[NavBar]:
        query = urllib.parse.urlencode(
            {
                "fundCode": code,
                "pageIndex": page,
                "pageSize": _PAGE_SIZE,
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
            }
        )
        url = f"{_URL}?{query}"
        req = urllib.request.Request(url, headers=self._req_headers)
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"数据源[{self.name}]拉取净值失败 {code} {start}~{end} 第{page}页：{e}")
            return []
        try:
            data = json.loads(text).get("Data") or {}
            rows = data.get("LSJZList") or []
        except Exception:  # noqa: BLE001
            logger.warning(f"数据源[{self.name}]返回解析失败 {code} 第{page}页")
            return []
        navs: list[NavBar] = []
        for row in rows:
            try:
                d = date.fromisoformat(row.get("FSRQ", ""))
            except ValueError:
                continue
            navs.append(
                NavBar(
                    trade_date=d,
                    unit_nav=_f(row.get("DWJZ")),
                    accum_nav=_f(row.get("LJJZ")),
                )
            )
        return navs


def _f(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
