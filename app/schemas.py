from datetime import date, datetime
from decimal import Decimal
from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# =========================================================
# 统一响应包装：{code, message, data}
# code == 0 表示成功，非 0 表示业务错误
# =========================================================

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: Optional[T] = None


class PageData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


def success(data: Any = None, message: str = "ok") -> ApiResponse:
    return ApiResponse(code=0, message=message, data=data)


def error(code: int, message: str) -> ApiResponse:
    return ApiResponse(code=code, message=message, data=None)


# =========================================================
# 业务错误码约定
# 40000 参数/校验错误，40001 基金代码重复，40002 删除被关联数据拦截，
# 40003 关联基金不存在，40400 基金不存在，40401 购买记录不存在
# =========================================================

# =========================================================
# PurchaseRecord 相关
# =========================================================


class PurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    quarter_id: Optional[int] = None
    fund_id: int
    purchase_date: date
    price: Decimal
    hands: int
    shares_per_hand: int
    total_amount: Decimal
    fee: Decimal
    note: Optional[str] = None
    created_at: datetime


class PurchaseCreate(BaseModel):
    fund_id: int = Field(..., description="基金ID")
    type: Literal["buy", "sell"] = Field("buy", description="交易类型：buy=买入 / sell=卖出")
    purchase_date: date = Field(..., description="购买日期")
    price: Decimal = Field(..., gt=0, decimal_places=4, description="每股价格")
    hands: int = Field(..., gt=0, description="手数（卖出时也为手数）")
    shares_per_hand: int = Field(100, gt=0, description="每手份数")
    total_amount: Optional[Decimal] = Field(
        None, gt=0, decimal_places=2, description="金额：买入=本金+手续费；卖出=成交额，不传则自动计算"
    )
    fee: Optional[Decimal] = Field(
        None, ge=0, decimal_places=2, description="手续费(元)，不传则按费率计算（默认 0.03%，不足 5 元按 5 元）"
    )
    fee_rate: Optional[Decimal] = Field(
        None, ge=0, le=100, decimal_places=4, description="手续费费率(%)，默认 0.03"
    )
    note: Optional[str] = Field(None, max_length=255, description="备注")
    quarter_id: Optional[int] = Field(None, description="关联季度汇总ID")


class PurchaseUpdate(BaseModel):
    fund_id: Optional[int] = Field(None, description="基金ID")
    type: Optional[Literal["buy", "sell"]] = Field(None, description="交易类型")
    purchase_date: Optional[date] = Field(None, description="购买日期")
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=4, description="每股价格")
    hands: Optional[int] = Field(None, gt=0, description="购买手数")
    shares_per_hand: Optional[int] = Field(None, gt=0, description="每手份数")
    total_amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2, description="花费总金额")
    fee: Optional[Decimal] = Field(None, ge=0, decimal_places=2, description="手续费(元)")
    fee_rate: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=4, description="手续费费率(%)，默认 0.03")
    note: Optional[str] = Field(None, max_length=255, description="备注")
    quarter_id: Optional[int] = Field(None, description="关联季度汇总ID")


# =========================================================
# Quarter 季度汇总 相关
# =========================================================


class QuarterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    period: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Decimal
    equity_amount: Decimal
    total_fee: Decimal
    cash_amount: Decimal
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class QuarterDetail(QuarterOut):
    purchases: list[PurchaseOut] = Field(default_factory=list, description="本季购买记录")


class QuarterCreate(BaseModel):
    period: str = Field(..., min_length=1, max_length=10, description="周期标识，如 2026Q3")
    start_date: Optional[date] = Field(None, description="周期开始日期")
    end_date: Optional[date] = Field(None, description="周期结束日期")
    budget: Decimal = Field(..., gt=0, decimal_places=2, description="本周期预算")
    note: Optional[str] = Field(None, max_length=255, description="备注")
    # equity_amount / cash_amount 由后端根据购买记录计算，不开放写入


class QuarterUpdate(BaseModel):
    """季度更新：仅允许修改 budget，cash_amount 由后端自动重算（= budget − equity_amount）。"""

    budget: Optional[Decimal] = Field(None, gt=0, decimal_places=2, description="本周期预算（唯一可改字段）")


# =========================================================
# Fund 相关
# =========================================================


class FundBase(BaseModel):
    fund_code: str = Field(..., min_length=1, max_length=10, description="基金代码")
    fund_name: str = Field(..., min_length=1, max_length=64, description="基金名称")
    exchange: str = Field("上交所", max_length=16, description="交易所")
    currency: str = Field("CNY", max_length=3, description="币种")
    target_ratio: Optional[Decimal] = Field(
        None, ge=0, le=100, decimal_places=2, description="目标配置比例(%)，NULL=未设置"
    )


class FundCreate(FundBase):
    pass


