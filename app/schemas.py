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
    plan_id: int = Field(..., description="所属方案ID")
    fund_id: int = Field(..., description="基金ID")
    type: Literal["buy", "sell"] = Field("buy", description="交易类型：buy=买入 / sell=卖出")
    purchase_date: date = Field(..., description="购买日期")
    price: Decimal = Field(..., gt=0, decimal_places=4, description="每股价格")
    hands: int = Field(..., gt=0, description="手数（卖出时也为手数）")
    shares_per_hand: int = Field(100, gt=0, description="每手份数")
    total_amount: Optional[Decimal] = Field(
        None, gt=0, decimal_places=2, description="权益金额 = 本金/成交额（不含手续费），不传则自动计算"
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
    plan_id: Optional[int] = Field(None, description="所属方案ID")
    fund_id: Optional[int] = Field(None, description="基金ID")
    type: Optional[Literal["buy", "sell"]] = Field(None, description="交易类型")
    purchase_date: Optional[date] = Field(None, description="购买日期")
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=4, description="每股价格")
    hands: Optional[int] = Field(None, gt=0, description="购买手数")
    shares_per_hand: Optional[int] = Field(None, gt=0, description="每手份数")
    total_amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2, description="权益金额 = 本金/成交额（不含手续费）")
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
    plan_id: int = Field(..., description="所属方案ID")
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
    fund_type: str = Field("etf", max_length=16, description="标的类型：etf=场内(ETF/LOF，K线) / otc=场外基金(净值)")
    currency: str = Field("CNY", max_length=3, description="币种")


class FundCreate(FundBase):
    pass


class FundUpdate(BaseModel):
    fund_code: Optional[str] = Field(None, min_length=1, max_length=10, description="基金代码")
    fund_name: Optional[str] = Field(None, min_length=1, max_length=64, description="基金名称")
    exchange: Optional[str] = Field(None, max_length=16, description="交易所")
    fund_type: Optional[str] = Field(None, max_length=16, description="标的类型：etf / otc")
    currency: Optional[str] = Field(None, max_length=3, description="币种")


class FundOut(FundBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class FundDetail(FundOut):
    purchases: list[PurchaseOut] = Field(default_factory=list, description="该基金的购买记录")


class FundSummary(BaseModel):
    """每只基金的汇总统计（含该方案内的目标占比）。"""

    fund_id: int
    fund_code: str
    fund_name: str
    buy_count: int
    total_shares: int
    total_cost: Decimal
    avg_cost: Optional[Decimal] = None
    target_ratio: Optional[Decimal] = None  # 该方案内 plan_fund 目标占比
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
    source: Optional[str] = Field(None, description="数据源标识（可选覆盖），缺省用「当前数据源」")


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
    plan_id: Optional[int] = Field(None, description="方案ID，缺省用默认方案")
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
    plan_id: Optional[int] = Field(None, description="方案ID，缺省用默认方案")
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
    prev_close: Optional[float] = None  # 昨收
    change: Optional[float] = None  # 涨跌额
    change_pct: Optional[float] = None  # 涨跌幅(%)
    bid: list[Optional[float]] = Field(default_factory=list)  # 买1..买5 价
    ask: list[Optional[float]] = Field(default_factory=list)  # 卖1..卖5 价
    bid_vol: list[Optional[float]] = Field(default_factory=list)  # 买1..买5 挂单量(手)
    ask_vol: list[Optional[float]] = Field(default_factory=list)  # 卖1..卖5 挂单量(手)
    time: Optional[str] = None


class QuoteListOut(BaseModel):
    quotes: list[QuoteOut]
    source: str = "tencent"


# =========================================================
# DcaPlan 定投方案
# =========================================================


class PlanFundIn(BaseModel):
    fund_id: int = Field(..., description="基金ID")
    target_ratio: Decimal = Field(..., ge=0, le=100, decimal_places=2, description="该方案下此标的目标占比(%)")


class PlanCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="方案名")
    start_date: Optional[date] = Field(None, description="起始日期（首次定投，间隔基准）")
    interval_days: int = Field(91, ge=1, description="定投间隔天数（如 91 = 约每季）")
    tolerance_days: int = Field(5, ge=0, description="容错天数：下次窗口 = 基准 + 间隔 ± 容错")
    amount: Decimal = Field(0, ge=0, decimal_places=2, description="每次投入金额")
    rebalance_strategy: Literal["buy", "sell", "check"] = "check"
    cash_ratio: Decimal = Field(0, ge=0, le=100, decimal_places=2, description="现金目标比例(%)")
    active: bool = True
    funds: list[PlanFundIn] = Field(default_factory=list, description="标的配置")


class PlanUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    start_date: Optional[date] = None
    interval_days: Optional[int] = Field(None, ge=1)
    tolerance_days: Optional[int] = Field(None, ge=0)
    amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    rebalance_strategy: Optional[Literal["buy", "sell", "check"]] = None
    cash_ratio: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=2)
    active: Optional[bool] = None
    funds: Optional[list[PlanFundIn]] = None


