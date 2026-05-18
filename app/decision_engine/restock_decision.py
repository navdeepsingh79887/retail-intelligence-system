from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict, Any, Optional
from datetime import date, timedelta


async def get_restock_candidates(
    db: AsyncSession,
    store_id: Optional[str] = None
) -> List[Dict[str, Any]]:

    store_filter = "AND i.store_id = :store_id" if store_id else ""

    sql = text(f"""
        SELECT
            i.inventory_id,
            i.product_id,
            p.product_name,
            c.category_name,
            i.store_id,
            s.store_name,
            i.closing_stock,
            i.reorder_level,
            i.safety_stock,
            i.reorder_point,
            COALESCE(i.lead_time_days, sup.lead_time_days, 7) AS lead_time_days,
            i.unit_cost,
            p.supplier_id,
            sup.supplier_name,
            sup.contact_phone,
            ROUND((i.reorder_level - i.closing_stock)::NUMERIC, 0) AS restock_gap,
            ROUND((i.closing_stock * i.unit_cost)::NUMERIC, 2)     AS current_stock_value,
            CASE
                WHEN i.units_consumed > 0
                THEN ROUND((i.closing_stock::NUMERIC / i.units_consumed), 1)
                ELSE 999
            END AS days_until_stockout
        FROM inventory i
        JOIN product  p   ON i.product_id  = p.product_id
        JOIN category c   ON p.category_id = c.category_id
        JOIN store    s   ON i.store_id    = s.store_id
        JOIN supplier sup ON p.supplier_id = sup.supplier_id
        WHERE i.closing_stock <= i.reorder_level
          AND i.closing_stock >= 0
          {store_filter}
        ORDER BY restock_gap DESC, days_until_stockout ASC
    """)

    params = {"store_id": store_id} if store_id else {}
    result = await db.execute(sql, params)
    rows   = result.mappings().all()

    output = []
    for row in rows:
        r      = dict(row)
        lead   = int(r["lead_time_days"] or 7)
        gap    = float(r["restock_gap"]  or 0)
        safety = float(r["safety_stock"] or 0)

        order_deadline = date.today() + timedelta(days=max(1, lead - 2))
        days_left      = float(r["days_until_stockout"] or 999)

        if days_left <= lead:
            urgency = "🔴 CRITICAL — Stock out before delivery"
        elif days_left <= lead * 2:
            urgency = "🟠 HIGH — Order within 2 days"
        elif gap > safety:
            urgency = "🟡 MEDIUM — Order this week"
        else:
            urgency = "🟢 LOW — Monitor"

        r["order_deadline"]      = order_deadline.isoformat()
        r["urgency"]             = urgency
        r["days_until_stockout"] = days_left
        output.append(r)

    return output


def calculate_restock_quantity(
    closing_stock:   float,
    safety_stock:    float,
    reorder_level:   float,
    lead_time_days:  int,
    forecast_7d_qty: float,
) -> Dict[str, Any]:

    if forecast_7d_qty <= 0:
        restock_qty = max(0, reorder_level - closing_stock + safety_stock)
    else:
        daily_demand       = forecast_7d_qty / 7
        demand_during_lead = daily_demand * lead_time_days
        restock_qty        = demand_during_lead + safety_stock - closing_stock
        restock_qty        = max(restock_qty, reorder_level - closing_stock)

    restock_qty    = max(0, round(restock_qty, 0))
    order_deadline = date.today() + timedelta(days=max(1, lead_time_days - 2))

    return {
        "restock_qty":      restock_qty,
        "order_deadline":   order_deadline.isoformat(),
        "lead_time_days":   lead_time_days,
        "daily_demand_est": round(forecast_7d_qty / 7, 2),
        "method":           "forecast-based" if forecast_7d_qty > 0 else "gap-based",
    }


async def get_stockout_alerts(db: AsyncSession) -> List[Dict]:

    sql = text("""
        SELECT
            i.product_id,
            p.product_name,
            c.category_name,
            i.store_id,
            s.store_name,
            i.closing_stock,
            i.safety_stock,
            COALESCE(i.lead_time_days, sup.lead_time_days, 7) AS lead_time_days,
            sup.supplier_name,
            sup.contact_phone
        FROM inventory i
        JOIN product  p   ON i.product_id  = p.product_id
        JOIN category c   ON p.category_id = c.category_id
        JOIN store    s   ON i.store_id    = s.store_id
        JOIN supplier sup ON p.supplier_id = sup.supplier_id
        WHERE i.is_stockout = TRUE
           OR i.closing_stock = 0
        ORDER BY c.category_name, i.store_id
    """)

    result = await db.execute(sql)
    return [dict(r) for r in result.mappings().all()]