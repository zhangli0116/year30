"""一次性迁移：引入多定投方案（dca_plan / plan_fund），把现有数据挂到「默认方案」。

步骤：
  1. 建 dca_plan / plan_fund 表（已存在的表跳过）
  2. seed「默认方案」：amount=现有季度预算均值，cash_ratio=现金基金(000000)目标，标的比例从 fund.target_ratio 迁移
  3. quarter / purchase_record / fund_holding_daily / fund_cash_daily 加 plan_id 并回填默认方案
  4. 改唯一键为方案维度，加外键

用法：python scripts/migrate_plans.py
幂等：默认方案已存在或列已加时跳过。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app import models  # noqa: E402,F401  确保新表注册到 Base.metadata
from app.database import Base, engine  # noqa: E402

DEFAULT_PLAN = "默认方案"


def _col_exists(db, table: str, column: str) -> bool:
    row = db.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema=DATABASE() AND table_name=:t AND column_name=:c"
        ),
        {"t": table, "c": column},
    ).first()
    return row is not None


def _idx_exists(db, table: str, index: str) -> bool:
    row = db.execute(
        text(
            "SELECT 1 FROM information_schema.statistics "
            "WHERE table_schema=DATABASE() AND table_name=:t AND index_name=:i LIMIT 1"
        ),
        {"t": table, "i": index},
    ).first()
    return row is not None


def _fk_exists(db, table: str, fk: str) -> bool:
    row = db.execute(
        text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_schema=DATABASE() AND table_name=:t AND constraint_name=:f "
            "AND constraint_type='FOREIGN KEY'"
        ),
        {"t": table, "f": fk},
    ).first()
    return row is not None


def _add_plan_column(db, table: str, fk: str, unique_name: str | None, unique_cols: str | None, drop_old: list[str]) -> None:
    if not _col_exists(db, table, "plan_id"):
        db.execute(text(f"ALTER TABLE {table} ADD COLUMN plan_id INT UNSIGNED NULL AFTER id"))
        print(f"  {table} +plan_id")
    db.execute(text(f"UPDATE {table} SET plan_id=:pid WHERE plan_id IS NULL"), {"pid": _default_plan_id})
    db.execute(text(f"ALTER TABLE {table} MODIFY plan_id INT UNSIGNED NOT NULL"))
    for old in drop_old:
        if _idx_exists(db, table, old):
            db.execute(text(f"ALTER TABLE {table} DROP INDEX {old}"))
            print(f"  {table} -index {old}")
    if unique_name and not _idx_exists(db, table, unique_name):
        db.execute(text(f"ALTER TABLE {table} ADD UNIQUE KEY {unique_name} ({unique_cols})"))
        print(f"  {table} +unique {unique_name}")
    if fk and not _fk_exists(db, table, fk):
        db.execute(
            text(
                f"ALTER TABLE {table} ADD CONSTRAINT {fk} FOREIGN KEY (plan_id) "
                "REFERENCES dca_plan(id) ON UPDATE CASCADE ON DELETE CASCADE"
            )
        )
        print(f"  {table} +fk {fk}")


_default_plan_id = None


def main() -> None:
    global _default_plan_id
    # 若存在半成品空表（上次失败遗留的带符号 id），重建为 UNSIGNED 类型
    with engine.begin() as db:
        exists = db.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema=DATABASE() AND table_name='dca_plan'"
            )
        ).scalar()
        if exists:
            has_rows = db.execute(text("SELECT COUNT(*) FROM dca_plan")).scalar()
            if has_rows == 0:
                db.execute(text("DROP TABLE IF EXISTS plan_fund"))
                db.execute(text("DROP TABLE IF EXISTS dca_plan"))
                print("清理空方案表，重建为 UNSIGNED 类型")
    Base.metadata.create_all(bind=engine)  # 建 dca_plan / plan_fund（存在的表跳过）

    with engine.begin() as db:
        # 1) 默认方案
        row = db.execute(text("SELECT id FROM dca_plan WHERE name=:n"), {"n": DEFAULT_PLAN}).first()
        if row:
            _default_plan_id = row[0]
            print(f"默认方案已存在 id={_default_plan_id}")
        else:
            cash_ratio = db.execute(
                text("SELECT target_ratio FROM fund WHERE fund_code='000000'")
            ).scalar()
            amount = db.execute(text("SELECT ROUND(COALESCE(AVG(budget),0),2) FROM quarter")).scalar()
            res = db.execute(
                text(
                    "INSERT INTO dca_plan (name, `interval`, amount, rebalance_strategy, cash_ratio, active) "
                    "VALUES (:n, 'quarterly', :a, 'check', :c, 1)"
                ),
                {"n": DEFAULT_PLAN, "a": amount or 0, "c": cash_ratio or 0},
            )
            _default_plan_id = res.lastrowid
            db.execute(
                text(
                    "INSERT INTO plan_fund (plan_id, fund_id, target_ratio) "
                    "SELECT :pid, id, target_ratio FROM fund "
                    "WHERE fund_code <> '000000' AND target_ratio IS NOT NULL"
                ),
                {"pid": _default_plan_id},
            )
            print(f"已建默认方案 id={_default_plan_id} cash_ratio={cash_ratio}，标的已迁移")

        # 1.5) dca_plan：interval 枚举 → start_date/interval_days/tolerance_days
        if not _col_exists(db, "dca_plan", "interval_days"):
            db.execute(
                text(
                    "ALTER TABLE dca_plan "
                    "ADD COLUMN start_date DATE NULL COMMENT '起始日期' AFTER name, "
                    "ADD COLUMN interval_days INT NOT NULL DEFAULT 90 COMMENT '定投间隔天数' AFTER start_date, "
                    "ADD COLUMN tolerance_days INT NOT NULL DEFAULT 5 COMMENT '容错天数' AFTER interval_days"
                )
            )
            print("  dca_plan +start_date/interval_days/tolerance_days")
            # 回填默认方案：起始日期 = 最早 quarter.start_date，间隔 90 天
            earliest = db.execute(
                text("SELECT MIN(start_date) FROM quarter WHERE plan_id=:pid"), {"pid": _default_plan_id}
            ).scalar()
            db.execute(
                text(
                    "UPDATE dca_plan SET start_date=:sd, interval_days=90, tolerance_days=5 WHERE id=:pid"
                ),
                {"sd": earliest, "pid": _default_plan_id},
            )
        if _col_exists(db, "dca_plan", "interval"):
            db.execute(text("ALTER TABLE dca_plan DROP COLUMN `interval`"))
            print("  dca_plan -interval")

        # 2) 各表加 plan_id + 回填 + 唯一键改方案维度
        print("迁移 quarter:")
        _add_plan_column(db, "quarter", "fk_quarter_plan", "uk_plan_period", "plan_id, period", ["uk_period"])
        print("迁移 purchase_record:")
        _add_plan_column(db, "purchase_record", "fk_purchase_plan", None, None, [])  # 只加列+FK，不改唯一键
        # purchase_record 额外补索引
        if not _idx_exists(db, "purchase_record", "idx_plan_id"):
            db.execute(text("ALTER TABLE purchase_record ADD INDEX idx_plan_id (plan_id)"))
        if not _fk_exists(db, "purchase_record", "fk_purchase_plan"):
            db.execute(
                text(
                    "ALTER TABLE purchase_record ADD CONSTRAINT fk_purchase_plan "
                    "FOREIGN KEY (plan_id) REFERENCES dca_plan(id) ON UPDATE CASCADE ON DELETE CASCADE"
                )
            )
        print("迁移 fund_holding_daily:")
        _add_plan_column(db, "fund_holding_daily", "fk_holding_plan", "uk_plan_fund_date",
                         "plan_id, fund_id, trade_date", ["uk_fund_date"])
        if not _idx_exists(db, "fund_holding_daily", "idx_plan_fund"):
            db.execute(text("ALTER TABLE fund_holding_daily ADD INDEX idx_plan_fund (plan_id, fund_id)"))
        print("迁移 fund_cash_daily:")
        _add_plan_column(db, "fund_cash_daily", "fk_cash_plan", "uk_plan_date", "plan_id, trade_date", ["uk_date"])

        # 3) 校验
        for t in ["quarter", "purchase_record", "fund_holding_daily", "fund_cash_daily"]:
            total = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            nulls = db.execute(text(f"SELECT COUNT(*) FROM {t} WHERE plan_id IS NULL")).scalar()
            print(f"校验 {t}: {total} 行, plan_id 为 NULL: {nulls}")

    print("✅ 迁移完成")


if __name__ == "__main__":
    main()
