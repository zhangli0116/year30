from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.schemas import ApiResponse, error, success
from app.services import datasource

router = APIRouter(prefix="/api/v1/datasource", tags=["datasource"])


@router.get("", response_model=ApiResponse[schemas.DataSourceOut])
def get_current(db: Session = Depends(get_db)) -> ApiResponse:
    """列出可选数据源 + 当前使用哪个（设置页切换用）。"""
    current = datasource.get_provider(db).name
    return success(
        schemas.DataSourceOut(providers=datasource.list_providers(), current=current)
    )


@router.put("", response_model=ApiResponse[schemas.DataSourceOut])
def set_current(
    payload: schemas.DataSourceUpdate, db: Session = Depends(get_db)
) -> ApiResponse:
    """切换「当前数据源」并持久化，返回更新后的状态。"""
    try:
        datasource.set_provider(db, payload.provider)
    except ValueError as e:
        return error(40006, str(e))
    return success(
        schemas.DataSourceOut(
            providers=datasource.list_providers(),
            current=datasource.get_provider(db).name,
        )
    )
