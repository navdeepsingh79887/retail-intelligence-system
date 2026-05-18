import os
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from app.core.database import SessionLocal
from app.models.supplier import Supplier

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

def ingest_dim_supplier(file_path: str):
    df = pd.read_csv(file_path, dtype=str)

    df = df[df["supplier_id"].notna() & (df["supplier_id"].str.strip() != "")]

    df["supplier_id"]   = df["supplier_id"].astype(str).str.strip()
    df["supplier_name"] = df["supplier_name"].astype(str).str.strip()
    df["contact_phone"] = df["contact_phone"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)

    # ✅ Fix city/state swap using temp variables
    temp_city  = df["city"].astype(str).str.strip()   # actually = states (Odisha etc)
    temp_state = df["state"].astype(str).str.strip()  # actually = cities (Bhubaneswar etc)
    df["city"]  = temp_state  # ✅ cities go into city column
    df["state"] = temp_city   # ✅ states go into state column

    df["lead_time_days"] = pd.to_numeric(df["lead_time_days"], errors="coerce").apply(
        lambda x: int(x) if pd.notna(x) else None
    )

    df["is_active"] = df["is_active"].map(
        lambda v: True if str(v).strip().upper() in ["TRUE", "1", "YES"] else False
    )

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["created_at"] = df["created_at"].where(df["created_at"].notna(), None)

    # ✅ updated_at not in CSV — use created_at value as fallback
    df["updated_at"]    = df["created_at"]
    df["contact_email"] = None

    records = df[[
        "supplier_id", "supplier_name", "contact_phone", "contact_email",
        "city", "state", "lead_time_days", "is_active", "created_at", "updated_at"
    ]].to_dict(orient="records")

    for record in records:
        for key, val in record.items():
            if isinstance(val, float) and pd.isna(val):
                record[key] = None

    db = SessionLocal()
    try:
        stmt = insert(Supplier).values(records).on_conflict_do_nothing(
            index_elements=["supplier_id"]
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
    csv_path = os.path.join(DATA_DIR, "supplier.csv")
    ingest_dim_supplier(csv_path)