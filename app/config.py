from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（year30/），用于稳定定位 .env，避免受启动目录影响
_BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """应用配置，从项目根目录的 .env 读取，也可用环境变量覆盖。"""

    # ---- 服务监听地址（供 python -m app.main 启动时使用）----
    HTTP_HOST: str = "127.0.0.1"
    HTTP_PORT: int = 8000

    # ---- 数据库连接 ----
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "123456"
    DB_NAME: str = "fund_invest"

    # ---- CORS 允许来源 ----
    # 逗号分隔，如 "http://localhost:5173,http://127.0.0.1:5173"；"*" 表示全部放开
    CORS_ORIGINS: str = "*"

    model_config = SettingsConfigDict(
        env_file=_BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


settings = Settings()
