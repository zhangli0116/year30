from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.logger import logger
from app.schemas import ApiResponse, error, success

router = APIRouter(prefix="/api/v1/plans", tags=["plans"])


@router.get("", response_model=ApiResponse[list[schemas.PlanOut]])
def list_plans(db: Session = Depends(get_db)) -> ApiResponse:
    return success([crud.plan.plan_out(db, p) for p in crud.plan.list_plans(db)])


@router.post("", response_model=ApiResponse[schemas.PlanOut])
def create_plan(payload: schemas.PlanCreate, db: Session = Depends(get_db)) -> ApiResponse:
    if crud.plan.get_plan_by_name(db, payload.name):
        return error(40007, f"方案「{payload.name}」已存在")
    for f in payload.funds:
        if crud.fund.get_fund(db, f.fund_id) is None:
            return error(40003, f"基金 {f.fund_id} 不存在")
    try:
        plan = crud.plan.create_plan(db, payload)
    except ValueError as e:
        return error(40008, str(e))
    logger.info(f"创建方案 id={plan.id} {payload.name}")
    return success(crud.plan.plan_out(db, plan))


@router.get("/{plan_id}", response_model=ApiResponse[schemas.PlanOut])
def get_plan(plan_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    plan = crud.plan.get_plan(db, plan_id)
    if plan is None:
        return error(40403, f"方案 {plan_id} 不存在")
    return success(crud.plan.plan_out(db, plan))


@router.put("/{plan_id}", response_model=ApiResponse[schemas.PlanOut])
def update_plan(plan_id: int, payload: schemas.PlanUpdate, db: Session = Depends(get_db)) -> ApiResponse:
    plan = crud.plan.get_plan(db, plan_id)
    if plan is None:
        return error(40403, f"方案 {plan_id} 不存在")
    if payload.name is not None:
        exist = crud.plan.get_plan_by_name(db, payload.name)
        if exist and exist.id != plan_id:
            return error(40007, f"方案「{payload.name}」已存在")
    try:
        plan = crud.plan.update_plan(db, plan, payload)
    except ValueError as e:
        return error(40008, str(e))
    logger.info(f"更新方案 id={plan.id} {plan.name}")
    return success(crud.plan.plan_out(db, plan))


@router.delete("/{plan_id}", response_model=ApiResponse)
def delete_plan(plan_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    plan = crud.plan.get_plan(db, plan_id)
    if plan is None:
        return error(40403, f"方案 {plan_id} 不存在")
    if not crud.plan.delete_plan(db, plan):
        return error(40009, "该方案已有季度/购买记录，不能删除")
    logger.info(f"删除方案 id={plan_id} {plan.name}")
    return success(message="删除成功")
