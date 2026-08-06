"""loguru 日志配置。

日志输出到控制台 + 项目根目录 log/ 文件夹（按天滚动，保留 30 天）。
各模块统一 `from app.logger import logger` 使用。
"""
import sys
from pathlib import Path

from loguru import logger

# 项目根目录（app/ 的上一级）
LOG_DIR = Path(__file__).resolve().parent.parent / "log"
LOG_DIR.mkdir(exist_ok=True)

_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

# 移除 loguru 默认 handler，统一配置
logger.remove()
# 控制台
logger.add(sys.stderr, level="INFO", format=_FORMAT, enqueue=True, backtrace=False, diagnose=False)
# 文件：按天滚动，保留 30 天，UTF-8
logger.add(
    LOG_DIR / "app_{time:YYYY-MM-DD}.log",
    level="INFO",
    format=_FORMAT,
    rotation="00:00",
    retention="30 days",
    encoding="utf-8",
    enqueue=True,
    backtrace=False,
    diagnose=False,
)

__all__ = ["logger", "LOG_DIR"]
