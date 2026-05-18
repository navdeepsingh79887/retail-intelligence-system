import os
import math
import logging
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func
from app.core.database import SessionLocal
from app.models.inventory import Inventory

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

BOOL_COLUMNS  = ["is_stockout"]
DATE_COLUMNS  = ["expiry_date"]
INT_COLUMNS   = [
    "date_id", "opening_stock", "closing_stock", "units_consumed",
    "safety_stock", "reorder_level", "reorder_point",
    "lead_time_days", "shrinkage_units",
]
FLOAT_COLUMNS = ["unit_cost"]

def ingest_inventory(file_path: str, batch_size: int = 500):
    df = pd.read_csv(file_path, dtype=str)
    log.info(f"Loaded {len(df)} raw rows")

    # Drop metadata rows
    df = df[~df["inventory_id"].str.startswith(("PK:", "Legend:"), na=False)].copy()

    # Drop rows with no PK
    df = df.dropna(subset=["inventory_id"])
    df["inventory_id"] = df["inventory_id"].str.strip()

    # Int columns
    for col in INT_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # Float columns
    for col in FLOAT_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Date columns
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
            df[col] = df[col].where(df[col].notna(), None)

    # Timestamps
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["created_at"] = df["created_at"].where(df["created_at"].notna(), None)
    df["updated_at"] = df["created_at"]  # fallback

    # Boolean
    for col in BOOL_COLUMNS:
        if col in df.columns:
            df[col] = df[col].map(
                lambda v: str(v).strip().lower() in ("true", "1", "yes")
            )

    records = df.to_dict(orient="records")

    # Fix NaN → None
    records = [
        {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.items()}
        for row in records
    ]

    log.info(f"{len(records)} rows ready for ingestion")

    db = SessionLocal()
    try:
        for i in range(0, len(records), batch_size):
            batch = records[i: i + batch_size]
            stmt = insert(Inventory).values(batch).on_conflict_do_update(
                index_elements=["inventory_id"],
                set_={
                    "batch_number":    stmt.excluded.batch_number if False else insert(Inventory).values(batch).excluded.batch_number,
                },
            )
            # Simpler: just use on_conflict_do_nothing since inventory_id is unique PK
            stmt = insert(Inventory).values(batch).on_conflict_do_nothing(
                index_elements=["inventory_id"]
            )
            db.execute(stmt)
            db.commit()
            log.info(f"Inserted rows {i + 1}–{min(i + batch_size, len(records))}")

        log.info("✅ Ingestion complete.")
    except Exception as exc:
        db.rollback()
        log.error(f"❌ Ingestion failed: {exc}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    csv_path = os.path.join(DATA_DIR, "inventory.csv")
    ingest_inventory(csv_path)