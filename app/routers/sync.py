from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.schemas import ApiResponse, success
from app.services import sync as sync_service

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@router.post("/all", response_model=ApiResponse[schemas.SyncAllOut])
def sync_all(db: Session = Depends(get_db)) -> ApiResponse:
    """一键同步：补拉所有基金缺失日线，并生成每日权益流水与现金流量（幂等）。"""
    return success(schemas.SyncAllOut(**sync_service.sync_all(db)))
