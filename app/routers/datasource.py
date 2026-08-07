from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.schemas import ApiResponse, error, success
from app.services import datasource

router = APIRouter(prefix="/api/v1/datasource", tags=["datasource"])


@router.get("", response_model=ApiResponse[schemas.DataSourceOut])
def get_current(db: Session = Depends(get_db)) -> ApiResponse:
    """按 fund_type 分组列出数据源配置（设置页切换用）。"""
    return success(schemas.DataSourceOut(types=datasource.list_type_configs(db)))


@router.put("", response_model=ApiResponse[schemas.DataSourceOut])
def set_current(
    payload: schemas.DataSourceUpdate, db: Session = Depends(get_db)
) -> ApiResponse:
    """设置某 fund_type 的数据源并持久化，返回更新后的完整配置。"""
    try:
        datasource.set_provider(db, payload.fund_type, payload.provider)
    except ValueError as e:
        return error(40006, str(e))
    return success(schemas.DataSourceOut(types=datasource.list_type_configs(db)))
