import pandas as pd
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def build_feature_table(db: AsyncSession) -> pd.DataFrame:
    """
    Pulls transaction data + context features from DB.
    Returns a DataFrame with one row per (product_id, store_id, date).
    """
    sql = text("""
        SELECT
            d.full_date,
            t.product_id,
            p.product_name,
            c.category_name,
            t.store_id,
            SUM(t.quantity_sold)              AS quantity_sold,
            ROUND(SUM(t.final_sale_value), 2) AS total_revenue,
            d.day_name,
            d.is_weekend,
            d.season,
            d.month_number,
            COALESCE(ef.is_festival,        FALSE) AS is_festival,
            COALESCE(ef.is_public_holiday,  FALSE) AS is_public_holiday,
            COALESCE(ef.weather_type,   'Unknown') AS weather_type,
            COALESCE(ef.temperature_c,         20) AS temperature_c,
            COALESCE(ef.rainfall_mm,            0) AS rainfall_mm,
            COALESCE(ef.is_marriage_season, FALSE) AS is_marriage_season
        FROM transaction t
        JOIN date d         ON t.date_id      = d.date_id
        JOIN product p      ON t.product_id   = p.product_id
        JOIN category c     ON p.category_id  = c.category_id
        JOIN store s        ON t.store_id     = s.store_id
        LEFT JOIN external_factors ef
            ON d.full_date = ef.record_date
            AND ef.region  = s.region
        WHERE t.is_return          = FALSE
          AND t.transaction_status = 'Completed'
        GROUP BY
            d.full_date, t.product_id, p.product_name,
            c.category_name, t.store_id, d.day_name,
            d.is_weekend, d.season, d.month_number,
            ef.is_festival, ef.is_public_holiday, ef.weather_type,
            ef.temperature_c, ef.rainfall_mm, ef.is_marriage_season
        ORDER BY t.product_id, t.store_id, d.full_date
    """)

    result = await db.execute(sql)
    df = pd.DataFrame(result.mappings().all())

    if df.empty:
        return df

    # Types
    df["full_date"]           = pd.to_datetime(df["full_date"])
    df["quantity_sold"]       = pd.to_numeric(df["quantity_sold"], errors="coerce").fillna(0)
    df["is_weekend"]          = df["is_weekend"].astype(int)
    df["is_festival"]         = df["is_festival"].astype(int)
    df["is_public_holiday"]   = df["is_public_holiday"].astype(int)
    df["is_marriage_season"]  = df["is_marriage_season"].astype(int)

    # Lag features
    df = df.sort_values(["product_id", "store_id", "full_date"])
    grp = df.groupby(["product_id", "store_id"])["quantity_sold"]

    df["lag_7d_qty"]  = grp.shift(7)
    df["lag_14d_qty"] = grp.shift(14)
    df["lag_30d_qty"] = grp.shift(30)

    df["rolling_7d_avg"]  = grp.transform(lambda x: x.shift(1).rolling(7,  min_periods=1).mean())
    df["rolling_30d_avg"] = grp.transform(lambda x: x.shift(1).rolling(30, min_periods=1).mean())

    # Encode categoricals
    day_map    = {"Monday":1,"Tuesday":2,"Wednesday":3,"Thursday":4,"Friday":5,"Saturday":6,"Sunday":7}
    season_map = {"Winter":1,"Summer":2,"Monsoon":3,"Autumn":4}

    df["day_of_week"] = df["day_name"].map(day_map).fillna(0).astype(int)
    df["season_code"] = df["season"].map(season_map).fillna(0).astype(int)

    lag_cols = ["lag_7d_qty","lag_14d_qty","lag_30d_qty","rolling_7d_avg","rolling_30d_avg"]
    df[lag_cols] = df[lag_cols].fillna(0)

    return df


def get_feature_columns() -> list:
    return [
        "day_of_week", "is_weekend", "season_code", "month_number",
        "is_festival", "is_public_holiday", "is_marriage_season",
        "temperature_c", "rainfall_mm",
        "lag_7d_qty", "lag_14d_qty", "lag_30d_qty",
        "rolling_7d_avg", "rolling_30d_avg",
    ]