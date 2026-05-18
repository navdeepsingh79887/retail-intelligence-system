import os
import math
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from app.core.database import SessionLocal
from app.models.product import Product

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

def safe_date(val, fmt):
    try:
        return pd.to_datetime(val, format=fmt, errors="coerce").date()
    except:
        return None

def safe_decimal(val):
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
        return float(val)
    except:
        return None

def safe_int(val):
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
        return int(val)
    except:
        return None

def ingest_dim_product(file_path: str):
    df = pd.read_csv(file_path, dtype=str)

    # Drop legend/footer rows
    df = df[df["product_id"].notna() & (df["product_id"].str.strip() != "")]

    # String columns
    df["product_id"]    = df["product_id"].astype(str).str.strip()
    df["sku_code"]      = df["sku_code"].astype(str).str.strip()
    df["product_name"]  = df["product_name"].astype(str).str.strip()
    df["pack_size_unit"]= df["pack_size_unit"].astype(str).str.strip()
    df["supplier_id"]   = df["supplier_id"].astype(str).str.strip()

    # ✅ barcode — float like 6948020e+12 → strip decimal → string
    df["barcode"] = df["barcode"].apply(
        lambda v: str(int(float(v))) if pd.notna(v) and v not in ["", "nan"] else None
    )

    # FK integer columns
    df["category_id"] = df["category_id"].apply(safe_int)
    df["brand_id"]    = df["brand_id"].apply(safe_int)

    # Numeric columns
    for col in ["pack_size_value", "mrp", "cost_price", "selling_price", "tax_rate_pct"]:
        df[col] = df[col].apply(safe_decimal)

    # ✅ Dates — format DD-MM-YYYY
    df["manufacturing_date"] = df["manufacturing_date"].apply(
        lambda v: safe_date(v, "%d-%m-%Y") if pd.notna(v) else None
    )
    df["expiry_date"] = df["expiry_date"].apply(
        lambda v: safe_date(v, "%d-%m-%Y") if pd.notna(v) else None
    )

    # ✅ Timestamps — format DD-MM-YYYY HH:MM
    df["created_at"] = pd.to_datetime(df["created_at"], format="%d-%m-%Y %H:%M", errors="coerce")
    df["created_at"] = df["created_at"].where(df["created_at"].notna(), None)
    df["updated_at"] = pd.to_datetime(df["updated_at"], format="%d-%m-%Y %H:%M", errors="coerce")
    df["updated_at"] = df["updated_at"].where(df["updated_at"].notna(), None)

    # is_active
    df["is_active"] = df["is_active"].map(
        lambda v: True if str(v).strip().upper() in ["TRUE", "1", "YES"] else False
    )

    records = df[[
        "product_id", "sku_code", "barcode", "product_name",
        "category_id", "brand_id", "supplier_id",
        "pack_size_value", "pack_size_unit",
        "mrp", "cost_price", "selling_price", "tax_rate_pct",
        "manufacturing_date", "expiry_date",
        "is_active", "created_at", "updated_at"
    ]].to_dict(orient="records")

    # Fix any remaining NaN to None
    for record in records:
        for key, val in record.items():
            if isinstance(val, float) and math.isnan(val):
                record[key] = None

    db = SessionLocal()
    try:
        # Batch insert in chunks of 500 for performance
        chunk_size = 500
        total = 0
        for i in range(0, len(records), chunk_size):
            chunk = records[i:i + chunk_size]
            stmt = insert(Product).values(chunk).on_conflict_do_nothing(
                index_elements=["product_id"]
            )
            db.execute(stmt)
            total += len(chunk)
            print(f"  Inserted {total}/{len(records)} records...")

        db.commit()
        print(f"✅ Ingestion complete. {len(records)} records processed.")

    except Exception as e:
        db.rollback()
        print(f"❌ Ingestion failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    csv_path = os.path.join(DATA_DIR, "product.csv")
    ingest_dim_product(csv_path)