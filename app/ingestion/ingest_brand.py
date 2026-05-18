import os
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from app.core.database import SessionLocal
from app.models.brand import Brand

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

def ingest_dim_brand(csv_path: str):
    df = pd.read_csv(csv_path, dtype=str)

    # Drop non-numeric brand_id rows
    df = df[pd.to_numeric(df["brand_id"], errors="coerce").notna()]

    # Clean columns
    df["brand_id"]      = df["brand_id"].astype(int)
    df["brand_name"]    = df["brand_name"].astype(str).str.strip()
    df["brand_country"] = df["brand_country"].astype(str).str.strip()

    # Convert TRUE/FALSE string to boolean
    df["is_active"] = df["is_active"].map(
        lambda v: True if str(v).strip().upper() == "TRUE"
                  else (False if str(v).strip().upper() == "FALSE" else None)
    )

    # CSV date format is YYYY-MM-DD
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["created_at"] = df["created_at"].where(df["created_at"].notna(), None)

    records = df.to_dict(orient="records")

    db = SessionLocal()
    try:
        stmt = insert(Brand).values(records).on_conflict_do_nothing(
            index_elements=["brand_id"]
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
    csv_path = os.path.join(DATA_DIR, "brand.csv")
    ingest_dim_brand(csv_path)