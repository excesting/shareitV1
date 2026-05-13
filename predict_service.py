import numpy as np
import pandas as pd
import joblib
from datetime import datetime
import os
import re  

# Path to metadata
META_PATH = "artifacts/model_meta.pkl"

try:
    meta = joblib.load(META_PATH)
    # Pulling branch-specific targets established in V4
    LIPA_TARGETS = meta.get("lipa_targets", [])
    MALVAR_TARGETS = meta.get("malvar_targets", [])
except Exception as e:
    print(f"Warning: Could not load metadata. Error: {e}")
    LIPA_TARGETS, MALVAR_TARGETS = [], []

# The exact 12 base features your V4 Colab script trained on
BASE_FEATURES = [
    "Branch_ID", "Is_Weekend", "Is_Payday", "Event_Code", "Cust_Lag_1", "Cust_Lag_7",
    "Day_Sin", "Day_Cos", "Month_Sin", "Month_Cos", "Cust_Roll_3", "Cust_Roll_7"
]

# Caching dictionaries so models stay in RAM for fast predictions
branch_cust_models = {}
branch_ing_models = {}

def get_models(branch_id):
    """Dynamically loads the correct Customer AND Ingredient model based on branch."""
    bid = int(branch_id)
    
    # Load Customer Model
    if bid not in branch_cust_models:
        c_path = f"artifacts/customers_model_branch_{bid}.pkl"
        if not os.path.exists(c_path): 
            c_path = "artifacts/customers_model_branch_0.pkl" # Fallback
        branch_cust_models[bid] = joblib.load(c_path)
        
    # Load Ingredient Model
    if bid not in branch_ing_models:
        i_path = f"artifacts/ingredients_model_branch_{bid}.pkl"
        if not os.path.exists(i_path): 
            i_path = "artifacts/ingredients_model_branch_0.pkl" # Fallback
        branch_ing_models[bid] = joblib.load(i_path)
        
    return branch_cust_models[bid], branch_ing_models[bid]

def encode_event(remarks: str) -> int:
    x = str(remarks).lower()
    if any(word in x for word in ["holiday", "christmas", "new year"]): return 1
    if any(word in x for word in ["fiesta", "event"]): return 2
    if "promo" in x: return 3
    return 0

def predict_all(date_str, branch_id, cust_lag_1=0, cust_lag_7=0, remarks="Normal"):
    d = pd.to_datetime(date_str, errors="coerce")
    branch_val = int(branch_id)
    
    # Fetch the specific brains for this specific branch
    cust_model, ing_model = get_models(branch_val)
    
    # Target list depends on which branch we are predicting for
    current_targets = MALVAR_TARGETS if branch_val == 1 else LIPA_TARGETS
    
    # --- 1. FEATURE ENGINEERING ---
    event_val = encode_event(remarks)
    
    day_of_week = d.dayofweek
    month_num = d.month
    is_weekend = 1 if day_of_week >= 5 else 0
    is_payday = 1 if d.day in [14, 15, 29, 30, 31] else 0
    
    day_sin = np.sin(2 * np.pi * day_of_week / 7)
    day_cos = np.cos(2 * np.pi * day_of_week / 7)
    month_sin = np.sin(2 * np.pi * (month_num - 1) / 12)
    month_cos = np.cos(2 * np.pi * (month_num - 1) / 12)
    
    c_lag_1 = float(cust_lag_1)
    c_lag_7 = float(cust_lag_7)
    
    cust_roll_3 = c_lag_1  
    cust_roll_7 = (c_lag_1 + c_lag_7) / 2.0 if (c_lag_1 > 0 and c_lag_7 > 0) else c_lag_1

    # 2D Array for Scikit-Learn (Silences the warnings)
    base_features_array = [[
        branch_val, is_weekend, is_payday, event_val, 
        c_lag_1, c_lag_7, day_sin, day_cos, 
        month_sin, month_cos, cust_roll_3, cust_roll_7
    ]]
    
    # --- 2. PREDICT CUSTOMERS ---
    pred_customers = float(cust_model.predict(base_features_array)[0])
    pred_customers = max(0.0, round(pred_customers))

    # --- 3. PREDICT INGREDIENTS ---
    # The predicted customer count acts as the OOF feature for the ingredient model
    ing_features_array = [[pred_customers] + base_features_array[0]]
    
    preds = ing_model.predict(ing_features_array)
    if getattr(preds, "ndim", 1) > 1:
        preds = preds[0]
    preds = np.maximum(0.0, preds)

    # --- 4. MAP TO TARGET NAMES ---
    ingredients = {}
    for i, col_name in enumerate(current_targets):
        if i < len(preds):
            clean_name = str(col_name)
            clean_name = clean_name.replace(", kg)", ")").replace(", L)", ")").replace(", mL)", ")")
            clean_name = re.sub(r'\s*\((kg|L|mL|pcs)\)$', '', clean_name, flags=re.IGNORECASE)
            clean_name = clean_name.strip()
            
            ingredients[clean_name] = float(preds[i])

    return {
        "customers_pred": int(pred_customers),
        "ingredients_pred": ingredients
    }
