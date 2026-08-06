from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.schemas import ApiResponse, error, success
from app.services import rebalance as rebalance_service

router = APIRouter(prefix="/api/v1/rebalance", tags=["rebalance"])


@router.get("/check", response_model=ApiResponse[schemas.RebalanceOut])
def rebalance_check(
    plan_id: int = Query(..., description="方案ID"),
    r_band: float | None = Query(None),
    min_abs: float | None = Query(None),
    max_abs: float | None = Query(None),
    amount_floor: float | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """再平衡体检：某方案下各基金目标/当前占比/偏离/阈值/状态/建议动作 + 现金行。

    可传 r_band/min_abs/max_abs/amount_floor 临时覆盖参数做预览（不落库）。
    """
    if crud.plan.get_plan(db, plan_id) is None:
        return error(40403, f"方案 {plan_id} 不存在")
    overrides = {
        k: v
        for k, v in {
            "r_band": r_band,
            "min_abs": min_abs,
            "max_abs": max_abs,
            "amount_floor": amount_floor,
        }.items()
        if v is not None
    }
    params = rebalance_service.get_params(db)
    params.update(overrides)
    return success(
        schemas.RebalanceOut(**rebalance_service.analyze(db, plan_id, params=params))
    )


@router.get("/params", response_model=ApiResponse[schemas.RebalanceParams])
def get_params(
    plan_id: int | None = Query(None, description="方案ID（判定阈值全局，可不传）"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    return success(schemas.RebalanceParams(**rebalance_service.get_params(db)))


@router.put("/params", response_model=ApiResponse[schemas.RebalanceParams])
def update_params(
    payload: schemas.RebalanceParamsUpdate,
    plan_id: int | None = Query(None, description="方案ID（判定阈值全局，可不传）"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """更新判定参数（只写传入字段），返回更新后的完整参数。"""
    updated = rebalance_service.save_params(db, payload.model_dump(exclude_unset=True))
    return success(schemas.RebalanceParams(**updated))