class FundUpdate(BaseModel):
    fund_code: Optional[str] = Field(None, min_length=1, max_length=10, description="基金代码")
    fund_name: Optional[str] = Field(None, min_length=1, max_length=64, description="基金名称")
    exchange: Optional[str] = Field(None, max_length=16, description="交易所")
    currency: Optional[str] = Field(None, max_length=3, description="币种")
    target_ratio: Optional[Decimal] = Field(
        None, ge=0, le=100, decimal_places=2, description="目标配置比例(%)，NULL=未设置"
    )


class FundOut(FundBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class FundDetail(FundOut):
    purchases: list[PurchaseOut] = Field(default_factory=list, description="该基金的购买记录")


class FundSummary(BaseModel):
    """每只基金的汇总统计（含配置比例）。"""

    fund_id: int
    fund_code: str
    fund_name: str
    buy_count: int
    total_shares: int
    total_cost: Decimal
    avg_cost: Optional[Decimal] = None
    target_ratio: Optional[Decimal] = None
    real_ratio: Optional[Decimal] = None


class SummaryOut(BaseModel):
    """全部基金汇总：基金明细 + 总投资 + 总资金 + 现金目标比例。"""

    funds: list[FundSummary]
    total_invested: Decimal
    total_capital: Optional[Decimal] = None
    cash_ratio: Optional[Decimal] = None


# =========================================================
# FundPrice 历史价格 相关
# =========================================================


class PriceBarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fund_id: int
    trade_date: date
    open_price: Optional[Decimal] = None
    high_price: Optional[Decimal] = None
    low_price: Optional[Decimal] = None
    close_price: Decimal
    volume: Optional[int] = None
    source: str = "tencent"


class PriceSyncIn(BaseModel):
    fund_id: int = Field(..., description="基金ID")
    start_date: date = Field(..., description="起始日期")
    end_date: date = Field(..., description="结束日期")
    source: str = Field("tencent", description="数据源标识，如 tencent")


class PriceSyncOut(BaseModel):
    source: str
    fetched: int = Field(0, description="接口拉取条数")
    inserted: int = Field(0, description="新增入库条数")
    existing: int = Field(0, description="已存在条数")
    range_start: date
    range_end: date


class PriceSegment(BaseModel):
    start: date
    end: date


class PriceCheckOut(BaseModel):
    fund_id: int
    start_date: date
    end_date: date
    missing_days: int = Field(0, description="缺失的自然日总数")
    segments: list[PriceSegment] = Field(default_factory=list, description="缺失的时间段（连续的日历日缺口）")


# =========================================================
# FundHoldingDaily 每日权益流水 相关
# =========================================================


class HoldingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fund_id: int
    trade_date: date
    total_shares: int
    total_hands: int
    price: Decimal
    equity_amount: Decimal


class HoldingGenerateIn(BaseModel):
    fund_id: int = Field(..., description="基金ID")
    start_date: date = Field(..., description="起始日期")
    end_date: date = Field(..., description="结束日期")


class HoldingGenerateOut(BaseModel):
    fund_id: int
    generated: int = Field(0, description="生成/更新的日线条数")
    range_start: date
    range_end: date


class HoldingCheckOut(BaseModel):
    fund_id: int
    start_date: date
    end_date: date
    missing_days: int = Field(0, description="缺失的交易日数（该区间有历史价但无流水）")
    missing_start: Optional[date] = None
    missing_end: Optional[date] = None


class HoldingTotalOut(BaseModel):
    """某日全部基金权益市值之和（来自每日权益流水）。"""

    trade_date: date
    total_equity: Decimal


# =========================================================
# FundCashDaily 每日现金流 相关
# =========================================================


class CashOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trade_date: date
    increment: Decimal
    cash_amount: Decimal


class CashGenerateIn(BaseModel):
    start_date: date = Field(..., description="起始日期")
    end_date: date = Field(..., description="结束日期")


class CashGenerateOut(BaseModel):
    generated: int = Field(0, description="生成的日线条数")
    range_start: date
    range_end: date


class CashCheckOut(BaseModel):
    start_date: date
    end_date: date
    missing_days: int = Field(0, description="缺失的日历日数（未生成现金流的天数）")
    missing_start: Optional[date] = None
    missing_end: Optional[date] = None


# =========================================================
# 行情（外部公开接口转发）
# =========================================================


class QuoteOut(BaseModel):
    code: str
    name: str
    price: Optional[float] = None  # 最新价
    last: Optional[float] = None  # 最新价
    bid: list[Optional[float]] = Field(default_factory=list)  # 买1..买5
    ask: list[Optional[float]] = Field(default_factory=list)  # 卖1..卖5
    time: Optional[str] = None


class QuoteListOut(BaseModel):
    quotes: list[QuoteOut]
    source: str = "tencent"
