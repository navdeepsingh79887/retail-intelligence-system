import argparse
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from app.core.database import SessionLocal, engine
from app.models.date import DimDate, Base

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

COLUMN_MAP = {
    "date_id":       "date_id",
    "full_date":     "full_date",
    "day":           "day",
    "day_name":      "day_name",
    "month_number":  "month_number",
    "month_name":    "month_name",
    "quarter":       "quarter",
    "year":          "year",
    "week_number":   "week_number",
    "is_weekend":    "is_weekend",
    "is_month_start":"is_month_start",
    "is_month_end":  "is_month_end",
    "season":        "season",
}

FLOAT_AS_INT_COLUMNS = ["month_number", "quarter", "year", "week_number"]
BOOL_COLUMNS         = ["is_weekend", "is_month_start", "is_month_end"]


def load_csv(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype=str)
    log.info(f"Loaded {len(df)} raw rows from {csv_path}")

    df = df.rename(columns=COLUMN_MAP)

    valid_cols = list(COLUMN_MAP.values())
    df = df[[c for c in valid_cols if c in df.columns]]

    df["date_id"] = pd.to_numeric(df["date_id"], errors="coerce").astype("Int64")
    df["day"] = pd.to_numeric(df["day"], errors="coerce").astype("Int64")

    for col in FLOAT_AS_INT_COLUMNS:
        if col in df.columns:
            df[col] = (
                pd.to_numeric(df[col], errors="coerce")
                .astype("float")
                .round()
                .astype("Int64")
            )

    # 🔥 FIX: full_date handling
    df["full_date"] = pd.to_datetime(df["full_date"], errors="coerce").dt.date

    before = len(df)
    df = df.dropna(subset=["full_date"])   # ❗ REMOVE BAD ROWS
    after = len(df)

    log.info(f"Dropped {before - after} rows with invalid full_date")

    for col in BOOL_COLUMNS:
        if col in df.columns:
            df[col] = df[col].map(
                lambda v: str(v).strip().lower() in ("true", "1", "yes")
            )

    if "season" in df.columns:
        df["season"] = df["season"].str.strip()

    for col in ("day_name", "month_name"):
        if col in df.columns:
            df[col] = df[col].str.strip()

    df = df.dropna(subset=["date_id"])

    for col in ["date_id", "day"] + FLOAT_AS_INT_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(lambda v: int(v) if pd.notna(v) else None)

    log.info(f"{len(df)} rows ready for ingestion")
    return df


def ingest(csv_path: str, batch_size: int = 500) -> None:
    Base.metadata.create_all(bind=engine)

    df = load_csv(csv_path)
    records = df.to_dict(orient="records")

    records = [
        {k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in row.items()}
        for row in records
    ]

    db = SessionLocal()
    try:
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]

            stmt = insert(DimDate).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["full_date"],
                set_={
                    "day":            stmt.excluded.day,
                    "day_name":       stmt.excluded.day_name,
                    "month_number":   stmt.excluded.month_number,
                    "month_name":     stmt.excluded.month_name,
                    "quarter":        stmt.excluded.quarter,
                    "year":           stmt.excluded.year,
                    "week_number":    stmt.excluded.week_number,
                    "is_weekend":     stmt.excluded.is_weekend,
                    "is_month_start": stmt.excluded.is_month_start,
                    "is_month_end":   stmt.excluded.is_month_end,
                    "season":         stmt.excluded.season,
                },
            )

            db.execute(stmt)
            db.commit()
            log.info(f"Upserted rows {i + 1}–{min(i + batch_size, len(records))}")

        log.info("✅ date ingestion complete.")

    except Exception as exc:
        db.rollback()
        log.error(f"Ingestion failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest date CSV")
    parser.add_argument("--csv", required=True, help="Path to CSV file")
    parser.add_argument("--batch-size", type=int, default=500, help="Rows per DB batch")
    args = parser.parse_args()

    if not Path(args.csv).exists():
        raise FileNotFoundError(f"CSV not found: {args.csv}")

    ingest(args.csv, batch_size=args.batch_size)