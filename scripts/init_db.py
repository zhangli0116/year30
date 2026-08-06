"""补建缺失的数据表（只建缺失的，不改动已有表结构）。

用法：在项目根目录执行
    python scripts/init_db.py
"""

from app import models  # noqa: F401  确保模型注册到 Base.metadata
from app.database import Base, engine

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("数据库表检查完成，缺失的表已补建。")
