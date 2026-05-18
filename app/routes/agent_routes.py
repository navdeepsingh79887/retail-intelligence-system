from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.agents.restock_agent      import run as restock_run
from app.agents.notification_agent import build_restock_alerts, build_expiry_alerts, dispatch
from app.agents.supplier_agent     import prepare_supplier_orders

router = APIRouter(prefix="/api/agents", tags=["Agents"])


@router.post("/restock/run")
async def run_restock_agent(
    store_id: Optional[str] = Query(default=None, examples=["BBS-01"]),
    top_n:    int           = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await restock_run(db, store_id=store_id, top_n=top_n)


@router.post("/restock/notify")
async def run_and_notify(
    dry_run:  bool          = Query(default=True),
    store_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    agent_result    = await restock_run(db, store_id=store_id)
    orders          = agent_result.get("restock_orders", [])
    alerts          = build_restock_alerts(orders)
    dispatched      = await dispatch(alerts, dry_run=dry_run)
    supplier_orders = await prepare_supplier_orders(orders, dry_run=dry_run)

    return {
        "restock_summary":   agent_result["store_summary"],
        "total_orders":      agent_result["total_orders"],
        "alerts_dispatched": dispatched,
        "supplier_orders":   supplier_orders,
        "dry_run":           dry_run,
    }


@router.post("/expiry/notify")
async def expiry_notify(
    days_window: int  = Query(default=30),
    dry_run:     bool = Query(default=True),
    db: AsyncSession  = Depends(get_db),
):
    from app.decision_engine.pricing_decision import get_expiry_pricing_alerts
    items      = await get_expiry_pricing_alerts(db, days_window)
    alerts     = build_expiry_alerts(items)
    dispatched = await dispatch(alerts, dry_run=dry_run)
    return {
        "expiry_items_found": len(items),
        "alerts_built":       len(alerts),
        "alerts_dispatched":  dispatched,
        "dry_run":            dry_run,
    }