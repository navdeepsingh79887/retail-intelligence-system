import joblib
import json
import os
from pathlib import Path
from datetime import datetime

# Absolute path — works correctly inside Docker
MODEL_DIR  = Path(__file__).parent.parent.parent / "models"
MODEL_PATH = MODEL_DIR / "demand_forecast_model.pkl"
META_PATH  = MODEL_DIR / "model_metadata.json"


def ensure_model_dir():
    MODEL_DIR.mkdir(exist_ok=True)


def save_model(model, metadata: dict = None):
    ensure_model_dir()
    joblib.dump(model, MODEL_PATH)
    print(f"✅ Model saved to {MODEL_PATH}")
    if metadata:
        metadata["saved_at"] = datetime.now().isoformat()
        with open(META_PATH, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"✅ Metadata saved to {META_PATH}")


def load_model():
    if not MODEL_PATH.exists():
        return None
    return joblib.load(MODEL_PATH)


def model_exists() -> bool:
    return MODEL_PATH.exists()


def get_model_metadata() -> dict:
    if not META_PATH.exists():
        return {"status": "no model trained yet"}
    with open(META_PATH) as f:
        return json.load(f)