class PlanFundOut(BaseModel):
    fund_id: int
    fund_code: str
    fund_name: str
    target_ratio: Decimal


class PlanNextDue(BaseModel):
    """下次定投窗口：以起始日期为基准 + k×间隔天数，窗口 = 计划日 ± 容错。"""

    scheduled: date
    window_start: date
    window_end: date
    status: Literal["upcoming", "due", "overdue"]


class PlanOut(BaseModel):
    id: int
    name: str
    start_date: Optional[date] = None
    interval_days: int
    tolerance_days: int
    amount: Decimal
    rebalance_strategy: str
    cash_ratio: Decimal
    active: bool
    next_due: Optional[PlanNextDue] = None
    funds: list[PlanFundOut] = Field(default_factory=list)


# =========================================================
# XIRR 年化收益
# =========================================================


class XirrFundOut(BaseModel):
    fund_id: int
    fund_code: str
    fund_name: str
    xirr: Optional[float] = None  # 年化收益（小数，如 0.1234=12.34%），None=不可算
    current_mv: float = 0  # 期末市值
    invested: float = 0  # 累计投入（买入金额，含手续费）


class XirrAccountOut(BaseModel):
    xirr: Optional[float] = None  # 全账户资金加权年化（短期会被放大，需结合 span_days 看）
    twr: Optional[float] = None  # 时间加权收益率（期间非年化，剥离投入时点，短期稳定）
    span_days: int = 0  # 持有天数（首次投入至今），用于年化标注
    invested: float = 0  # 累计投入 = Σ 季度预算
    current_value: float = 0  # 期末总资产 = 权益市值 + 现金
    gain: float = 0  # 收益额
    gain_pct: Optional[float] = None  # 收益率(%)
    start_date: Optional[str] = None  # 首次投入日期


class XirrOut(BaseModel):
    account: XirrAccountOut
    funds: list[XirrFundOut]


# =========================================================
# 一键同步全部
# =========================================================


class SyncAllOut(BaseModel):
    funds: int = Field(0, description="处理的基金数")
    prices_inserted: int = Field(0, description="新增日线条数")
    holdings_generated: int = Field(0, description="生成的权益流水天数")
    cash_generated: int = Field(0, description="生成的现金流天数")
    failures: int = Field(0, description="失败的基金数")
    range_start: Optional[date] = None
    range_end: Optional[date] = None


# =========================================================
# 再平衡体检
# =========================================================


class RebalanceParams(BaseModel):
    """偏离判定参数：阈值(%) = clamp(目标% × r_band/100, min_abs, max_abs)。"""

    r_band: float = 15.0  # 相对带系数(%)
    min_abs: float = 1.0  # 绝对底线(%)
    max_abs: float = 3.0  # 绝对上限(%)
    amount_floor: float = 300.0  # 偏离金额底线(元)


class RebalanceParamsUpdate(BaseModel):
    r_band: Optional[float] = Field(None, gt=0, le=100)
    min_abs: Optional[float] = Field(None, ge=0, le=100)
    max_abs: Optional[float] = Field(None, ge=0, le=100)
    amount_floor: Optional[float] = Field(None, ge=0)


class RebalanceFundOut(BaseModel):
    fund_id: int
    fund_code: str
    fund_name: str
    price: Optional[float] = None  # 现价（计划算手数用）
    target: Optional[float] = None  # 目标比例(%)
    real: float  # 当前占比(%)
    deviation: float  # 偏离(百分点)
    deviation_amount: Optional[float] = None  # 偏离金额(元)，无持仓组合(total=0)时为 None
    threshold: Optional[float] = None  # 判定阈值(%)，未设目标时 None
    status: str = "normal"  # above / below / normal（后端统一判定）
    suggestion: str = "—"  # 建议动作文本（后端计算）


class RebalanceCashOut(BaseModel):
    target: float
    real: float
    deviation: float
    deviation_amount: Optional[float] = None  # 无持仓组合(total=0)时为 None
    threshold: float
    status: str = "normal"
    suggestion: str = "—"


class RebalanceOut(BaseModel):
    params: RebalanceParams
    total: float
    funds: list[RebalanceFundOut]
    cash: RebalanceCashOut


# =========================================================
# 对比基准（回测用）
# =========================================================


class BenchmarkOut(BaseModel):
    id: int
    symbol: str  # 行情 symbol，如 sh000300 / sz399006 / sh513500
    name: str
    source: str = "tencent"
    fund_id: Optional[int] = None  # 代理基金ID，NULL=直连指数
    fund_code: Optional[str] = None
    fund_name: Optional[str] = None
    active: bool = True


class BenchmarkSyncOut(BaseModel):
    symbol: str
    fetched: int = 0
    inserted: int = 0
    existing: int = 0
    range_start: date
    range_end: date


