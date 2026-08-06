"""补建缺失的数据表（只建缺失的，不改动已有表结构）。

用法：在项目根目录执行
    python scripts/init_db.py
"""

import sys
from pathlib import Path

# 保证从任意目录调用都能 import 到 app（否则 sys.path 只有 scripts/ 目录）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402,F401  确保模型注册到 Base.metadata
from app.database import Base, engine  # noqa: E402

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("数据库表检查完成，缺失的表已补建。")
