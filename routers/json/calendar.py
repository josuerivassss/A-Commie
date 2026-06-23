from fastapi import APIRouter, Query
from schemas.responses import HTTPResponse
from calendar import month as get_month
from datetime import datetime

router = APIRouter(prefix="/json", tags=["JSON"])

@router.get("/calendar", 
    description="Returns a calendar for the specified month and year.",
    response_model=HTTPResponse
)
async def calendar(
    year: int = Query(2023, description="The year calendar", le=2100, ge=1000),
    month: int = Query(datetime.now().month, description="The month calendar", le=12, ge=1)
):
    return HTTPResponse.use(data=get_month(year, month))