# =========================================================
# 方案回测
# =========================================================


class BacktestCoverageItem(BaseModel):
    """回测数据覆盖检查单条：基金或基准。"""

    kind: Literal["fund", "benchmark"]
    id: int
    code: str
    name: str
    first_date: Optional[date] = None  # 全表最早可用日期
    last_date: Optional[date] = None  # 全表最晚可用日期
    missing_days: int = 0  # 区间内真实缺失的交易日数（剔除节假日/今天未收盘）
    segments: list[PriceSegment] = Field(default_factory=list)
    covers_window: bool = False  # 数据起点≤start 且终点≥全局最后交易日 且 无真实缺失
    actionable: bool = False  # True=存在可补的真实缺口（需同步/补历史）；False=仅数据起点晚（多为上市晚）


class BacktestCoverageOut(BaseModel):
    items: list[BacktestCoverageItem] = Field(default_factory=list)
    start_date: date
    end_date: date
    ready: bool = False  # 全部 covers_window


class BacktestTradeOut(BaseModel):
    date: date
    fund_code: str
    fund_name: str
    side: Literal["buy", "sell"]
    hands: int
    price: Decimal
    principal: Decimal
    fee: Decimal
    total_amount: Decimal
    reason: Literal["period", "annual"]  # period=每期定投 / annual=年末再平衡


class BacktestPointOut(BaseModel):
    date: date
    asset: Decimal  # 总资产 = 权益 + 现金
    equity: Decimal  # 权益市值
    cash: Decimal  # 现金
    invested: Decimal  # 累计投入
    nav: float  # TWR 累计净值
    drawdown: float  # 水下：相对历史峰值回撤（≤0）
    drawup: float  # 水上：相对历史谷底涨幅（回撤镜像，≥0）
    allocations: dict[str, float] = Field(default_factory=dict)  # 各标的持仓占比(%)，现金键 000000


class BacktestMetricsOut(BaseModel):
    xirr: Optional[float] = None  # 资金加权年化（主指标）
    twr: Optional[float] = None  # 时间加权期间收益
    twr_annualized: Optional[float] = None  # TWR 年化
    span_days: int = 0
    start_date: Optional[date] = None  # 实际生效起始日（可能晚于请求值）
    end_date: Optional[date] = None  # 实际最后交易日
    max_drawdown: float = 0.0  # 最大回撤（≤0）
    max_drawdown_start: Optional[date] = None  # 最大回撤对应峰值日
    max_drawdown_end: Optional[date] = None  # 最大回撤谷底日
    current_drawdown: float = 0.0
    max_drawup: float = 0.0  # 最大水上涨幅（距谷底，≥0，回撤镜像）
    current_drawup: float = 0.0
    invested: Decimal = Decimal("0")
    current_value: Decimal = Decimal("0")
    gain: Decimal = Decimal("0")
    gain_pct: Optional[float] = None
    deposit_count: int = 0


class BacktestBenchmarkNav(BaseModel):
    date: date
    nav: Optional[float] = None  # 归一化净值（起始日=1），基准无数据前为 None


class BacktestBenchmarkOut(BaseModel):
    symbol: str
    name: str
    cagr: Optional[float] = None
    total_return: float = 0.0
    nav_series: list[BacktestBenchmarkNav] = Field(default_factory=list)


class BacktestParamsOut(BaseModel):
    start_date: date
    end_date: date
    amount: Decimal
    interval_days: int
    rebalance_strategy: str
    buy_rebalance: bool = True  # 买入式再平衡（每期低配补买）
    sell_rebalance: bool = True  # 卖出式再平衡（年末超配卖出）
    unlisted_mode: str = "park"  # 未上市标的处理：park=现金停泊 / redistribute=比例重分配


class BacktestOut(BaseModel):
    plan_id: int
    plan_name: str
    params: BacktestParamsOut
    metrics: BacktestMetricsOut
    points: list[BacktestPointOut] = Field(default_factory=list)
    trades: list[BacktestTradeOut] = Field(default_factory=list)
    benchmarks: list[BacktestBenchmarkOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# =========================================================
# 数据源（按 fund_type 分别配置）
# =========================================================


class DataSourceProvider(BaseModel):
    name: str
    label: str
    fund_types: list[str] = Field(default_factory=list)


class DataSourceType(BaseModel):
    """某 fund_type（etf/otc）的数据源配置组。"""

    fund_type: str
    label: str
    options: list[DataSourceProvider] = Field(default_factory=list)
    current: str = ""


class DataSourceOut(BaseModel):
    types: list[DataSourceType] = Field(default_factory=list)


class DataSourceUpdate(BaseModel):
    fund_type: str = Field(..., description="标的类型：etf / otc")
    provider: str = Field(
        ..., description="数据源名称，如 tencent / sina / eastmoney / akshare"
    )
