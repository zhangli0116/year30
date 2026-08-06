from fastapi import APIRouter, Query

from app.schemas import ApiResponse, QuoteListOut, error, success
from app.services import quote as quote_service

router = APIRouter(prefix="/api/v1/quotes", tags=["quotes"])


@router.get("", response_model=ApiResponse[QuoteListOut])
def get_quotes(
    codes: str = Query(..., description="逗号分隔的基金/ETF 代码，如 513500,513100"),
) -> ApiResponse:
    code_list = [
        c.strip()
        for c in codes.split(",")
        if c.strip().isdigit() and len(c.strip()) == 6
    ]
    if not code_list:
        return error(40004, "请提供合法的 6 位基金代码")
    quotes = quote_service.fetch_quotes(code_list)
    return success(QuoteListOut(quotes=quotes, source="tencent"))
