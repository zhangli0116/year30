from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Fund(Base):
    """指数基金基本信息，对应已有的 fund 表。"""

    __tablename__ = "fund"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, comment="基金代码")
    fund_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="基金名称")
    exchange: Mapped[str] = mapped_column(String(16), nullable=False, default="上交所", comment="交易所")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY", comment="币种")
    target_ratio: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="目标配置比例(%)，NULL=未设置"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )

    purchases: Mapped[list["PurchaseRecord"]] = relationship(
        back_populates="fund",
        # 不在 ORM 层级联删除：有记录的基金删除由业务层拦截（与数据库 FK RESTRICT 一致）
    )


class FundHoldingDaily(Base):
    """基金每日权益流水：按天累计持有份额 × 当日收盘价。"""

    __tablename__ = "fund_holding_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
    """每日现金流量表：按日历日累计现金余额。"""

    __tablename__ = "fund_cash_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, comment="日期")
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


class Quarter(Base):
    """季度定投汇总表。"""

    __tablename__ = "quarter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, comment="周期标识")
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="周期开始日期")
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="周期结束日期")
    budget: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="本周期预算")
    equity_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="权益投入(本金，不含手续费)")
    total_fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="本季度手续费总额")
    cash_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="剩余现金 = budget − equity − total_fee")
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    purchases: Mapped[list["PurchaseRecord"]] = relationship(back_populates="quarter")


class PurchaseRecord(Base):
    """指数基金购买记录，对应已有的 purchase_record 表。"""

    __tablename__ = "purchase_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(8), nullable=False, default="buy", comment="交易类型：buy=买入 / sell=卖出")
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
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, comment="花费总金额 = 本金 + 手续费")
    fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=5, comment="手续费(元)，默认 5")
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="记录创建时间"
    )

    fund: Mapped[Fund] = relationship(back_populates="purchases")
    quarter: Mapped[Optional[Quarter]] = relationship(back_populates="purchases")
