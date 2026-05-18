import os
import math
import logging
from decimal import Decimal

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func
from app.core.database import SessionLocal
from app.models.transaction import Transaction  # ✅ fixed import path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

INT_COLUMNS     = ["date_id", "quantity_sold"]
NUMERIC_COLUMNS = ["mrp_per_unit", "unit_selling_price", "discount_amount",
                   "tax_amount", "final_sale_value"]
BOOL_COLUMNS    = ["is_return"]


def ingest_transaction(file_path: str, batch_size: int = 500):
    df = pd.read_csv(file_path, dtype=str)
    log.info(f"Loaded {len(df)} raw rows")

    # Drop metadata/legend rows
    df = df[~df["transaction_id"].str.startswith(("PK:", "Legend:"), na=False)].copy()
    df = df.dropna(subset=["transaction_id"])
    df["transaction_id"] = df["transaction_id"].str.strip()
    log.info(f"{len(df)} data rows after cleanup")

    # Int columns
    for col in INT_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # Numeric/Decimal columns
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: Decimal(str(v)).quantize(Decimal("0.01"))
                if pd.notna(v) and str(v).strip() != ""
                else Decimal("0.00")
            )

    # Boolean columns
    for col in BOOL_COLUMNS:
        if col in df.columns:
            df[col] = df[col].map(
                lambda v: str(v).strip().lower() in ("true", "1", "yes")
            )

    # String columns
    for col in ["transaction_id", "invoice_number", "store_id",
                "product_id", "payment_mode", "transaction_status"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # customer_id — nullable
    df["customer_id"] = df["customer_id"].replace({"": None, "nan": None})
    df["customer_id"] = df["customer_id"].where(df["customer_id"].notna(), None)

    # Timestamps
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["created_at"] = df["created_at"].where(df["created_at"].notna(), None)
    df["updated_at"] = df["created_at"]  # ✅ fallback

    records = df[[
        "transaction_id", "invoice_number", "date_id", "store_id",
        "customer_id", "product_id", "quantity_sold",
        "mrp_per_unit", "unit_selling_price", "discount_amount",
        "tax_amount", "final_sale_value", "payment_mode",
        "transaction_status", "is_return", "created_at", "updated_at"
    ]].to_dict(orient="records")

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

            stmt = insert(Transaction).values(batch).on_conflict_do_update(
                index_elements=["transaction_id"],
                set_={
                    "invoice_number":     insert(Transaction).values(batch).excluded.invoice_number,
                    "date_id":            insert(Transaction).values(batch).excluded.date_id,
                    "store_id":           insert(Transaction).values(batch).excluded.store_id,
                    "customer_id":        insert(Transaction).values(batch).excluded.customer_id,
                    "product_id":         insert(Transaction).values(batch).excluded.product_id,
                    "quantity_sold":      insert(Transaction).values(batch).excluded.quantity_sold,
                    "mrp_per_unit":       insert(Transaction).values(batch).excluded.mrp_per_unit,
                    "unit_selling_price": insert(Transaction).values(batch).excluded.unit_selling_price,
                    "discount_amount":    insert(Transaction).values(batch).excluded.discount_amount,
                    "tax_amount":         insert(Transaction).values(batch).excluded.tax_amount,
                    "final_sale_value":   insert(Transaction).values(batch).excluded.final_sale_value,
                    "payment_mode":       insert(Transaction).values(batch).excluded.payment_mode,
                    "transaction_status": insert(Transaction).values(batch).excluded.transaction_status,
                    "is_return":          insert(Transaction).values(batch).excluded.is_return,
                    "updated_at":         func.now(),
                },
            )
            db.execute(stmt)
            db.commit()
            log.info(f"Upserted rows {i + 1}–{min(i + batch_size, len(records))}")

        log.info("✅ Ingestion complete.")

    except Exception as exc:
        db.rollback()
        log.error(f"❌ Ingestion failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    csv_path = os.path.join(DATA_DIR, "transaction.csv")
    ingest_transaction(csv_path)