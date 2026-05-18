from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict


async def get_store_category_preferences(db: AsyncSession) -> List[Dict]:
    sql = text("""
        WITH store_totals AS (
            SELECT store_id, SUM(final_sale_value) AS store_total
            FROM "transaction"
            WHERE is_return = FALSE AND transaction_status = 'Completed'
            GROUP BY store_id
        ),
        store_cat AS (
            SELECT
                s.store_name, s.city, s.store_id,
                c.category_name,
                ROUND(SUM(t.final_sale_value)::numeric, 2) AS category_revenue,
                ROUND(SUM(t.final_sale_value)::numeric
                      / st.store_total * 100, 2)           AS revenue_share_pct,
                RANK() OVER (
                    PARTITION BY s.store_name
                    ORDER BY SUM(t.final_sale_value) DESC
                ) AS rank
            FROM "transaction" t
            JOIN store    s  ON t.store_id    = s.store_id
            JOIN product  p  ON t.product_id  = p.product_id
            JOIN category c  ON p.category_id = c.category_id
            JOIN store_totals st ON t.store_id = st.store_id
            WHERE t.is_return = FALSE
              AND t.transaction_status = 'Completed'
              AND s.store_id IN ('BBS-01','BIL-01','CUT-01','DUR-01','KOL-01','RAI-01')
            GROUP BY s.store_name, s.city, s.store_id, c.category_name, st.store_total
        )
        SELECT * FROM store_cat WHERE rank <= 5
        ORDER BY store_id, rank
    """)
    result = await db.execute(sql)
    return [dict(r) for r in result.mappings().all()]


async def get_seasonal_category_mix(db: AsyncSession) -> List[Dict]:
    sql = text("""
        SELECT
            d.season,
            c.category_name,
            SUM(t.quantity_sold)                       AS total_units,
            ROUND(SUM(t.final_sale_value)::numeric, 2) AS total_revenue,
            RANK() OVER (
                PARTITION BY d.season
                ORDER BY SUM(t.final_sale_value) DESC
            ) AS rank_in_season
        FROM "transaction" t
        JOIN date     d  ON t.date_id     = d.date_id
        JOIN product  p  ON t.product_id  = p.product_id
        JOIN category c  ON p.category_id = c.category_id
        WHERE t.is_return = FALSE AND t.transaction_status = 'Completed'
        GROUP BY d.season, c.category_name
        ORDER BY d.season, rank_in_season
    """)
    result = await db.execute(sql)
    return [dict(r) for r in result.mappings().all()]


async def get_payment_preference_by_store(db: AsyncSession) -> List[Dict]:
    sql = text("""
        SELECT
            s.store_name, s.store_id,
            t.payment_mode,
            COUNT(*) AS txn_count,
            ROUND(COUNT(*) * 100.0
                / SUM(COUNT(*)) OVER (PARTITION BY s.store_name), 2) AS pct
        FROM "transaction" t
        JOIN store s ON t.store_id = s.store_id
        WHERE t.is_return = FALSE
          AND t.transaction_status = 'Completed'
          AND t.payment_mode IS NOT NULL
          AND s.store_id IN ('BBS-01','BIL-01','CUT-01','DUR-01','KOL-01','RAI-01')
        GROUP BY s.store_name, s.store_id, t.payment_mode
        ORDER BY s.store_id, txn_count DESC
    """)
    result = await db.execute(sql)
    return [dict(r) for r in result.mappings().all()]


async def get_customer_type_breakdown(db: AsyncSession) -> List[Dict]:
    sql = text("""
        SELECT
            s.store_name, s.store_id,
            cu.customer_type,
            COUNT(DISTINCT t.customer_id)              AS unique_customers,
            COUNT(t.transaction_id)                    AS total_transactions,
            ROUND(SUM(t.final_sale_value)::numeric, 2) AS total_spend,
            ROUND(AVG(t.final_sale_value)::numeric, 2) AS avg_basket
        FROM "transaction" t
        JOIN store    s  ON t.store_id    = s.store_id
        JOIN customer cu ON t.customer_id = cu.customer_id
        WHERE t.is_return = FALSE
          AND t.transaction_status = 'Completed'
          AND s.store_id IN ('BBS-01','BIL-01','CUT-01','DUR-01','KOL-01','RAI-01')
          AND cu.customer_type IN ('NEW', 'REPEAT', 'INACTIVE')
        GROUP BY s.store_name, s.store_id, cu.customer_type
        ORDER BY s.store_id, total_transactions DESC
    """)
    result = await db.execute(sql)
    return [dict(r) for r in result.mappings().all()]