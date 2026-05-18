from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict, Any


async def get_category_trends(db: AsyncSession) -> List[Dict[str, Any]]:
    sql = text("""
        WITH daily_rev AS (
            SELECT
                c.category_name,
                d.full_date,
                SUM(t.final_sale_value) AS daily_revenue,
                SUM(t.quantity_sold)    AS daily_units
            FROM "transaction" t
            JOIN date     d  ON t.date_id     = d.date_id
            JOIN product  p  ON t.product_id  = p.product_id
            JOIN category c  ON p.category_id = c.category_id
            WHERE t.is_return          = FALSE
              AND t.transaction_status = 'Completed'
              AND d.full_date >= (
                  SELECT MAX(d2.full_date) - INTERVAL '30 days'
                  FROM "transaction" t2
                  JOIN date d2 ON t2.date_id = d2.date_id
                  WHERE t2.is_return = FALSE
                    AND t2.transaction_status = 'Completed'
              )
            GROUP BY c.category_name, d.full_date
        ),
        latest_date AS (
            SELECT MAX(full_date) AS max_date FROM daily_rev
        ),
        period_avg AS (
            SELECT
                dr.category_name,
                AVG(CASE
                    WHEN dr.full_date > ld.max_date - INTERVAL '7 days'
                    THEN dr.daily_revenue END)                      AS last_7d_avg,
                AVG(CASE
                    WHEN dr.full_date <= ld.max_date - INTERVAL '7 days'
                     AND dr.full_date >  ld.max_date - INTERVAL '14 days'
                    THEN dr.daily_revenue END)                      AS prev_7d_avg,
                SUM(dr.daily_revenue)                               AS total_30d_revenue,
                SUM(dr.daily_units)                                 AS total_30d_units
            FROM daily_rev dr, latest_date ld
            GROUP BY dr.category_name
        )
        SELECT
            category_name,
            ROUND(last_7d_avg::numeric, 2)       AS last_7d_avg,
            ROUND(prev_7d_avg::numeric, 2)       AS prev_7d_avg,
            ROUND(
                (last_7d_avg - prev_7d_avg)
                / GREATEST(prev_7d_avg, 1) * 100
            , 2)                                 AS change_pct,
            ROUND(total_30d_revenue::numeric, 2) AS total_30d_revenue,
            total_30d_units
        FROM period_avg
        ORDER BY change_pct DESC
    """)
    result = await db.execute(sql)
    rows = result.mappings().all()

    output = []
    for row in rows:
        change = float(row["change_pct"] or 0)
        if   change >=  25: label = "SPIKE"
        elif change >=  10: label = "RISING"
        elif change >= -10: label = "STABLE"
        elif change >= -25: label = "FALLING"
        else:               label = "CRASH"

        action = (
            "Increase stock. Check for upcoming festivals."
            if label in ("SPIKE", "RISING")
            else "Review pricing. Check competitor activity."
            if label in ("FALLING", "CRASH")
            else "No immediate action needed."
        )
        output.append({
            "category_name":       row["category_name"],
            "last_7d_avg_revenue": row["last_7d_avg"],
            "prev_7d_avg_revenue": row["prev_7d_avg"],
            "change_pct":          change,
            "trend_label":         label,
            "total_30d_revenue":   row["total_30d_revenue"],
            "total_30d_units":     row["total_30d_units"],
            "recommended_action":  action,
        })
    return output


async def get_store_trends(db: AsyncSession) -> List[Dict[str, Any]]:
    sql = text("""
        WITH daily_rev AS (
            SELECT
                s.store_name,
                d.full_date,
                SUM(t.final_sale_value) AS daily_revenue
            FROM "transaction" t
            JOIN date  d ON t.date_id  = d.date_id
            JOIN store s ON t.store_id = s.store_id
            WHERE t.is_return          = FALSE
              AND t.transaction_status = 'Completed'
              AND d.full_date >= (
                  SELECT MAX(d2.full_date) - INTERVAL '30 days'
                  FROM "transaction" t2
                  JOIN date d2 ON t2.date_id = d2.date_id
                  WHERE t2.is_return = FALSE
                    AND t2.transaction_status = 'Completed'
              )
            GROUP BY s.store_name, d.full_date
        ),
        latest_date AS (SELECT MAX(full_date) AS max_date FROM daily_rev),
        period_avg AS (
            SELECT
                dr.store_name,
                AVG(CASE WHEN dr.full_date > ld.max_date - INTERVAL '7 days'
                    THEN dr.daily_revenue END) AS last_7d_avg,
                AVG(CASE WHEN dr.full_date <= ld.max_date - INTERVAL '7 days'
                     AND dr.full_date >  ld.max_date - INTERVAL '14 days'
                    THEN dr.daily_revenue END) AS prev_7d_avg
            FROM daily_rev dr, latest_date ld
            GROUP BY dr.store_name
        )
        SELECT
            store_name,
            ROUND(last_7d_avg::numeric, 2) AS last_7d_avg,
            ROUND(prev_7d_avg::numeric, 2) AS prev_7d_avg,
            ROUND((last_7d_avg - prev_7d_avg)
                / GREATEST(prev_7d_avg, 1) * 100, 2) AS change_pct
        FROM period_avg
        ORDER BY change_pct DESC
    """)
    result = await db.execute(sql)
    rows = result.mappings().all()

    output = []
    for row in rows:
        change = float(row["change_pct"] or 0)
        if   change >=  25: label = "SPIKE"
        elif change >=  10: label = "RISING"
        elif change >= -10: label = "STABLE"
        elif change >= -25: label = "FALLING"
        else:               label = "CRASH"
        output.append({
            "store_name":  row["store_name"],
            "last_7d_avg": row["last_7d_avg"],
            "prev_7d_avg": row["prev_7d_avg"],
            "change_pct":  change,
            "trend_label": label,
        })
    return output