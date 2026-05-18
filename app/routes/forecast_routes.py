from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.forecasting import forecast_service, model_loader

router = APIRouter(prefix="/api/forecast", tags=["Forecasting"])


@router.post("/train")
async def train_model(db: AsyncSession = Depends(get_db)):
    return await forecast_service.train_model(db)


@router.get("/model-info")
async def model_info():
    return model_loader.get_model_metadata()


@router.get("/demand")
async def predict_demand(
    product_id: str          = Query(..., examples=["OIL-FOR-001"]),
    store_id:   str          = Query(..., examples=["BBS-01"]),
    days_ahead: int          = Query(default=7, ge=1, le=30),
    db:         AsyncSession = Depends(get_db),
):
    return await forecast_service.predict_demand(db, product_id, store_id, days_ahead)


@router.get("/top-demand/{store_id}")
async def top_demand_forecast(
    store_id: str,
    top_n:    int          = Query(default=10, ge=1, le=50),
    db:       AsyncSession = Depends(get_db),
):
    return await forecast_service.get_top_demand_forecast(db, store_id, top_n)