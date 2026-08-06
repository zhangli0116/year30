from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


def get_setting(db: Session, key: str) -> str | None:
    row = db.scalar(select(models.AppSetting).where(models.AppSetting.key == key))
    return row.value if row else None


def get_all(db: Session) -> dict[str, str]:
    return dict(
        db.execute(
            select(models.AppSetting.key, models.AppSetting.value)
        ).all()
    )


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.scalar(select(models.AppSetting).where(models.AppSetting.key == key))
    if row is None:
        row = models.AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()
