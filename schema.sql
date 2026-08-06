-- =============================================
-- 指数基金定投记录 数据库表结构
-- 业务规则：
--   1. 每季度买入若干只指数基金
--   2. 一手 = 100 份；购买以"手"为单位
--   3. 每次记录：购买时间、基金代码/名称、每股价格、购买手数、总花费金额
-- 金额 = 手数 × 每手份数(100) × 每股价格（如另有手续费可自行计入 total_amount）
-- =============================================

DROP DATABASE IF EXISTS fund_invest;
CREATE DATABASE fund_invest
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE fund_invest;

-- --------------------------------------------------
-- 表 1：基金维度表 —— 存放你长期持有的基金标的
-- --------------------------------------------------
CREATE TABLE fund (
    id          INT UNSIGNED    NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    fund_code   VARCHAR(10)     NOT NULL COMMENT '基金/ETF代码，如 513500',
    fund_name   VARCHAR(64)     NOT NULL COMMENT '基金名称，如 标普500ETF',
    exchange    VARCHAR(16)     NOT NULL DEFAULT '上交所' COMMENT '上市交易所：上交所/深交所',
    currency    CHAR(3)         NOT NULL DEFAULT 'CNY' COMMENT '币种',
    target_ratio DECIMAL(5,2)   NULL COMMENT '目标配置比例(%)，如 20.00；NULL 表示未设置',
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_fund_code (fund_code)
) ENGINE = InnoDB COMMENT = '指数基金基本信息';

-- --------------------------------------------------
-- 表 2：季度汇总表 —— 每次定投一条汇总记录
-- --------------------------------------------------
CREATE TABLE quarter (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    period          VARCHAR(10)     NOT NULL COMMENT '周期标识，如 2026Q3',
    start_date      DATE            NULL COMMENT '周期开始日期',
    end_date        DATE            NULL COMMENT '周期结束日期',
    budget          DECIMAL(14,2)   NOT NULL DEFAULT 0.00 COMMENT '本周期预算，如 12500',
    equity_amount   DECIMAL(14,2)   NOT NULL DEFAULT 0.00 COMMENT '权益投入(本金，不含手续费)',
    total_fee       DECIMAL(14,2)   NOT NULL DEFAULT 0.00 COMMENT '本季度手续费总额',
    cash_amount     DECIMAL(14,2)   NOT NULL DEFAULT 0.00 COMMENT '剩余现金 = budget - equity_amount - total_fee',
    note            VARCHAR(255)    NULL COMMENT '备注，如 2026Q3 定投',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_period (period)
) ENGINE = InnoDB COMMENT = '季度定投汇总表';

