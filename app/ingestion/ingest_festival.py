import os
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from app.core.database import SessionLocal
from app.models.festival import Festival, FestivalProduct

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

def parse_date(val):
    try:
        return pd.to_datetime(val, errors="coerce").date() if pd.notna(val) else None
    except:
        return None

def ingest_dim_festival(file_path: str):
    df = pd.read_csv(file_path, dtype=str)

    # Drop legend/footer rows
    df = df[df["festival_id"].astype(str).str.match(r"^FES\d+$")]

    # --- Clean festival records ---
    df["festival_id"]                    = df["festival_id"].str.strip()
    df["event_id"]                       = df["event_id"].str.strip()
    df["event_name"]                     = df["event_name"].str.strip()
    df["festival_name"]                  = df["festival_name"].str.strip()
    df["religion_id"]                    = pd.to_numeric(df["religion_id"], errors="coerce")
    df["religion"]                       = df["religion"].str.strip()
    df["state"]                          = df["state"].str.strip()
    df["region"]                         = df["region"].str.strip()
    df["festival_start_date"]            = df["festival_start_date"].apply(parse_date)
    df["festival_end_date"]              = df["festival_end_date"].apply(parse_date)
    df["festival_period_days"]           = pd.to_numeric(df["festival_period_days"], errors="coerce")
    df["demand_level"]                   = df["demand_level"].str.strip()
    df["demand_category"]                = df["demand_category"].str.strip()
    df["expected_demand_multiplier"]     = pd.to_numeric(df["expected_demand_multiplier"], errors="coerce")
    df["created_at"]                     = pd.to_datetime(df["created_at"], errors="coerce")
    df["created_at"]                     = df["created_at"].where(df["created_at"].notna(), None)
    df["updated_at"]                     = pd.to_datetime(df["updated_at"], errors="coerce")
    df["updated_at"]                     = df["updated_at"].where(df["updated_at"].notna(), None)

    # Boolean columns
    df["is_national_holiday"] = df["is_national_holiday"].map(
        lambda v: True if str(v).strip().upper() in ["TRUE", "1", "YES"] else False
    )
    df["historically_consistent_uplift"] = df["historically_consistent_uplift"].map(
        lambda v: True if str(v).strip().upper() in ["TRUE", "1", "YES"] else False
    )

    festival_cols = [
        "festival_id", "event_id", "event_name", "festival_name",
        "religion_id", "religion", "state", "region",
        "festival_start_date", "festival_end_date", "festival_period_days",
        "is_national_holiday", "historically_consistent_uplift",
        "demand_level", "demand_category", "expected_demand_multiplier",
        "created_at", "updated_at"
    ]
    festival_records = df[festival_cols].to_dict(orient="records")

    # Fix NaN to None
    for record in festival_records:
        for key, val in record.items():
            if isinstance(val, float) and pd.isna(val):
                record[key] = None

    # --- Build junction table records from top_product_ids / top_product_names ---
    junction_records = []
    for _, row in df.iterrows():
        fid        = row["festival_id"]
        prod_ids   = [x.strip() for x in str(row["top_product_ids"]).split(",") if x.strip()]
        prod_names = [x.strip() for x in str(row["top_product_names"]).split(",") if x.strip()]

        # Zip them together with rank
        for rank, (pid, pname) in enumerate(zip(prod_ids, prod_names), start=1):
            junction_records.append({
                "festival_id":  fid,
                "product_id":   pid if pid else None,
                "product_name": pname if pname else None,
                "rank":         rank
            })

    db = SessionLocal()
    try:
        # Step 1 — Insert festivals
        print(f"Inserting {len(festival_records)} festival records...")
        db.execute(
            insert(Festival).values(festival_records).on_conflict_do_nothing(
                index_elements=["festival_id"]
            )
        )
        db.flush()

        # Step 2 — Insert junction table
        print(f"Inserting {len(junction_records)} festival_product records...")
        if junction_records:
            db.execute(
                insert(FestivalProduct).values(junction_records).on_conflict_do_nothing()
            )

        db.commit()
        print(f"✅ Ingestion complete. {len(festival_records)} festivals + {len(junction_records)} product links.")

    except Exception as e:
        db.rollback()
        print(f"❌ Ingestion failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    csv_path = os.path.join(DATA_DIR, "festival.csv")
    ingest_dim_festival(csv_path)