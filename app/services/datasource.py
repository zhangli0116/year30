"""数据源注册表 + 「当前数据源」管理 + fund→symbol 解析。

所有外部取数（实时行情 / 历史日线 / 基准指数 / 每日自动同步 / XIRR·再平衡实时价）
统一走 `get_provider(db)` 获取当前数据源。切换通过 `GET/PUT /api/v1/datasource`，
持久化到 `app_setting`（键 `datasource.provider`）。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud, models
from app.services.price import DataProvider, TencentProvider

KEY_PROVIDER = "datasource.provider"
DEFAULT_PROVIDER = "tencent"


def _registry() -> dict[str, DataProvider]:
    """懒构造避免循环导入：price 不依赖本模块，sina 依赖 price。"""
    from app.services.sina import SinaProvider

    return {
        "tencent": TencentProvider(),
        "sina": SinaProvider(),
    }


def list_providers() -> list[dict]:
    return [{"name": name, "label": p.label} for name, p in _registry().items()]


def get_provider_by_name(name: str) -> DataProvider | None:
    return _registry().get(name)


def get_provider(db: Session | None = None) -> DataProvider:
    """读取「当前数据源」；无 db 或未设置/值非法时回退默认。"""
    name = DEFAULT_PROVIDER
    if db is not None:
        stored = crud.app_setting.get_setting(db, KEY_PROVIDER)
        if stored in _registry():
            name = stored
    return _registry()[name]


def set_provider(db: Session, name: str) -> DataProvider:
    """设置「当前数据源」，返回该 Provider；未知数据源抛 ValueError。"""
    registry = _registry()
    if name not in registry:
        raise ValueError(f"未知数据源：{name}")
    crud.app_setting.set_setting(db, KEY_PROVIDER, name)
    return registry[name]


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
