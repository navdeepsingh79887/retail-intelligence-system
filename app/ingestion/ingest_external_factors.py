import os
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from app.core.database import SessionLocal
from app.models.external_factors import ExternalFactors

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

def ingest_external_factors(file_path: str):
    df = pd.read_csv(file_path, dtype=str)

    # Drop non-numeric date_id rows (legends/footers)
    df = df[pd.to_numeric(df["date_id"], errors="coerce").notna()]

    # factor_id from date_id
    df["factor_id"] = df["date_id"].apply(lambda x: int(float(x)))

    # record_date — Date only
    df["record_date"] = pd.to_datetime(df["full_date"], errors="coerce").dt.date
    df["record_date"] = df["record_date"].where(df["record_date"].notna(), None)

    # Numeric columns
    for col in ["temperature_c", "rainfall_mm", "humidity_pct"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # String columns
    df["weather_type"] = df["weather_type"].astype(str).str.strip()
    df["region"]       = df["region"].astype(str).str.strip()

    # Boolean columns
    bool_cols = [
        "is_school_holiday", "is_school_reopening", "is_festival",
        "is_weekend", "is_public_holiday", "is_marriage_season",
        "is_harvest_season", "is_exam_season"
    ]
    for col in bool_cols:
        df[col] = df[col].map(
            lambda v: True if str(v).strip().upper() in ["TRUE", "1", "YES"] else False
        )

    # Timestamps
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["created_at"] = df["created_at"].where(df["created_at"].notna(), None)
    df["updated_at"] = df["created_at"]  # fallback

    records = df[[
        "factor_id", "record_date", "region",
        "temperature_c", "rainfall_mm", "humidity_pct", "weather_type",
        "is_school_holiday", "is_school_reopening", "is_festival",
        "is_weekend", "is_public_holiday", "is_marriage_season",
        "is_harvest_season", "is_exam_season",
        "created_at", "updated_at"
    ]].to_dict(orient="records")

    # Fix NaN to None
    for record in records:
        for key, val in record.items():
            if isinstance(val, float) and pd.isna(val):
                record[key] = None

    db = SessionLocal()
    try:
        stmt = insert(ExternalFactors).values(records).on_conflict_do_nothing(
            index_elements=["factor_id"]
        )
        db.execute(stmt)
        db.commit()
        print(f"✅ Ingestion complete. {len(records)} records processed.")

    except Exception as e:
        db.rollback()
        print(f"❌ Ingestion failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    csv_path = os.path.join(DATA_DIR, "external_factors.csv")
    ingest_external_factors(csv_path)