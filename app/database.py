from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    # 取出连接前先 ping 一次，避免拿到已失效的旧连接
    pool_pre_ping=True,
    # 连接超过 1 小时回收，规避 MySQL 的 wait_timeout
    pool_recycle=3600,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def get_db():
    """FastAPI 依赖：为每个请求提供独立的数据库会话，结束后自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
