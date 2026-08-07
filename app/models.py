from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.mysql import INTEGER as MySQLInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# 主键/外键用 UNSIGNED，与 schema.sql 中 fund/quarter 等表的 INT UNSIGNED 一致
_UINT = lambda: MySQLInteger(unsigned=True)


class DcaPlan(Base):
    """定投方案：一次定投的定义（节奏 / 金额 / 标的比例 / 现金比例 / 再平衡策略）。"""

    __tablename__ = "dca_plan"

    id: Mapped[int] = mapped_column(_UINT(), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="方案名")
    start_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, comment="起始日期（首次定投，作为间隔基准）"
    )
    interval_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=91, comment="定投间隔天数（如 91 = 约每季）"
    )
    tolerance_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, comment="容错天数：下次定投窗口 = 上次基准 + 间隔 ± 容错"
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0, comment="每次投入金额"
    )
    rebalance_strategy: Mapped[str] = mapped_column(
        String(16), nullable=False, default="check", comment="再平衡策略：buy(买入式)/sell(卖出式)/check(偏离分析)"
    )
    cash_ratio: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=0, comment="现金目标比例(%)，方案内 Σ标的+现金=100"
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    fund_configs: Mapped[list["PlanFund"]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class PlanFund(Base):
    """方案-标的配置：某方案下每只基金的占比。"""

    __tablename__ = "plan_fund"
    __table_args__ = (UniqueConstraint("plan_id", "fund_id", name="uk_plan_fund"),)

    id: Mapped[int] = mapped_column(_UINT(), primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        _UINT(),
        ForeignKey("dca_plan.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="方案ID",
    )
    fund_id: Mapped[int] = mapped_column(
        _UINT(),
        ForeignKey("fund.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        comment="基金ID",
    )
    target_ratio: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, comment="该方案下此标的目标占比(%)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )

    plan: Mapped[DcaPlan] = relationship(back_populates="fund_configs")
    fund: Mapped["Fund"] = relationship()


class Fund(Base):
    """指数基金基本信息，对应已有的 fund 表。"""

    __tablename__ = "fund"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, comment="基金代码")
    fund_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="基金名称")
    exchange: Mapped[str] = mapped_column(String(16), nullable=False, default="上交所", comment="交易所")
    fund_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="etf", comment="标的类型：etf=场内(ETF/LOF，K线) / otc=场外基金(净值)"
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY", comment="币种")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )

    purchases: Mapped[list["PurchaseRecord"]] = relationship(
        back_populates="fund",
        # 不在 ORM 层级联删除：有记录的基金删除由业务层拦截（与数据库 FK RESTRICT 一致）
    )


class FundHoldingDaily(Base):
    """基金每日权益流水：按天累计持有份额 × 当日收盘价（按方案拆分）。"""

    __tablename__ = "fund_holding_daily"
    __table_args__ = (
        UniqueConstraint("plan_id", "fund_id", "trade_date", name="uk_plan_fund_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        _UINT(),
        ForeignKey("dca_plan.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="方案ID",
    )
    fund_id: Mapped[int] = mapped_column(
        ForeignKey("fund.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="基金ID",
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, comment="交易日")
    total_shares: Mapped[int] = mapped_column(Integer, nullable=False, comment="当日累计持有份数")
    total_hands: Mapped[int] = mapped_column(Integer, nullable=False, comment="当日累计手数")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, comment="当日收盘价")
    equity_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, comment="当日权益金额")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="记录创建时间"
    )

    fund: Mapped[Fund] = relationship()


class FundCashDaily(Base):
    """每日现金流量表：按日历日累计现金余额（按方案拆分）。"""

    __tablename__ = "fund_cash_daily"
    __table_args__ = (UniqueConstraint("plan_id", "trade_date", name="uk_plan_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        _UINT(),
        ForeignKey("dca_plan.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="方案ID",
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, comment="日期")
    increment: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="当日现金增量")
    cash_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="当日累计现金余额")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="记录创建时间"
    )


