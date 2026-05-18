import pandas as pd
import numpy as np
from datetime import date, timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from app.forecasting.feature_engineering import build_feature_table, get_feature_columns
from app.forecasting import model_loader


async def train_model(db: AsyncSession) -> Dict[str, Any]:
    print("🔄 Building feature table...")
    df = await build_feature_table(db)

    if df.empty or len(df) < 50:
        return {"error": "Not enough data to train. Need at least 50 rows."}

    FEATURES = get_feature_columns()
    TARGET   = "quantity_sold"

    df_clean = df.dropna(subset=FEATURES + [TARGET]).copy()

    if len(df_clean) < 30:
        return {"error": "Too many NaN rows after cleaning. Check your data."}

    df_clean = df_clean.sort_values("full_date")
    cutoff   = df_clean["full_date"].max() - pd.Timedelta(days=14)

    train_df = df_clean[df_clean["full_date"] <= cutoff]
    test_df  = df_clean[df_clean["full_date"] >  cutoff]

    X_train, y_train = train_df[FEATURES], train_df[TARGET]
    X_test,  y_test  = test_df[FEATURES],  test_df[TARGET]

    print(f"📊 Training rows: {len(train_df)} | Test rows: {len(test_df)}")

    model = RandomForestRegressor(
        n_estimators=100, max_depth=10,
        min_samples_leaf=3, random_state=42, n_jobs=-1,
    )
    model.fit(X_train, y_train)
    print("✅ Model trained!")

    y_pred = np.maximum(model.predict(X_test), 0)

    mae  = round(float(mean_absolute_error(y_test, y_pred)), 3)
    rmse = round(float(np.sqrt(mean_squared_error(y_test, y_pred))), 3)
    mape = round(float(np.mean(np.abs((y_test - y_pred) / np.maximum(y_test, 1))) * 100), 2)

    importance = dict(sorted(
        zip(FEATURES, [round(float(x), 4) for x in model.feature_importances_]),
        key=lambda x: x[1], reverse=True
    ))

    metadata = {
        "mae": mae, "rmse": rmse, "mape_pct": mape,
        "mean_actual_qty": round(float(y_test.mean()), 3),
        "train_rows": len(train_df), "test_rows": len(test_df),
        "features_used": FEATURES, "feature_importance": importance,
        "model_type": "RandomForestRegressor",
    }

    model_loader.save_model(model, metadata)
    print(f"📈 MAE: {mae}  RMSE: {rmse}  MAPE: {mape}%")
    return {"status": "success", "metrics": metadata}


async def predict_demand(
    db: AsyncSession, product_id: str, store_id: str, days_ahead: int = 7
) -> Dict[str, Any]:

    if not model_loader.model_exists():
        return {"error": "No trained model found. Call POST /api/forecast/train first."}

    model    = model_loader.load_model()
    FEATURES = get_feature_columns()

    df = await build_feature_table(db)
    product_history = df[
        (df["product_id"] == product_id) & (df["store_id"] == store_id)
    ].sort_values("full_date")

    if product_history.empty:
        return {"error": f"No history found for {product_id} at {store_id}"}

    last_row = product_history.iloc[-1]

    season_map = {12:1,1:1,2:1, 3:2,4:2,5:2, 6:3,7:3,8:3,9:3, 10:4,11:4}
    predictions = []
    today = date.today()

    for i in range(1, days_ahead + 1):
        pred_date   = today + timedelta(days=i)
        day_of_week = pred_date.weekday() + 1
        is_weekend  = 1 if day_of_week >= 6 else 0

        features = {
            "day_of_week":        day_of_week,
            "is_weekend":         is_weekend,
            "season_code":        season_map.get(pred_date.month, 1),
            "month_number":       pred_date.month,
            "is_festival":        0,
            "is_public_holiday":  0,
            "is_marriage_season": 0,
            "temperature_c":      float(last_row.get("temperature_c", 25)),
            "rainfall_mm":        0.0,
            "lag_7d_qty":         float(last_row.get("lag_7d_qty", 0)),
            "lag_14d_qty":        float(last_row.get("lag_14d_qty", 0)),
            "lag_30d_qty":        float(last_row.get("lag_30d_qty", 0)),
            "rolling_7d_avg":     float(last_row.get("rolling_7d_avg", 0)),
            "rolling_30d_avg":    float(last_row.get("rolling_30d_avg", 0)),
        }

        pred_qty = max(0, round(float(model.predict(pd.DataFrame([features])[FEATURES])[0]), 1))
        predictions.append({
            "date": pred_date.isoformat(),
            "day_name": pred_date.strftime("%A"),
            "predicted_qty": pred_qty,
            "is_weekend": bool(is_weekend),
        })

    return {
        "product_id":          product_id,
        "store_id":            store_id,
        "product_name":        str(last_row.get("product_name", "")),
        "category":            str(last_row.get("category_name", "")),
        "days_ahead":          days_ahead,
        "total_predicted_qty": sum(p["predicted_qty"] for p in predictions),
        "daily_forecast":      predictions,
    }


async def get_top_demand_forecast(
    db: AsyncSession, store_id: str, top_n: int = 10
) -> List[Dict]:

    if not model_loader.model_exists():
        return [{"error": "No model trained yet."}]

    df = await build_feature_table(db)
    store_df = df[df["store_id"] == store_id]

    if store_df.empty:
        return [{"error": f"No data found for store {store_id}"}]

    top_products = (
        store_df.groupby("product_id")["quantity_sold"]
        .sum().nlargest(top_n).index.tolist()
    )

    results = []
    for pid in top_products:
        forecast = await predict_demand(db, pid, store_id, days_ahead=7)
        if "error" not in forecast:
            results.append({
                "product_id":        pid,
                "product_name":      forecast["product_name"],
                "category":          forecast["category"],
                "total_7d_forecast": forecast["total_predicted_qty"],
            })

    return sorted(results, key=lambda x: x["total_7d_forecast"], reverse=True)