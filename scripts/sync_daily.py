"""每日收盘后同步行情（独立运行，供 Windows 任务计划等调度）。

用法：在项目根目录执行
    python scripts/sync_daily.py

会补拉所有基金的缺失历史日线，并生成每日权益流水与每日现金流量（幂等）。
也可用系统自带任务计划每天 17:30 后调用一次：
    schtasks /create /tn "fund-sync" /tr "D:\\py_project\\year30\\.venv\\Scripts\\python.exe D:\\py_project\\year30\\scripts\\sync_daily.py" /sc weekly /d MON,TUE,WED,THU,FRI /st 17:35
"""

import sys
from pathlib import Path

# 保证从任意目录调用都能 import 到 app（否则 sys.path 只有 scripts/ 目录）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.services import sync  # noqa: E402


def main() -> None:
    with SessionLocal() as db:
        result = sync.sync_all(db)
    print(
        f"同步完成：基金 {result['funds']} 只，新增日线 {result['prices_inserted']} 根，"
        f"权益流水 {result['holdings_generated']} 天，现金流 {result['cash_generated']} 天，"
        f"失败 {result['failures']} 只（{result['range_start']} ~ {result['range_end']}）。"
    )


if __name__ == "__main__":
    main()
