from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict, Any


async def get_upcoming_festivals(db: AsyncSession, days_ahead: int = 30) -> List[Dict]:
    sql = text("""
        SELECT
            f.festival_id,
            f.festival_name,
            f.religion,
            f.festival_start_date,
            f.festival_end_date,
            f.festival_period_days,
            f.is_national_holiday,
            f.historically_consistent_uplift,
            f.demand_level,
            f.expected_demand_multiplier,
            (f.festival_start_date - CURRENT_DATE) AS days_until
        FROM festival f
        WHERE f.festival_start_date BETWEEN CURRENT_DATE
              AND CURRENT_DATE + :days_ahead * INTERVAL '1 day'
        ORDER BY f.festival_start_date ASC
    """)
    result = await db.execute(sql, {"days_ahead": days_ahead})
    return [dict(r) for r in result.mappings().all()]


async def get_festival_product_recommendations(db: AsyncSession, festival_id: str) -> List[Dict]:
    sql = text("""
        SELECT
            fp.rank,
            p.product_id,
            p.product_name,
            c.category_name,
            p.mrp,
            p.selling_price,
            ROUND(AVG(i.closing_stock)::numeric, 0) AS avg_closing_stock,
            ROUND(AVG(i.safety_stock)::numeric,  0) AS avg_safety_stock,
            ROUND(COALESCE((
                SELECT SUM(t.quantity_sold)::numeric
                       / GREATEST(COUNT(DISTINCT d.full_date), 1)
                FROM "transaction" t
                JOIN date d ON t.date_id = d.date_id
                WHERE t.product_id = p.product_id
                  AND t.is_return          = FALSE
                  AND t.transaction_status = 'Completed'
                  AND d.full_date >= CURRENT_DATE - INTERVAL '30 days'
            ), 0), 2) AS daily_avg_units
        FROM festival_products fp
        JOIN product  p  ON fp.product_id  = p.product_id
        JOIN category c  ON p.category_id  = c.category_id
        LEFT JOIN inventory i ON p.product_id = i.product_id
        WHERE fp.festival_id = :festival_id
        GROUP BY fp.rank, p.product_id, p.product_name,
                 c.category_name, p.mrp, p.selling_price
        ORDER BY fp.rank ASC
    """)
    result = await db.execute(sql, {"festival_id": festival_id})
    rows = result.mappings().all()

    output = []
    for row in rows:
        daily_avg = float(row["daily_avg_units"] or 0)
        recommended_extra = round(daily_avg * 2, 0)
        output.append({
            **dict(row),
            "recommended_extra_stock": recommended_extra,
            "stock_note": (
                "Low stock — order urgently"
                if (row["avg_closing_stock"] or 0) < recommended_extra
                else "Stock sufficient"
            ),
        })
    return output


async def get_festival_revenue_uplift(db: AsyncSession) -> Dict:
    sql = text("""
        SELECT
            ef.is_festival,
            COUNT(DISTINCT d.full_date)                           AS days_count,
            ROUND(SUM(t.final_sale_value)::numeric, 2)            AS total_revenue,
            ROUND(SUM(t.final_sale_value)::numeric
                  / GREATEST(COUNT(DISTINCT d.full_date), 1), 2) AS avg_daily_revenue,
            COUNT(t.transaction_id)                               AS total_transactions
        FROM "transaction" t
        JOIN date d ON t.date_id = d.date_id
        LEFT JOIN external_factors ef ON d.full_date = ef.record_date
        WHERE t.is_return          = FALSE
          AND t.transaction_status = 'Completed'
        GROUP BY ef.is_festival
    """)
    result = await db.execute(sql)
    rows = result.mappings().all()

    festival_rev = normal_rev = 0.0
    breakdown = []
    for row in rows:
        is_fest = row["is_festival"]
        label = "Festival Day" if is_fest is True else "Normal Day" if is_fest is False else "No External Data"
        rev = float(row["avg_daily_revenue"] or 0)
        breakdown.append({"day_type": label, **dict(row)})
        if is_fest is True:   festival_rev = rev
        elif is_fest is False: normal_rev  = rev

    uplift_pct = round((festival_rev - normal_rev) / max(normal_rev, 1) * 100, 2)
    return {
        "festival_uplift_pct": uplift_pct,
        "festival_avg_daily":  festival_rev,
        "normal_avg_daily":    normal_rev,
        "breakdown":           breakdown,
    }