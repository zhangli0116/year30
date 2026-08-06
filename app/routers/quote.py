from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ApiResponse, QuoteListOut, error, success
from app.services import datasource

router = APIRouter(prefix="/api/v1/quotes", tags=["quotes"])


@router.get("", response_model=ApiResponse[QuoteListOut])
def get_quotes(
    codes: str = Query(..., description="逗号分隔的基金/ETF 代码，如 513500,513100"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """实时行情（含五档盘口），按「当前数据源」取数（设置页可切换腾讯/新浪）。"""
    code_list = [
        c.strip()
        for c in codes.split(",")
        if c.strip().isdigit() and len(c.strip()) == 6
    ]
    if not code_list:
        return error(40004, "请提供合法的 6 位基金代码")
    provider = datasource.get_provider(db)
    symbol_map = datasource.resolve_symbols(db, code_list)
    symbols = [symbol_map[c] for c in code_list if c in symbol_map]
    quotes = provider.fetch_quotes(symbols)
    return success(QuoteListOut(quotes=quotes, source=provider.name))
