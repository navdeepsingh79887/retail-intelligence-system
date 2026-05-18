import os
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from app.core.database import SessionLocal
from app.models.store import Store

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

def ingest_dim_store(file_path: str):
    df = pd.read_csv(file_path, dtype=str)

    # Drop rows where store_id is missing
    df = df[df["store_id"].notna() & (df["store_id"].str.strip() != "")]

    # Clean columns
    df["store_id"]   = df["store_id"].astype(str).str.strip()
    df["store_name"] = df["store_name"].astype(str).str.strip()
    df["store_type"] = df["store_type"].astype(str).str.strip()
    df["city"]       = df["city"].astype(str).str.strip()
    df["state"]      = df["state"].astype(str).str.strip()
    df["region"]     = df["region"].astype(str).str.strip()
    df["zone"]       = df["zone"].astype(str).str.strip()
    df["country"]    = df["country"].astype(str).str.strip()

    # is_active
    df["is_active"] = df["is_active"].map(
        lambda v: True if str(v).strip().upper() in ["TRUE", "1", "YES"] else False
    )

    # Dates
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["created_at"] = df["created_at"].where(df["created_at"].notna(), None)
    df["updated_at"] = df["created_at"]  # fallback to created_at

    # Columns not in CSV
    df["store_code"] = None
    df["address"]    = None
    df["pincode"]    = None

    records = df[[
        "store_id", "store_name", "store_code", "store_type",
        "address", "city", "state", "pincode", "region", "zone",
        "country", "is_active", "created_at", "updated_at"
    ]].to_dict(orient="records")

    # Fix any remaining NaN to None
    for record in records:
        for key, val in record.items():
            if isinstance(val, float) and pd.isna(val):
                record[key] = None

    db = SessionLocal()
    try:
        stmt = insert(Store).values(records).on_conflict_do_nothing(
            index_elements=["store_id"]
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
    csv_path = os.path.join(DATA_DIR, "store.csv")
    ingest_dim_store(csv_path)