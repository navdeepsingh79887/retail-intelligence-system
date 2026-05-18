from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict, Any


async def detect_demand_spikes(db: AsyncSession, z_threshold: float = 2.0) -> List[Dict]:
    sql = text("""
        WITH daily_units AS (
            SELECT
                c.category_name,
                d.full_date,
                SUM(t.quantity_sold) AS units_sold
            FROM "transaction" t
            JOIN date     d  ON t.date_id     = d.date_id
            JOIN product  p  ON t.product_id  = p.product_id
            JOIN category c  ON p.category_id = c.category_id
            WHERE t.is_return          = FALSE
              AND t.transaction_status = 'Completed'
              AND d.full_date >= (
                  SELECT MAX(d2.full_date) - INTERVAL '31 days'
                  FROM "transaction" t2
                  JOIN date d2 ON t2.date_id = d2.date_id
                  WHERE t2.is_return = FALSE
                    AND t2.transaction_status = 'Completed'
              )
            GROUP BY c.category_name, d.full_date
        ),
        latest_date AS (SELECT MAX(full_date) AS max_date FROM daily_units),
        stats AS (
            SELECT
                du.category_name,
                AVG(du.units_sold)    AS mean_units,
                STDDEV(du.units_sold) AS stddev_units,
                MAX(CASE WHEN du.full_date = ld.max_date
                    THEN du.units_sold END) AS latest_units
            FROM daily_units du, latest_date ld
            GROUP BY du.category_name
        )
        SELECT
            category_name,
            ROUND(mean_units::numeric,   2) AS mean_units,
            ROUND(stddev_units::numeric, 2) AS stddev_units,
            ROUND(latest_units::numeric, 2) AS latest_units,
            ROUND(
                (latest_units - mean_units)
                / GREATEST(stddev_units, 0.01)
            , 2) AS z_score
        FROM stats
        ORDER BY z_score DESC
    """)
    result = await db.execute(sql)
    rows = result.mappings().all()

    output = []
    for row in rows:
        z = float(row["z_score"] or 0)
        if   z >  z_threshold:  status = "SPIKE"
        elif z < -z_threshold:  status = "DROP"
        else:                   continue  # skip normal

        output.append({
            "category_name":      row["category_name"],
            "mean_units":         row["mean_units"],
            "stddev_units":       row["stddev_units"],
            "latest_units":       row["latest_units"],
            "z_score":            z,
            "status":             status,
            "recommended_action": (
                "Check festival calendar. Consider emergency restock."
                if status == "SPIKE"
                else "Investigate cause. Check stockouts or competitor pricing."
            ),
        })
    return output


async def get_all_category_demand_status(db: AsyncSession) -> List[Dict]:
    sql = text("""
        WITH daily_units AS (
            SELECT
                c.category_name,
                d.full_date,
                SUM(t.quantity_sold) AS units_sold
            FROM "transaction" t
            JOIN date     d  ON t.date_id     = d.date_id
            JOIN product  p  ON t.product_id  = p.product_id
            JOIN category c  ON p.category_id = c.category_id
            WHERE t.is_return          = FALSE
              AND t.transaction_status = 'Completed'
              AND d.full_date >= (
                  SELECT MAX(d2.full_date) - INTERVAL '31 days'
                  FROM "transaction" t2
                  JOIN date d2 ON t2.date_id = d2.date_id
                  WHERE t2.is_return = FALSE
                    AND t2.transaction_status = 'Completed'
              )
            GROUP BY c.category_name, d.full_date
        ),
        latest_date AS (SELECT MAX(full_date) AS max_date FROM daily_units)
        SELECT
            du.category_name,
            ROUND(AVG(du.units_sold)::numeric,    2) AS mean_units,
            ROUND(STDDEV(du.units_sold)::numeric, 2) AS stddev_units,
            ROUND(MAX(CASE WHEN du.full_date = ld.max_date
                THEN du.units_sold END)::numeric, 2)  AS latest_units
        FROM daily_units du, latest_date ld
        GROUP BY du.category_name
        ORDER BY mean_units DESC
    """)
    result = await db.execute(sql)
    rows = result.mappings().all()

    output = []
    for row in rows:
        mean = float(row["mean_units"]   or 0)
        std  = float(row["stddev_units"] or 0.01)
        lat  = float(row["latest_units"] or 0)
        z    = round((lat - mean) / max(std, 0.01), 2)
        if   z >  2.0: status = "SPIKE"
        elif z < -2.0: status = "DROP"
        else:           status = "NORMAL"
        output.append({**dict(row), "z_score": z, "status": status})
    return output


async def get_weather_demand_correlation(db: AsyncSession) -> List[Dict]:
    sql = text("""
        SELECT
            COALESCE(ef.weather_type, 'No External Data') AS weather_type,
            COUNT(DISTINCT d.full_date)                   AS days_count,
            COUNT(t.transaction_id)                       AS total_transactions,
            ROUND(AVG(t.final_sale_value)::numeric, 2)    AS avg_basket,
            ROUND(SUM(t.final_sale_value)::numeric, 2)    AS total_revenue,
            ROUND(AVG(ef.temperature_c)::numeric,  1)     AS avg_temp_c,
            ROUND(AVG(ef.rainfall_mm)::numeric,    2)     AS avg_rainfall_mm
        FROM "transaction" t
        JOIN date d ON t.date_id = d.date_id
        LEFT JOIN external_factors ef ON d.full_date = ef.record_date
        WHERE t.is_return          = FALSE
          AND t.transaction_status = 'Completed'
        GROUP BY ef.weather_type
        ORDER BY total_revenue DESC
    """)
    result = await db.execute(sql)
    return [dict(r) for r in result.mappings().all()]