-- --------------------------------------------------
-- 表 3：购买记录表 —— 每次定投一条记录，明细归属于某季度
-- --------------------------------------------------
CREATE TABLE purchase_record (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    quarter_id      INT UNSIGNED    NULL     COMMENT '关联季度汇总表 -> quarter.id',
    fund_id         INT UNSIGNED    NOT NULL COMMENT '基金ID -> fund.id',
    purchase_date   DATE            NOT NULL COMMENT '购买日期（如 2026-04-02）',
    price           DECIMAL(10,4)   NOT NULL COMMENT '每股/每份价格，如 2.6760',
    hands           INT UNSIGNED    NOT NULL COMMENT '购买手数（以手为单位）',
    shares_per_hand INT UNSIGNED    NOT NULL DEFAULT 100 COMMENT '每手份数，1手=100份',
    total_amount    DECIMAL(14,2)   NOT NULL COMMENT '本次花费总金额 = 本金 + 手续费',
    fee             DECIMAL(14,2)   NOT NULL DEFAULT 5.00 COMMENT '手续费(元)，默认 5；费率默认 0.03%，不足 5 元按 5 元',
    note            VARCHAR(255)    NULL COMMENT '备注，如 2026Q1 定投',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    PRIMARY KEY (id),
    KEY idx_fund_date (fund_id, purchase_date),
    KEY idx_quarter_id (quarter_id),
    CONSTRAINT fk_purchase_fund FOREIGN KEY (fund_id) REFERENCES fund (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_purchase_quarter FOREIGN KEY (quarter_id) REFERENCES quarter (id)
        ON DELETE SET NULL
) ENGINE = InnoDB COMMENT = '指数基金购买记录';

-- --------------------------------------------------
-- 表 4：基金历史日线价格（OHLC），供趋势图/K线图与市值估算
-- --------------------------------------------------
CREATE TABLE fund_price (
    id           INT UNSIGNED   NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    fund_id      INT UNSIGNED   NOT NULL COMMENT '基金ID -> fund.id',
    trade_date   DATE           NOT NULL COMMENT '交易日',
    open_price   DECIMAL(10,4)  NULL COMMENT '开盘价',
    high_price   DECIMAL(10,4)  NULL COMMENT '最高价',
    low_price    DECIMAL(10,4)  NULL COMMENT '最低价',
    close_price  DECIMAL(10,4)  NOT NULL COMMENT '收盘价',
    volume       BIGINT         NULL COMMENT '成交量',
    source       VARCHAR(16)    NOT NULL DEFAULT 'tencent' COMMENT '数据源',
    created_at   DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_fund_date (fund_id, trade_date),
    KEY idx_trade_date (trade_date),
    CONSTRAINT fk_price_fund FOREIGN KEY (fund_id) REFERENCES fund (id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '基金历史日线价格';

-- --------------------------------------------------
-- 表 5：基金每日权益流水（按天累计持有份额 × 当日收盘价）
-- --------------------------------------------------
CREATE TABLE fund_holding_daily (
    id            INT UNSIGNED   NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    fund_id       INT UNSIGNED   NOT NULL COMMENT '基金ID -> fund.id',
    trade_date    DATE           NOT NULL COMMENT '交易日',
    total_shares  INT UNSIGNED   NOT NULL COMMENT '当日累计持有份数（买+卖-）',
    total_hands   INT UNSIGNED   NOT NULL COMMENT '当日累计手数（=份数/100）',
    price         DECIMAL(10,4)  NOT NULL COMMENT '当日收盘价',
    equity_amount DECIMAL(14,2)  NOT NULL COMMENT '当日权益金额 = 份数 × 价格',
    created_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_fund_date (fund_id, trade_date),
    KEY idx_fund (fund_id),
    CONSTRAINT fk_holding_fund FOREIGN KEY (fund_id) REFERENCES fund (id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '基金每日权益流水';

-- --------------------------------------------------
-- 表 6：每日现金流量表（日历日累计现金余额）
-- 增量 = 季度预算入账(+budget) − 买入支出(−buy total_amount，含费) + 卖出回笼(+sell total_amount) − 卖出手续费(−sell fee)
-- --------------------------------------------------
CREATE TABLE fund_cash_daily (
    id          INT UNSIGNED   NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    trade_date  DATE           NOT NULL COMMENT '日期（日历日，含周末）',
    increment   DECIMAL(14,2)  NOT NULL DEFAULT 0.00 COMMENT '当日现金增量',
    cash_amount DECIMAL(14,2)  NOT NULL DEFAULT 0.00 COMMENT '当日累计现金余额',
    created_at  DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_date (trade_date)
) ENGINE = InnoDB COMMENT = '每日现金流量表';

-- --------------------------------------------------
-- 表 7：系统键值配置（如再平衡判定阈值）
-- --------------------------------------------------
CREATE TABLE app_setting (
    id         INT UNSIGNED  NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `key`      VARCHAR(64)   NOT NULL COMMENT '配置键',
    `value`    VARCHAR(255)  NOT NULL COMMENT '配置值',
    created_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_key (`key`)
) ENGINE = InnoDB COMMENT = '系统键值配置';

-- --------------------------------------------------
-- 示例数据
-- --------------------------------------------------
INSERT INTO fund (fund_code, fund_name, exchange) VALUES
    ('513500', '标普500ETF', '上交所'),
    ('159920', '恒生ETF',    '深交所'),
    ('510300', '沪深300ETF', '上交所');

-- 示例：2026Q1 买入 标普500(513500)，单价 2.676，买 200 手（200×100=20000 份），共花费 53520.00 元
INSERT INTO purchase_record (fund_id, purchase_date, price, hands, total_amount, note)
SELECT id, '2026-04-02', 2.6760, 200, 53520.00, '2026Q1 定投'
FROM fund WHERE fund_code = '513500';

-- --------------------------------------------------
-- 常用查询
-- --------------------------------------------------
-- 某基金全部买入记录（按时间排序）
SELECT
    f.fund_code,
    f.fund_name,
    p.purchase_date,
    p.price,
    p.hands,
    p.hands * p.shares_per_hand AS shares,
    p.total_amount
FROM purchase_record p
JOIN fund f ON f.id = p.fund_id
WHERE f.fund_code = '513500'
ORDER BY p.purchase_date;

-- 汇总：每只基金的购买次数、累计份数、累计投入、平均成本
SELECT
    f.fund_code,
    f.fund_name,
    COUNT(p.id)                                                 AS buy_count,
    SUM(p.hands * p.shares_per_hand)                            AS total_shares,
    SUM(p.total_amount)                                         AS total_cost,
    ROUND(SUM(p.total_amount) / SUM(p.hands * p.shares_per_hand), 4) AS avg_cost
FROM fund f
LEFT JOIN purchase_record p ON p.fund_id = f.id
GROUP BY f.id, f.fund_code, f.fund_name
ORDER BY f.fund_code;
