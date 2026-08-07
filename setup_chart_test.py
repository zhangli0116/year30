# -*- coding: utf-8 -*-
"""主 agent 造图表测试方案数据（保留不删，供用户复核）。临时脚本，用后可删。"""
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, "D:/py_project/year30")
from app import crud, schemas
from app.database import SessionLocal

PLAN_NAME = "测试图表方案"
db = SessionLocal()

# 1) 方案（含标的 + 现金比例，Σ=100）
plan = crud.plan.get_plan_by_name(db, PLAN_NAME)
if plan is None:
    plan = crud.plan.create_plan(
        db,
        schemas.PlanCreate(
            name=PLAN_NAME,
            start_date=date(2026, 1, 1),
            interval_days=30,
            tolerance_days=5,
            amount=Decimal("5000"),
            rebalance_strategy="buy",
            cash_ratio=Decimal("10"),
            active=True,
            funds=[
                schemas.PlanFundIn(fund_id=9, target_ratio=Decimal("30")),   # 513500
                schemas.PlanFundIn(fund_id=10, target_ratio=Decimal("20")),  # 513100
                schemas.PlanFundIn(fund_id=11, target_ratio=Decimal("25")),  # 563360
                schemas.PlanFundIn(fund_id=12, target_ratio=Decimal("15")),  # 512890
            ],
        ),
    )
    print(f"创建方案 id={plan.id}")
else:
    print(f"方案已存在 id={plan.id}（复用）")
pid = plan.id

# 2) 三个周期（月度）
periods = [
    ("2026-01", date(2026, 1, 5)),
    ("2026-02", date(2026, 2, 5)),
    ("2026-03", date(2026, 3, 5)),
]
for period, sd in periods:
    if crud.quarter.get_quarter_by_period(db, period, pid) is None:
        crud.quarter.create_quarter(
            db,
            schemas.QuarterCreate(
                plan_id=pid, period=period, start_date=sd,
                budget=Decimal("10000"), note="图表测试",
            ),
        )
        print(f"  创建周期 {period}")

# 3) 购买记录（含一笔卖出，覆盖买卖两路径）
qid_map = {q.period: q.id for q in crud.quarter.list_quarters(db, pid)}
rows = [
    # period, date, fund_id, type, hands, price
    ("2026-01", date(2026, 1, 5), 9, "buy", 5, "2.65"),
    ("2026-01", date(2026, 1, 5), 10, "buy", 5, "2.20"),
    ("2026-01", date(2026, 1, 5), 11, "buy", 8, "1.28"),
    ("2026-01", date(2026, 1, 5), 12, "buy", 6, "1.15"),
    ("2026-02", date(2026, 2, 5), 9, "buy", 6, "2.68"),
    ("2026-02", date(2026, 2, 5), 10, "buy", 5, "2.25"),
    ("2026-02", date(2026, 2, 5), 11, "buy", 9, "1.30"),
    ("2026-02", date(2026, 2, 5), 12, "buy", 7, "1.17"),
    ("2026-03", date(2026, 3, 5), 9, "buy", 5, "2.70"),
    ("2026-03", date(2026, 3, 5), 10, "buy", 4, "2.28"),
    ("2026-03", date(2026, 3, 5), 11, "buy", 7, "1.31"),
    ("2026-03", date(2026, 3, 5), 12, "buy", 5, "1.18"),
    ("2026-03", date(2026, 3, 20), 11, "sell", 2, "1.33"),
]
items = []
for period, pd, fid, typ, hands, price in rows:
    items.append(
        schemas.PurchaseCreate(
            plan_id=pid, quarter_id=qid_map[period], fund_id=fid, type=typ,
            purchase_date=pd, price=Decimal(price), hands=hands, shares_per_hand=100,
        )
    )
# 复用现有方案时避免重复插入：判断该方案是否已有购买记录
from sqlalchemy import func, select
from app import models

existing_cnt = db.scalar(
    select(func.count()).select_from(models.PurchaseRecord).where(
        models.PurchaseRecord.plan_id == pid
    )
)
if existing_cnt == 0:
    crud.purchase.create_purchases(db, items)
    print(f"  创建购买记录 {len(items)} 条（含 1 笔卖出）")
else:
    print(f"  已有购买记录 {existing_cnt} 条，跳过插入")

db.close()
