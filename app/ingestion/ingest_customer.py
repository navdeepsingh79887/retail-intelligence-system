import os
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from app.core.database import SessionLocal
from app.models.customer import Customer

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

VALID_CUSTOMER_TYPES = {"NEW", "REPEAT", "INACTIVE"}

def ingest_dim_customer(file_path: str):
    df = pd.read_csv(file_path, dtype=str)

    # ✅ Drop legend/footer rows — keep only valid customer_id and customer_type
    df = df[pd.to_numeric(df["customer_id"].str.replace("CUST", "", regex=False), errors="coerce").notna()]
    df = df[df["customer_type"].isin(VALID_CUSTOMER_TYPES)]

    # Clean columns
    df["customer_id"]   = df["customer_id"].astype(str).str.strip()
    df["phone_hash"]    = df["phone_hash"].astype(str).str.strip()
    df["customer_type"] = df["customer_type"].astype(str).str.strip()

    # first_transaction_date — Date only (no time)
    df["first_transaction_date"] = pd.to_datetime(
        df["first_transaction_date"], errors="coerce"
    ).dt.date
    df["first_transaction_date"] = df["first_transaction_date"].where(
        df["first_transaction_date"].notna(), None
    )

    # is_active — safe boolean conversion
    df["is_active"] = df["is_active"].map(
        lambda v: True if str(v).strip().upper() in ["TRUE", "1", "YES"]
                  else (False if str(v).strip().upper() in ["FALSE", "0", "NO"] else None)
    )

    # created_at
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["created_at"] = df["created_at"].where(df["created_at"].notna(), None)

    records = df[[
        "customer_id", "phone_hash", "customer_type",
        "first_transaction_date", "is_active", "created_at"
    ]].to_dict(orient="records")

    # Fix any remaining NaN to None
    for record in records:
        for key, val in record.items():
            if isinstance(val, float) and pd.isna(val):
                record[key] = None

    db = SessionLocal()
    try:
        stmt = insert(Customer).values(records).on_conflict_do_nothing(
            index_elements=["customer_id"]
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
    csv_path = os.path.join(DATA_DIR, "customer.csv")
    ingest_dim_customer(csv_path)