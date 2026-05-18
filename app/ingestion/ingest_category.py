import os
import math
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from app.core.database import SessionLocal
from app.models.category import Category

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

PARENT_ROWS = [
    {"category_id": 32, "category_name": "Grocery & Staples",  "parent_category_id": None, "is_active": True, "created_at": pd.Timestamp("2026-02-27"), "updated_at": pd.Timestamp("2026-02-27")},
    {"category_id": 33, "category_name": "Snacks & Beverages", "parent_category_id": None, "is_active": True, "created_at": pd.Timestamp("2026-02-27"), "updated_at": pd.Timestamp("2026-02-27")},
    {"category_id": 34, "category_name": "Dairy & Beverages",  "parent_category_id": None, "is_active": True, "created_at": pd.Timestamp("2026-02-27"), "updated_at": pd.Timestamp("2026-02-27")},
    {"category_id": 35, "category_name": "Home & Cleaning",    "parent_category_id": None, "is_active": True, "created_at": pd.Timestamp("2026-02-27"), "updated_at": pd.Timestamp("2026-02-27")},
    {"category_id": 36, "category_name": "Personal Care",      "parent_category_id": None, "is_active": True, "created_at": pd.Timestamp("2026-02-27"), "updated_at": pd.Timestamp("2026-02-27")},
    {"category_id": 37, "category_name": "Religious & Others", "parent_category_id": None, "is_active": True, "created_at": pd.Timestamp("2026-02-27"), "updated_at": pd.Timestamp("2026-02-27")},
]

def ingest_dim_category(file_path: str):
    df = pd.read_excel(file_path) if file_path.endswith(".xlsx") else pd.read_csv(file_path)

    df.columns = [c.lower() for c in df.columns]
    df = df[pd.to_numeric(df["category_id"], errors="coerce").notna()]

    df["category_id"]   = df["category_id"].astype(int)
    df["category_name"] = df["category_name"].astype(str).str.strip()
    df["is_active"]     = df["is_active"].map(
        lambda v: True if str(v).strip().upper() in ["TRUE", "1", "YES"] else False
    )
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["updated_at"] = pd.to_datetime(df["updated_at"], errors="coerce")

    # Use pandas Int64 (nullable integer) before to_dict
    df["parent_category_id"] = pd.to_numeric(
        df["parent_category_id"], errors="coerce"
    ).astype("Int64")  # ✅ capital I — pandas nullable integer, preserves None

    child_records = df.to_dict(orient="records")

    # ✅ Fix AFTER to_dict — convert pandas NA/float back to Python None or int
    for record in child_records:
        pid = record.get("parent_category_id")
        if pid is None or (isinstance(pid, float) and math.isnan(pid)):
            record["parent_category_id"] = None
        elif hasattr(pid, 'item'):  # numpy/pandas integer type
            record["parent_category_id"] = int(pid)
        else:
            record["parent_category_id"] = int(pid) if pid is not None else None

    db = SessionLocal()
    try:
        print("Inserting parent categories...")
        db.execute(
            insert(Category).values(PARENT_ROWS).on_conflict_do_nothing(
                index_elements=["category_id"]
            )
        )
        db.flush()

        print("Inserting child categories...")
        db.execute(
            insert(Category).values(child_records).on_conflict_do_nothing(
                index_elements=["category_id"]
            )
        )
        db.commit()
        print(f"✅ Ingestion complete. {len(PARENT_ROWS)} parents + {len(child_records)} children = {len(PARENT_ROWS) + len(child_records)} total records.")

    except Exception as e:
        db.rollback()
        print(f"❌ Ingestion failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    for fname in ["category.xlsx", "category.csv"]:
        path = os.path.join(DATA_DIR, fname)
        if os.path.exists(path):
            ingest_dim_category(path)
            break
    else:
        print("❌ No category file found in data/ folder")