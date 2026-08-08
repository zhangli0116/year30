"""数据源注册表 + 按 fund_type 的「当前数据源」管理 + fund→symbol 解析。

所有外部取数（实时行情 / 历史日线 / 场外净值 / 基准指数 / 每日自动同步 / XIRR·再平衡实时价）
统一走 `get_provider(db, fund_type)` 获取该标的类型对应的数据源。

配置按 fund_type 分别存储（app_setting 键 `datasource.provider.{fund_type}`）：
    - etf（场内 ETF/LOF）/ stock（A股股票）：腾讯 / 新浪 / AKShare
    - otc（场外基金）：东财净值 / AKShare
切换通过 `GET/PUT /api/v1/datasource`，body 为 `{fund_type, provider}`。
兼容旧键 `datasource.provider`（etf 类型未设新键时回退读取）。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud, models
from app.services.price import (
    FUND_TYPE_ETF,
    FUND_TYPE_OTC,
    FUND_TYPE_STOCK,
    DataProvider,
    TencentProvider,
)

KEY_PROVIDER = "datasource.provider"  # 旧全局键（仅兼容 etf 读取）
KEY_PROVIDER_PREFIX = "datasource.provider."

# 各 fund_type 的展示名（设置页分组标题）
FUND_TYPE_LABELS = {
    FUND_TYPE_ETF: "场内 ETF/LOF",
    FUND_TYPE_STOCK: "A股股票",
    FUND_TYPE_OTC: "场外基金",
}

# 各 fund_type 默认数据源（未配置/值非法时回退）
DEFAULT_PROVIDER = {
    FUND_TYPE_ETF: "tencent",
    FUND_TYPE_STOCK: "tencent",
    FUND_TYPE_OTC: "eastmoney",
}


def _registry() -> dict[str, DataProvider]:
    """懒构造避免循环导入：price 不依赖本模块，sina/eastmoney/akshare 依赖 price。"""
    from app.services.akshare import AkShareProvider
    from app.services.eastmoney import EastMoneyNavProvider
    from app.services.sina import SinaProvider

    return {
        "tencent": TencentProvider(),
        "sina": SinaProvider(),
        "eastmoney": EastMoneyNavProvider(),
        "akshare": AkShareProvider(),
    }


def list_providers() -> list[dict]:
    return [
        {"name": name, "label": p.label, "fund_types": list(p.fund_types)}
        for name, p in _registry().items()
    ]


def get_provider_by_name(name: str) -> DataProvider | None:
    return _registry().get(name)


def _provider_key(fund_type: str) -> str:
    return f"{KEY_PROVIDER_PREFIX}{fund_type}"


def get_provider(db: Session | None = None, fund_type: str | None = None) -> DataProvider:
    """读取指定 fund_type 的当前数据源；无 db/未设置/值非法时回退该类型默认。

    fund_type=None → 默认 etf（兼容旧调用）。etf 类型兼容旧键 `datasource.provider`。
    """
    registry = _registry()
    ft = fund_type or FUND_TYPE_ETF
    if ft not in DEFAULT_PROVIDER:
        ft = FUND_TYPE_ETF
    name = None
    if db is not None:
        name = crud.app_setting.get_setting(db, _provider_key(ft))
        if name is None and ft == FUND_TYPE_ETF:
            name = crud.app_setting.get_setting(db, KEY_PROVIDER)  # 兼容旧键
    if not (name and name in registry and ft in registry[name].fund_types):
        name = DEFAULT_PROVIDER[ft]
    return registry[name]


def set_provider(db: Session, fund_type: str, name: str) -> DataProvider:
    """设置某 fund_type 的当前数据源；未知数据源/类型不匹配抛 ValueError。"""
    registry = _registry()
    ft = fund_type or FUND_TYPE_ETF
    if name not in registry:
        raise ValueError(f"未知数据源：{name}")
    if ft not in registry[name].fund_types:
        raise ValueError(f"数据源 {name} 不支持标的类型 {ft}")
    crud.app_setting.set_setting(db, _provider_key(ft), name)
    return registry[name]


def list_type_configs(db: Session) -> list[dict]:
    """设置页展示：按 fund_type 分组，各组可选数据源 + 当前值。"""
    registry = _registry()
    out: list[dict] = []
    for ft, label in FUND_TYPE_LABELS.items():
        options = [
            {"name": n, "label": p.label, "fund_types": list(p.fund_types)}
            for n, p in registry.items()
            if ft in p.fund_types
        ]
        out.append(
            {
                "fund_type": ft,
                "label": label,
                "options": options,
                "current": get_provider(db, ft).name,
            }
        )
    return out


# ---- fund → symbol 解析（完整行情代码）----
def fund_symbol(exchange: str | None, code: str) -> str:
    """6 位基金代码 → 完整 symbol；按交易所 sh/sz，未知回退首位启发式。

    修复：现有代码对所有基金一律强制 `sh` 前缀，深交所标的（如 159920）会取错。
    """
    if exchange:
        if "深" in exchange:
            return f"sz{code}"
        if "上" in exchange:
            return f"sh{code}"
    return f"sh{code}" if code[:1] in ("5", "6") else f"sz{code}"


def resolve_symbols(db: Session, codes: list[str]) -> dict[str, str]:
    """批量把 6 位基金代码解析为完整 symbol（查 fund 表 exchange，未知回退启发式）。"""
    codes = [c for c in codes if c]
    if not codes:
        return {}
    exch_map = dict(
        db.execute(
            select(models.Fund.fund_code, models.Fund.exchange).where(
                models.Fund.fund_code.in_(codes)
            )
        ).all()
    )
    return {c: fund_symbol(exch_map.get(c), c) for c in codes}
