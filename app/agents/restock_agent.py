# app/agents/restock_agent.py
# Autonomous restock scanning agent
# Scans all 6 stores, creates restock orders using forecast + inventory data

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict, Any
from datetime import date
import logging

from app.decision_engine.restock_decision import (
    get_restock_candidates,
    calculate_restock_quantity,
    get_stockout_alerts,
)
from app.forecasting import forecast_service

logger = logging.getLogger(__name__)

# YOUR 6 stores from the dataset
ALL_STORES = ["BBS-01", "BIL-01", "CUT-01", "DUR-01", "KOL-01", "RAI-01"]


async def run(
    db:       AsyncSession,
    store_id: str = None,     # None = scan all stores
    top_n:    int = 50,       # max products per store
) -> Dict[str, Any]:
    """
    Main agent entry point.
    Scans inventory, fetches forecasts, creates restock orders.
    Called daily by the scheduler OR via POST /api/agents/restock/run
    """
    logger.info(f"🤖 RestockAgent starting — store: {store_id or 'ALL'}")

    stores_to_scan = [store_id] if store_id else ALL_STORES
    all_orders     = []
    summary        = {}

    for sid in stores_to_scan:
        logger.info(f"  Scanning store {sid}...")
        store_orders = await _scan_store(db, sid, top_n)
        all_orders.extend(store_orders)
        summary[sid] = {
            "orders_created":    len(store_orders),
            "critical_count":    sum(1 for o in store_orders if "CRITICAL" in o.get("urgency", "")),
            "total_order_value": round(sum(o.get("estimated_order_value", 0) for o in store_orders), 2),
        }
        logger.info(f"  {sid}: {len(store_orders)} restock orders created")

    # Sort: most urgent first
    all_orders.sort(key=lambda x: (
        0 if "CRITICAL" in x.get("urgency", "") else
        1 if "HIGH"     in x.get("urgency", "") else 2
    ))

    result = {
        "run_date":        date.today().isoformat(),
        "stores_scanned":  stores_to_scan,
        "total_orders":    len(all_orders),
        "critical_orders": sum(1 for o in all_orders if "CRITICAL" in o.get("urgency", "")),
        "high_orders":     sum(1 for o in all_orders if "HIGH"     in o.get("urgency", "")),
        "store_summary":   summary,
        "restock_orders":  all_orders[:top_n * len(stores_to_scan)],
    }

    logger.info(f"✅ RestockAgent done — {len(all_orders)} total orders")
    return result


async def _scan_store(
    db:       AsyncSession,
    store_id: str,
    top_n:    int,
) -> List[Dict]:
    """Scans a single store and returns restock orders."""
    candidates = await get_restock_candidates(db, store_id=store_id)
    orders     = []

    for item in candidates[:top_n]:
        # Try to get Phase 4 forecast for this product+store
        forecast_qty = 0.0
        try:
            forecast = await forecast_service.predict_demand(
                db,
                product_id = item["product_id"],
                store_id   = store_id,
                days_ahead = 7,
            )
            if "error" not in forecast:
                forecast_qty = float(forecast.get("total_predicted_qty", 0))
        except Exception as e:
            logger.warning(f"Forecast unavailable for {item['product_id']}: {e}")

        # Calculate exact restock quantity
        restock_calc = calculate_restock_quantity(
            closing_stock   = float(item["closing_stock"]  or 0),
            safety_stock    = float(item["safety_stock"]   or 0),
            reorder_level   = float(item["reorder_level"]  or 0),
            lead_time_days  = int(item["lead_time_days"]   or 7),
            forecast_7d_qty = forecast_qty,
        )

        # Estimated order cost
        estimated_value = round(
            restock_calc["restock_qty"] * float(item["unit_cost"] or 0), 2
        )

        orders.append({
            "product_id":            item["product_id"],
            "product_name":          item["product_name"],
            "category":              item["category_name"],
            "store_id":              store_id,
            "store_name":            item["store_name"],
            "supplier_id":           item["supplier_id"],
            "supplier_name":         item["supplier_name"],
            "supplier_phone":        item["contact_phone"],
            "current_stock":         item["closing_stock"],
            "reorder_level":         item["reorder_level"],
            "restock_qty":           restock_calc["restock_qty"],
            "order_deadline":        restock_calc["order_deadline"],
            "lead_time_days":        restock_calc["lead_time_days"],
            "forecast_7d_qty":       forecast_qty,
            "estimated_order_value": estimated_value,
            "urgency":               item["urgency"],
            "calculation_method":    restock_calc["method"],
        })

    return orders