class FundPrice(Base):
    """基金历史日线价格（OHLC），对应 fund_price 表。"""

    __tablename__ = "fund_price"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = mapped_column(
        ForeignKey("fund.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="基金ID",
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, comment="交易日")
    open_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True, comment="开盘价")
    high_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True, comment="最高价")
    low_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True, comment="最低价")
    close_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, comment="收盘价")
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="成交量")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="tencent", comment="数据源")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="记录创建时间"
    )

    fund: Mapped[Fund] = relationship()


class FundNav(Base):
    """场外基金每日净值（单位净值/累计净值），对应 fund_nav 表。

    与 fund_price（交易所 OHLC）分开存储：场外基金无盘口/无 OHLC。
    """

    __tablename__ = "fund_nav"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = mapped_column(
        ForeignKey("fund.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="基金ID",
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, comment="净值日期")
    unit_nav: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, comment="单位净值")
    accum_nav: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True, comment="累计净值")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="eastmoney", comment="数据源")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="记录创建时间"
    )

    fund: Mapped[Fund] = relationship()


class Benchmark(Base):
    """对比基准指数（回测对比用）。fund_id 非空=代理基准（如 标普500→513500）。"""

    __tablename__ = "benchmark"

    id: Mapped[int] = mapped_column(_UINT(), primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, comment="行情symbol，如 sh000300")
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="基准名称")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="tencent", comment="数据源")
    fund_id: Mapped[Optional[int]] = mapped_column(
        _UINT(),
        ForeignKey("fund.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        comment="代理基金ID（标普500→513500），NULL=直连指数日线",
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )

    fund: Mapped[Optional[Fund]] = relationship()


class BenchmarkPrice(Base):
    """基准指数历史日线（回测对比用）。"""

    __tablename__ = "benchmark_price"
    __table_args__ = (UniqueConstraint("benchmark_id", "trade_date", name="uk_benchmark_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benchmark_id: Mapped[int] = mapped_column(
        _UINT(),
        ForeignKey("benchmark.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="基准ID",
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, comment="交易日")
    close_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, comment="收盘点位")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )

    benchmark: Mapped[Benchmark] = relationship()


class Quarter(Base):
    """定投周期汇总表（某方案的每一期投入）。"""

    __tablename__ = "quarter"
    __table_args__ = (UniqueConstraint("plan_id", "period", name="uk_plan_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        _UINT(),
        ForeignKey("dca_plan.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="方案ID",
    )
    period: Mapped[str] = mapped_column(String(10), nullable=False, comment="周期标识，如 2026Q3")
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="周期开始日期")
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="周期结束日期")
    budget: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="本周期预算")
    equity_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="权益投入(本金，不含手续费)")
    total_fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="本周期手续费总额")
    cash_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="剩余现金 = budget − equity − total_fee")
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    plan: Mapped[DcaPlan] = relationship()
    purchases: Mapped[list["PurchaseRecord"]] = relationship(back_populates="quarter")


class PurchaseRecord(Base):
    """指数基金购买记录，对应已有的 purchase_record 表。"""

    __tablename__ = "purchase_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(8), nullable=False, default="buy", comment="交易类型：buy=买入 / sell=卖出")
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("dca_plan.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属方案ID",
    )
    quarter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("quarter.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联季度汇总表",
    )
    fund_id: Mapped[int] = mapped_column(
        ForeignKey("fund.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="基金ID",
    )
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False, comment="购买日期")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, comment="每股价格")
    hands: Mapped[int] = mapped_column(Integer, nullable=False, comment="购买手数")
    shares_per_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=100, comment="每手份数")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, comment="权益金额 = 本金/成交额（不含手续费）")
    fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=5, comment="手续费(元)，默认 5")
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="记录创建时间"
    )

    fund: Mapped[Fund] = relationship(back_populates="purchases")
    quarter: Mapped[Optional[Quarter]] = relationship(back_populates="purchases")


class AppSetting(Base):
    """系统键值配置（如再平衡判定阈值），供页面读写。"""

    __tablename__ = "app_setting"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="配置键")
    value: Mapped[str] = mapped_column(String(255), nullable=False, comment="配置值")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
