from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_db
from app.analytics import (
    trend_detection,
    festival_analytics,
    taste_analysis,
    demand_spike_detector,
)

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


# ── TREND DETECTION ─────────────────────────────────────────────

@router.get("/trends/categories")
async def category_trends(db: AsyncSession = Depends(get_db)):
    return await trend_detection.get_category_trends(db)


@router.get("/trends/stores")
async def store_trends(db: AsyncSession = Depends(get_db)):
    return await trend_detection.get_store_trends(db)


# ── FESTIVAL ANALYTICS ──────────────────────────────────────────

@router.get("/festivals/upcoming")
async def upcoming_festivals(
    days_ahead: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    return await festival_analytics.get_upcoming_festivals(db, days_ahead)


@router.get("/festivals/{festival_id}/products")
async def festival_products(
    festival_id: str,
    db: AsyncSession = Depends(get_db),
):
    return await festival_analytics.get_festival_product_recommendations(db, festival_id)


@router.get("/festivals/uplift")
async def festival_uplift(db: AsyncSession = Depends(get_db)):
    return await festival_analytics.get_festival_revenue_uplift(db)


# ── TASTE ANALYSIS ──────────────────────────────────────────────

@router.get("/taste/stores")
async def store_preferences(db: AsyncSession = Depends(get_db)):
    return await taste_analysis.get_store_category_preferences(db)


@router.get("/taste/seasonal")
async def seasonal_mix(db: AsyncSession = Depends(get_db)):
    return await taste_analysis.get_seasonal_category_mix(db)


@router.get("/taste/payment-modes")
async def payment_modes(db: AsyncSession = Depends(get_db)):
    return await taste_analysis.get_payment_preference_by_store(db)


@router.get("/taste/customer-types")
async def customer_types(db: AsyncSession = Depends(get_db)):
    return await taste_analysis.get_customer_type_breakdown(db)


# ── DEMAND SPIKE DETECTOR ───────────────────────────────────────

@router.get("/spikes")
async def demand_spikes(
    z_threshold: float = Query(default=2.0, ge=1.0, le=4.0),
    db: AsyncSession = Depends(get_db),
):
    return await demand_spike_detector.detect_demand_spikes(db, z_threshold)


@router.get("/demand/all")
async def all_demand_status(db: AsyncSession = Depends(get_db)):
    return await demand_spike_detector.get_all_category_demand_status(db)


@router.get("/demand/weather")
async def weather_demand(db: AsyncSession = Depends(get_db)):
    return await demand_spike_detector.get_weather_demand_correlation(db)