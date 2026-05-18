from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.decision_engine import restock_decision, pricing_decision

router = APIRouter(prefix="/api/decisions", tags=["Decision Engine"])


@router.get("/restock")
async def get_restock_candidates(
    store_id: Optional[str] = Query(default=None, examples=["BBS-01"]),
    db: AsyncSession = Depends(get_db),
):
    return await restock_decision.get_restock_candidates(db, store_id)


@router.get("/stockouts")
async def get_stockouts(db: AsyncSession = Depends(get_db)):
    return await restock_decision.get_stockout_alerts(db)


@router.get("/expiry-alerts")
async def get_expiry_alerts(
    days_window: int = Query(default=90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    return await pricing_decision.get_expiry_pricing_alerts(db, days_window)


@router.get("/low-margin")
async def get_low_margin(db: AsyncSession = Depends(get_db)):
    return await pricing_decision.get_low_margin_products(db)