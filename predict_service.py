import numpy as np
import pandas as pd
import joblib
from datetime import datetime
import os

# Paths to artifacts
ING_MODEL_PATH = "artifacts/ingredients_model.pkl"
META_PATH = "artifacts/model_meta.pkl"

ingredients_model = joblib.load(ING_MODEL_PATH)
meta = joblib.load(META_PATH)
TARGET_COLS = meta.get("target_cols", [])

branch_cust_models = {}

def get_customer_model(branch_id):
    bid = int(branch_id)
    if bid not in branch_cust_models:
        model_path = f"artifacts/customers_model_branch_{bid}.pkl"
        if not os.path.exists(model_path):
            model_path = f"artifacts/customers_model_branch_0.pkl"
        branch_cust_models[bid] = joblib.load(model_path)
    return branch_cust_models[bid]

def get_automated_event(d: datetime, user_remarks: str) -> int:
    if (d.month == 12 and d.day >= 24) or (d.month == 1 and d.day <= 2): return 1
    if d.month == 2 and d.day == 14: return 1
    x = str(user_remarks).lower()
    if "holiday" in x: return 1
    if "fiesta" in x or "event" in x: return 2
    if "promo" in x: return 3
    return 0

def predict_all(date_str, branch_id, cust_lag_1=0, cust_lag_7=0, remarks="Normal"):
    d = pd.to_datetime(date_str, errors="coerce")
    branch_val = int(branch_id)
    cust_model = get_customer_model(branch_val)
    
    # 1. Prepare 7 Features to match the new Colab model
    event_val = get_automated_event(d, remarks)
    dow = d.dayofweek
    is_weekend = 1 if dow >= 5 else 0
    
    # NEW: The list now contains 7 features
    features = [[
        branch_val, d.month, dow, is_weekend, event_val, 
        float(cust_lag_1), float(cust_lag_7)
    ]]
    
    cols = ["Branch_ID", "Month_Num", "DayOfWeek_Num", "Is_Weekend", "Event_Code", "Cust_Lag_1", "Cust_Lag_7"]
    df_cust = pd.DataFrame(features, columns=cols)

    # 2. Predict Customers
    pred_customers = float(cust_model.predict(df_cust)[0])
    pred_customers = max(0.0, round(pred_customers))

    # 3. Predict Ingredients (8 features: Customers + 7 base features)
    df_ing = pd.DataFrame([[pred_customers] + features[0]], columns=["Customers"] + cols)
    
    preds = ingredients_model.predict(df_ing)
    if getattr(preds, "ndim", 1) > 1:
        preds = preds[0]
    preds = np.maximum(0.0, preds)

    # 4. Map to target names
    ingredients = {}
    for i, col_name in enumerate(TARGET_COLS):
        if i < len(preds):
            ingredients[str(col_name)] = float(preds[i])

    return {
        "customers_pred": int(pred_customers),
        "ingredients_pred": ingredients
    }