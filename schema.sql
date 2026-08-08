-- =============================================
-- 指数基金定投记录 数据库表结构
-- 业务规则：
--   1. 每季度买入若干只指数基金
--   2. 一手 = 100 份；购买以"手"为单位
--   3. 每次记录：购买时间、基金代码/名称、每股价格、购买手数、权益金额
-- 权益金额(total_amount) = 手数 × 每手份数(100) × 每股价格，不含手续费；手续费单独存 fee 列
-- =============================================

DROP DATABASE IF EXISTS fund_invest;
CREATE DATABASE fund_invest
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE fund_invest;

-- --------------------------------------------------
-- 表 1：定投方案表 —— 一次定投的定义（节奏/金额/标的比例/现金比例/再平衡策略）
-- --------------------------------------------------
CREATE TABLE dca_plan (
    id                 INT UNSIGNED   NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    name               VARCHAR(64)    NOT NULL COMMENT '方案名，如 稳健季定投',
    `interval`         VARCHAR(16)    NOT NULL DEFAULT 'quarterly' COMMENT '定投间隔：weekly/monthly/quarterly',
    amount             DECIMAL(14,2)  NOT NULL DEFAULT 0.00 COMMENT '每次投入金额',
    rebalance_strategy VARCHAR(16)    NOT NULL DEFAULT 'check' COMMENT '再平衡策略：buy(买入式)/sell(卖出式)/check(偏离分析)',
    cash_ratio         DECIMAL(5,2)   NOT NULL DEFAULT 0.00 COMMENT '现金目标比例(%)，方案内 Σ标的+现金=100',
    active             TINYINT(1)     NOT NULL DEFAULT 1 COMMENT '是否启用',
    created_at         DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at         DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_name (name)
) ENGINE = InnoDB COMMENT = '定投方案表';

