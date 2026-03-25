import numpy as np
import pandas as pd
import joblib
from datetime import datetime
import os
import re  # <-- ADDED REGEX LIBRARY HERE

# Paths to artifacts
ING_MODEL_PATH = "artifacts/ingredients_model.pkl"
META_PATH = "artifacts/model_meta.pkl"

ingredients_model = joblib.load(ING_MODEL_PATH)
meta = joblib.load(META_PATH)
TARGET_COLS = meta.get("target_cols", [])

# The exact 11 features your Colab script trained on
BASE_FEATURES = [
    "Branch_ID", "Is_Weekend", "Event_Code", "Cust_Lag_1", "Cust_Lag_7",
    "Day_Sin", "Day_Cos", "Month_Sin", "Month_Cos", "Cust_Roll_3", "Cust_Roll_7"
]

branch_cust_models = {}

def get_customer_model(branch_id):
    bid = int(branch_id)
    if bid not in branch_cust_models:
        model_path = f"artifacts/customers_model_branch_{bid}.pkl"
        if not os.path.exists(model_path):
            model_path = f"artifacts/customers_model_branch_0.pkl"
        branch_cust_models[bid] = joblib.load(model_path)
    return branch_cust_models[bid]

def encode_event(remarks: str) -> int:
    x = str(remarks).lower()
    if any(word in x for word in ["holiday", "christmas", "new year"]): return 1
    if any(word in x for word in ["fiesta", "event"]): return 2
    if "promo" in x: return 3
    return 0

def predict_all(date_str, branch_id, cust_lag_1=0, cust_lag_7=0, remarks="Normal"):
    d = pd.to_datetime(date_str, errors="coerce")
    branch_val = int(branch_id)
    cust_model = get_customer_model(branch_val)
    
    # --- 1. FEATURE ENGINEERING (Matching Colab Exactly) ---
    event_val = encode_event(remarks)
    
    day_of_week = d.dayofweek
    month_num = d.month
    is_weekend = 1 if day_of_week >= 5 else 0
    
    # A. Cyclical Features (Trigonometry for repeating time patterns)
    day_sin = np.sin(2 * np.pi * day_of_week / 7)
    day_cos = np.cos(2 * np.pi * day_of_week / 7)
    month_sin = np.sin(2 * np.pi * (month_num - 1) / 12)
    month_cos = np.cos(2 * np.pi * (month_num - 1) / 12)
    
    # B. Lags and Rolling Averages
    c_lag_1 = float(cust_lag_1)
    c_lag_7 = float(cust_lag_7)
    
    # Safe approximation for rolling averages so we don't have to rewrite app.py
    cust_roll_3 = c_lag_1  
    cust_roll_7 = (c_lag_1 + c_lag_7) / 2.0 if (c_lag_1 > 0 and c_lag_7 > 0) else c_lag_1

    # C. Build the exact 11-item array the model is begging for
    features = [[
        branch_val, 
        is_weekend, 
        event_val, 
        c_lag_1, 
        c_lag_7,
        day_sin, 
        day_cos, 
        month_sin, 
        month_cos, 
        cust_roll_3, 
        cust_roll_7
    ]]
    
    # --- 2. PREDICT CUSTOMERS ---
    df_cust = pd.DataFrame(features, columns=BASE_FEATURES)
    pred_customers = float(cust_model.predict(df_cust)[0])
    pred_customers = max(0.0, round(pred_customers))

    # --- 3. PREDICT INGREDIENTS (Customers + 11 base features) ---
    ing_cols = ["Customers"] + BASE_FEATURES
    df_ing = pd.DataFrame([[pred_customers] + features[0]], columns=ing_cols)
    
    preds = ingredients_model.predict(df_ing)
    if getattr(preds, "ndim", 1) > 1:
        preds = preds[0]
    preds = np.maximum(0.0, preds)

# --- 4. MAP TO TARGET NAMES ---
    ingredients = {}
    for i, col_name in enumerate(TARGET_COLS):
        if i < len(preds):
            clean_name = str(col_name)
            
            # 1. First, fix the tricky Excel formatting (e.g. "Rice (uncooked, kg)" -> "Rice (uncooked)")
            clean_name = clean_name.replace(", kg)", ")").replace(", L)", ")").replace(", mL)", ")")
            
            # 2. Then, strip off any normal trailing units (e.g. "Pork (kg)" -> "Pork")
            clean_name = re.sub(r'\s*\((kg|L|mL|pcs)\)$', '', clean_name, flags=re.IGNORECASE)
            
            # 3. Clean up any extra spaces
            clean_name = clean_name.strip()
            
            ingredients[clean_name] = float(preds[i])

    return {
        "customers_pred": int(pred_customers),
        "ingredients_pred": ingredients
    }
