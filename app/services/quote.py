"""免费公开行情接口转发（腾讯行情 qt.gtimg.cn）。

接口来源为公开免费行情，仅供个人学习/记录使用，请勿高频抓取或商用。
返回格式（GBK 编码）：
    v_sh513500="1~名称~代码~最新价~昨收~今开~...~买1价~买1量~买2价~买2量~...~卖1价~...~时间~...";
按 "~" 拆分后的关键索引：
    [3]=最新价
    [9]=买1价 [11]=买2价 [13]=买3价 [15]=买4价 [17]=买5价
    [19]=卖1价 [21]=卖2价 [23]=卖3价 [25]=卖4价 [27]=卖5价
    [30]=YYYYMMDDHHMMSS
     ? openctp
"""

from __future__ import annotations

import re
import urllib.request
from datetime import datetime

_QUOTE_URL = "https://qt.gtimg.cn/q={codes}"

_LINE_RE = re.compile(r'^v_(\w+)="(.*)"\s*;?\s*$')

# 买1..买5 / 卖1..卖5 价格对应的 ~ 拆分索引
_BID_IDX = [9, 11, 13, 15, 17]
_ASK_IDX = [19, 21, 23, 25, 27]


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_quotes(codes: list[str], timeout: int = 8) -> list[dict]:
    """批量获取若干基金/ETF 的行情与五档盘口。

    codes: 如 ["513500", "513100"]，统一按 sh 前缀取上交所行情。
    返回: [{"code","name","last","price","bid","ask","time"}]，
        price 同 last（最新价）；bid/ask 为买1..买5、卖1..卖5，缺失时为 None。
    """
    codes = [c.strip() for c in codes if c.strip()]
    if not codes:
        return []

    symbols = ",".join(f"sh{c}" for c in codes)
    url = _QUOTE_URL.format(codes=symbols)

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except Exception:
        # 网络异常/超时时返回空，由调用方决定如何提示
        return []

    text = raw.decode("gbk", errors="ignore")
    quotes: list[dict] = []
    for line in text.splitlines():
        m = _LINE_RE.match(line.strip())
        if not m:
            continue
        parts = m.group(2).split("~")
        if len(parts) < 31:
            continue
        last = _to_float(parts[3])
        if last is None:
            continue
        quotes.append(
            {
                "code": parts[2],
                "name": parts[1],
                "last": last,
                "price": last,
                "bid": [_to_float(parts[i]) for i in _BID_IDX],
                "ask": [_to_float(parts[i]) for i in _ASK_IDX],
                "time": _format_time(parts[30]),
            }
        )
    return quotes


def _format_time(raw: str) -> str | None:
    """把 YYYYMMDDHHMMSS 转成 2026-08-06 14:15:20。"""
    if not raw or len(raw) < 14 or not raw.isdigit():
        return None
    try:
        dt = datetime.strptime(raw, "%Y%m%d%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