-- --------------------------------------------------
-- 表 2：方案-标的配置表 —— 某方案下每只基金的占比
-- --------------------------------------------------
CREATE TABLE plan_fund (
    id           INT UNSIGNED   NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    plan_id      INT UNSIGNED   NOT NULL COMMENT '方案ID -> dca_plan.id',
    fund_id      INT UNSIGNED   NOT NULL COMMENT '基金ID -> fund.id',
    target_ratio DECIMAL(5,2)   NOT NULL COMMENT '该方案下此标的目标占比(%)',
    created_at   DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_plan_fund (plan_id, fund_id),
    CONSTRAINT fk_pf_plan FOREIGN KEY (plan_id) REFERENCES dca_plan (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_pf_fund FOREIGN KEY (fund_id) REFERENCES fund (id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '方案-标的配置';

-- --------------------------------------------------
-- 表 3：基金维度表 —— 存放你长期持有的基金标的
-- --------------------------------------------------
CREATE TABLE fund (
    id          INT UNSIGNED    NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    fund_code   VARCHAR(10)     NOT NULL COMMENT '基金/ETF代码，如 513500',
    fund_name   VARCHAR(64)     NOT NULL COMMENT '基金名称，如 标普500ETF',
    exchange    VARCHAR(16)     NOT NULL DEFAULT '上交所' COMMENT '上市交易所：上交所/深交所',
    fund_type   VARCHAR(16)     NOT NULL DEFAULT 'etf' COMMENT '标的类型：etf=场内(ETF/LOF，K线) / otc=场外基金(净值)',
    currency    CHAR(3)         NOT NULL DEFAULT 'CNY' COMMENT '币种',
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_fund_code (fund_code)
) ENGINE = InnoDB COMMENT = '指数基金基本信息';

-- --------------------------------------------------
-- 表 3.1：场外基金每日净值表 —— 与 fund_price 的交易所 OHLC 分开
-- 场外基金（fund.fund_type='otc'）无盘口/无 OHLC，一天只有单位净值/累计净值
-- --------------------------------------------------
CREATE TABLE fund_nav (
    id          INT UNSIGNED    NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    fund_id     INT UNSIGNED    NOT NULL COMMENT '基金ID -> fund.id',
    trade_date  DATE            NOT NULL COMMENT '净值日期',
    unit_nav    DECIMAL(10,4)   NOT NULL COMMENT '单位净值',
    accum_nav   DECIMAL(10,4)   NULL COMMENT '累计净值(现金分红线性累加)',
    adj_nav     DECIMAL(10,4)   NULL COMMENT '复权净值(分红复投口径，由单位净值+分红明细计算)',
    source      VARCHAR(16)     NOT NULL DEFAULT 'eastmoney' COMMENT '数据源',
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_fund_nav_date (fund_id, trade_date),
    KEY idx_nav_trade_date (trade_date),
    CONSTRAINT fk_nav_fund FOREIGN KEY (fund_id) REFERENCES fund (id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '场外基金每日净值';

-- --------------------------------------------------
-- 表 4：定投周期汇总表 —— 某方案每一期投入一条
-- --------------------------------------------------
CREATE TABLE quarter (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    plan_id         INT UNSIGNED    NOT NULL COMMENT '方案ID -> dca_plan.id',
    period          VARCHAR(10)     NOT NULL COMMENT '周期标识，如 2026Q3',
    start_date      DATE            NULL COMMENT '周期开始日期',
    end_date        DATE            NULL COMMENT '周期结束日期',
    budget          DECIMAL(14,2)   NOT NULL DEFAULT 0.00 COMMENT '本周期预算，如 12500',
    equity_amount   DECIMAL(14,2)   NOT NULL DEFAULT 0.00 COMMENT '权益投入(本金，不含手续费)',
    total_fee       DECIMAL(14,2)   NOT NULL DEFAULT 0.00 COMMENT '本周期手续费总额',
    cash_amount     DECIMAL(14,2)   NOT NULL DEFAULT 0.00 COMMENT '剩余现金 = budget - equity_amount - total_fee',
    note            VARCHAR(255)    NULL COMMENT '备注，如 2026Q3 定投',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_plan_period (plan_id, period),
    CONSTRAINT fk_quarter_plan FOREIGN KEY (plan_id) REFERENCES dca_plan (id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '定投周期汇总表';

-- --------------------------------------------------
-- 表 5：购买记录表 —— 每次定投一条记录，明细归属于某方案某周期
-- --------------------------------------------------
CREATE TABLE purchase_record (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    plan_id         INT UNSIGNED    NOT NULL COMMENT '所属方案ID -> dca_plan.id',
    quarter_id      INT UNSIGNED    NULL     COMMENT '关联季度汇总表 -> quarter.id',
    fund_id         INT UNSIGNED    NOT NULL COMMENT '基金ID -> fund.id',
    purchase_date   DATE            NOT NULL COMMENT '购买日期（如 2026-04-02）',
    price           DECIMAL(10,4)   NOT NULL COMMENT '每股/每份价格，如 2.6760',
    hands           INT UNSIGNED    NOT NULL COMMENT '购买手数（以手为单位）',
    shares_per_hand INT UNSIGNED    NOT NULL DEFAULT 100 COMMENT '每手份数，1手=100份',
    total_amount    DECIMAL(14,2)   NOT NULL COMMENT '权益金额 = 本金/成交额（不含手续费），手续费单独存 fee',
    fee             DECIMAL(14,2)   NOT NULL DEFAULT 5.00 COMMENT '手续费(元)，默认 5；费率默认 0.03%，不足 5 元按 5 元',
    note            VARCHAR(255)    NULL COMMENT '备注，如 2026Q1 定投',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    PRIMARY KEY (id),
    KEY idx_fund_date (fund_id, purchase_date),
    KEY idx_plan_id (plan_id),
    KEY idx_quarter_id (quarter_id),
    CONSTRAINT fk_purchase_plan FOREIGN KEY (plan_id) REFERENCES dca_plan (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
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
-- 表 5：对比基准指数（回测用）
-- fund_id 非空 = 代理基准（用基金历史价代替指数，如 标普500→513500）
-- --------------------------------------------------
CREATE TABLE benchmark (
    id         INT UNSIGNED  NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    symbol     VARCHAR(20)   NOT NULL COMMENT '行情symbol，如 sh000300 / sz399006 / sh513500',
    name       VARCHAR(64)   NOT NULL COMMENT '基准名称，如 沪深300',
    source     VARCHAR(16)   NOT NULL DEFAULT 'tencent' COMMENT '数据源',
    fund_id    INT UNSIGNED  NULL COMMENT '代理基金ID（标普500→513500），NULL=直连指数日线',
    active     TINYINT(1)    NOT NULL DEFAULT 1 COMMENT '是否启用',
    created_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_symbol (symbol),
    CONSTRAINT fk_benchmark_fund FOREIGN KEY (fund_id) REFERENCES fund (id)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE = InnoDB COMMENT = '对比基准指数';

-- --------------------------------------------------
-- 表 6：基准指数历史日线（回测对比用）
-- --------------------------------------------------
CREATE TABLE benchmark_price (
    id           INT UNSIGNED  NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    benchmark_id INT UNSIGNED  NOT NULL COMMENT '基准ID -> benchmark.id',
    trade_date   DATE          NOT NULL COMMENT '交易日',
    close_price  DECIMAL(10,4) NOT NULL COMMENT '收盘点位',
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_benchmark_date (benchmark_id, trade_date),
    CONSTRAINT fk_bp_benchmark FOREIGN KEY (benchmark_id) REFERENCES benchmark (id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '基准指数历史日线';

-- 基准种子（回测对比：沪深300/上证指数/创业板指直连指数；标普500 用 513500ETF 代理，人民币口径）
INSERT INTO benchmark (symbol, name, source, fund_id) VALUES
    ('sh000300',  '沪深300',          'tencent', NULL),
    ('sh000001',  '上证指数',         'tencent', NULL),
    ('sz399006',  '创业板指',         'tencent', NULL),
    ('sh513500',  '标普500(513500代理)', 'tencent', (SELECT id FROM fund WHERE fund_code = '513500'));

-- --------------------------------------------------
-- 表 7：基金每日权益流水（按天累计持有份额 × 当日收盘价，按方案拆分）
-- --------------------------------------------------
CREATE TABLE fund_holding_daily (
    id            INT UNSIGNED   NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    plan_id       INT UNSIGNED   NOT NULL COMMENT '方案ID -> dca_plan.id',
    fund_id       INT UNSIGNED   NOT NULL COMMENT '基金ID -> fund.id',
    trade_date    DATE           NOT NULL COMMENT '交易日',
    total_shares  INT UNSIGNED   NOT NULL COMMENT '当日累计持有份数（买+卖-）',
    total_hands   INT UNSIGNED   NOT NULL COMMENT '当日累计手数（=份数/100）',
    price         DECIMAL(10,4)  NOT NULL COMMENT '当日收盘价',
    equity_amount DECIMAL(14,2)  NOT NULL COMMENT '当日权益金额 = 份数 × 价格',
    created_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_plan_fund_date (plan_id, fund_id, trade_date),
    KEY idx_plan_fund (plan_id, fund_id),
    CONSTRAINT fk_holding_plan FOREIGN KEY (plan_id) REFERENCES dca_plan (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_holding_fund FOREIGN KEY (fund_id) REFERENCES fund (id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '基金每日权益流水（按方案）';

-- --------------------------------------------------
-- 表 7：每日现金流量表（日历日累计现金余额，按方案拆分）
-- 增量 = 方案周期预算入账(+budget) − 买入支出(−(buy total_amount + fee)，total_amount 不含手续费) + 卖出回笼(+sell total_amount) − 卖出手续费(−sell fee)
-- --------------------------------------------------
CREATE TABLE fund_cash_daily (
    id          INT UNSIGNED   NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    plan_id     INT UNSIGNED   NOT NULL COMMENT '方案ID -> dca_plan.id',
    trade_date  DATE           NOT NULL COMMENT '日期（日历日，含周末）',
    increment   DECIMAL(14,2)  NOT NULL DEFAULT 0.00 COMMENT '当日现金增量',
    cash_amount DECIMAL(14,2)  NOT NULL DEFAULT 0.00 COMMENT '当日累计现金余额',
    created_at  DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_plan_date (plan_id, trade_date),
    CONSTRAINT fk_cash_plan FOREIGN KEY (plan_id) REFERENCES dca_plan (id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '每日现金流量表（按方案）';

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
