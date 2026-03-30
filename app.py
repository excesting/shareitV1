from flask import Flask, request, render_template, jsonify, g, session, redirect, url_for, flash
import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# Import the branch-aware prediction service
from predict_service import predict_all

app = Flask(__name__)

# Railway injects DATABASE_URL automatically. 
# We provide a default fallback for your local testing if you run a local Postgres server.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ims")

# Set a secret key for session encryption (Required for logins)
app.secret_key = 'your_super_secret_key_here'

# ==========================================
# Database Management & Setup
# ==========================================
def init_db():
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                # PostgreSQL uses SERIAL instead of AUTOINCREMENT
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS prediction_runs (
                        id SERIAL PRIMARY KEY,
                        start_date TEXT,
                        end_date TEXT,
                        horizon_days INTEGER,
                        branch_id INTEGER,
                        remarks TEXT
                    );
                    CREATE TABLE IF NOT EXISTS prediction_daily (
                        id SERIAL PRIMARY KEY,
                        run_id INTEGER,
                        date TEXT,
                        customers REAL,
                        FOREIGN KEY(run_id) REFERENCES prediction_runs(id) ON DELETE CASCADE
                    );
                    CREATE TABLE IF NOT EXISTS prediction_daily_items (
                        id SERIAL PRIMARY KEY,
                        daily_id INTEGER,
                        ingredient TEXT,
                        unit TEXT,
                        qty REAL,
                        FOREIGN KEY(daily_id) REFERENCES prediction_daily(id) ON DELETE CASCADE
                    );
                    CREATE TABLE IF NOT EXISTS daily_logs (
                        id SERIAL PRIMARY KEY,
                        date TEXT NOT NULL,
                        branch_id INTEGER NOT NULL,
                        customers REAL NOT NULL DEFAULT 0,
                        remarks TEXT,
                        UNIQUE(date, branch_id)
                    );
                    CREATE TABLE IF NOT EXISTS daily_log_items (
                        id SERIAL PRIMARY KEY,
                        log_id INTEGER NOT NULL,
                        ingredient TEXT NOT NULL,
                        qty REAL NOT NULL DEFAULT 0,
                        waste REAL NOT NULL DEFAULT 0,
                        FOREIGN KEY(log_id) REFERENCES daily_logs(id) ON DELETE CASCADE,
                        UNIQUE(log_id, ingredient)
                    );
                    CREATE TABLE IF NOT EXISTS inventory (
                        id TEXT PRIMARY KEY,
                        branch_id INTEGER NOT NULL DEFAULT 0,
                        name TEXT NOT NULL,
                        unit TEXT NOT NULL,
                        stock REAL NOT NULL DEFAULT 0,
                        min_level REAL NOT NULL DEFAULT 0,
                        max_level REAL NOT NULL DEFAULT 0,
                        reorder_model TEXT NOT NULL DEFAULT 'rop',
                        updated_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL,
                        branch_id INTEGER NOT NULL
                    );
                """)
                
                # Automatically create default accounts if none exist
                cur.execute("SELECT COUNT(*) FROM users")
                if cur.fetchone()[0] == 0:
                    default_users = [
                        # Super Admin (Access to everything, defaults to branch 0)
                        ('admin', generate_password_hash('admin123'), 'admin', 0),
                        # Lipa Manager (Locked to branch 0)
                        ('lipa_mgr', generate_password_hash('lipa123'), 'manager', 0),
                        # Malvar Manager (Locked to branch 1)
                        ('malvar_mgr', generate_password_hash('malvar123'), 'manager', 1)
                    ]
                    # psycopg2 uses %s for variables, not ?
                    cur.executemany(
                        "INSERT INTO users (username, password_hash, role, branch_id) VALUES (%s, %s, %s, %s)", 
                        default_users
                    )
            conn.commit()
    except Exception as e:
        print(f"Database initialization skipped or failed: {e}")

init_db()

def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(DATABASE_URL)
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ==========================================
# Security & RBAC Decorators
# ==========================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_branch():
    """
    Returns the locked branch_id for managers.
    Returns None if Admin is logged in and wants to view ALL branches.
    """
    if session.get('role') == 'admin':
        branch_req = request.args.get('branch_id')
        # If the frontend specifically asks for a branch, return it. Otherwise return None (All).
        if branch_req is not None and branch_req != 'all':
            return int(branch_req)
        return None
    else:
        # Managers are securely locked to their own branch
        return int(session.get('branch_id', 0))

# ==========================================
# Authentication Routes
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            
            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                session['branch_id'] = user['branch_id']
                return redirect(url_for('home'))
            else:
                flash('Invalid username or password. Please try again.')
                
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# Web Page Routes (Protected)
# ==========================================
@app.route('/')
@login_required
def home(): 
    try:
        db = get_db()
        cur = db.cursor()
        branch_id = get_user_branch()
        
        # Admins see everything, Managers see only their branch
        if branch_id is not None:
            cur.execute("SELECT name, stock, min_level, unit, branch_id FROM inventory WHERE branch_id = ? ORDER BY name ASC", (branch_id,))
        else:
            cur.execute("SELECT name, stock, min_level, unit, branch_id FROM inventory ORDER BY branch_id ASC, name ASC")
            
        inventory_data = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        inventory_data = []
        print(f"Error loading dashboard data: {e}")

    return render_template("index.html", inventory=inventory_data, user_role=session.get('role'))

@app.route('/inventory')
@login_required
def inventory(): return render_template('inventory.html')

@app.route('/analytics')
@login_required
def sales_analytics(): return render_template('analytics.html')

@app.route('/daily-log')
@login_required
def daily_log(): return render_template('daily_log.html')

@app.route('/predict')
@login_required
def predict_page(): return render_template('prediction.html')

# ==========================================
# API Routes: Dashboard & Stats (Branch Aware)
# ==========================================
@app.route('/api/dashboard-stats', methods=['GET'])
@login_required
def get_dashboard_stats():
    branch_id = get_user_branch()
    try:
        db = get_db()
        cur = db.cursor()
        
        if branch_id is not None:
            cur.execute("SELECT COUNT(*) as count FROM inventory WHERE branch_id = ?", (branch_id,))
            total_products = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM inventory WHERE stock <= min_level AND stock > 0 AND branch_id = ?", (branch_id,))
            low_stock = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM inventory WHERE stock <= 0 AND branch_id = ?", (branch_id,))
            out_of_stock = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM daily_logs WHERE branch_id = ?", (branch_id,))
            total_logs = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM prediction_runs WHERE branch_id = ?", (branch_id,))
            total_predictions = cur.fetchone()['count']
        else:
            # Admin Global Stats
            cur.execute("SELECT COUNT(*) as count FROM inventory")
            total_products = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM inventory WHERE stock <= min_level AND stock > 0")
            low_stock = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM inventory WHERE stock <= 0")
            out_of_stock = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM daily_logs")
            total_logs = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM prediction_runs")
            total_predictions = cur.fetchone()['count']
        
        return jsonify({
            "success": True,
            "stats": {
                "totalProducts": total_products,
                "lowStockCount": low_stock,
                "outOfStockCount": out_of_stock,
                "totalLogs": total_logs,
                "totalPredictions": total_predictions
            }
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
# ==========================================
# API Routes: Inventory (Branch Aware)
# ==========================================
@app.route('/api/inventory', methods=['GET'])
@login_required
def get_inventory():
    branch_id = get_user_branch()
    try:
        db = get_db()
        cur = db.cursor()
        if branch_id is not None:
            cur.execute("SELECT * FROM inventory WHERE branch_id = ? ORDER BY name ASC", (branch_id,))
        else:
            cur.execute("SELECT * FROM inventory ORDER BY branch_id ASC, name ASC")
            
        items = [dict(row) for row in cur.fetchall()]
        return jsonify({"success": True, "items": items}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/inventory', methods=['POST'])
@login_required
def save_inventory():
    try:
        data = request.get_json()
        db = get_db()
        cur = db.cursor()
        
        # Ensure managers cannot change the branch ID of an item
        item_branch_id = int(data.get('branch_id', session.get('branch_id')))
        if session.get('role') != 'admin' and item_branch_id != session.get('branch_id'):
            return jsonify({"success": False, "error": "Unauthorized branch action"}), 403

        cur.execute("""
            INSERT INTO inventory (id, branch_id, name, unit, stock, min_level, max_level, reorder_model, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, unit=excluded.unit, stock=excluded.stock, 
                min_level=excluded.min_level, max_level=excluded.max_level, 
                reorder_model=excluded.reorder_model, updated_at=excluded.updated_at
        """, (
            data['id'], item_branch_id, data['name'], data['unit'], 
            float(data.get('stock', 0)), float(data.get('min', 0)), 
            float(data.get('max', 0)), data.get('reorder_model', 'rop'), datetime.now().isoformat()
        ))
        db.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/inventory/<item_id>', methods=['DELETE'])
@login_required
def delete_inventory(item_id):
    try:
        # Only admins can delete inventory items completely to prevent data corruption
        if session.get('role') != 'admin':
            return jsonify({"success": False, "error": "Only administrators can delete items."}), 403
            
        db = get_db()
        db.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
        db.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================
# API Routes: Daily Logs (Branch Aware + Smart Deductions w/ Waste)
# ==========================================
@app.route('/api/daily-logs', methods=['GET'])
@login_required
def get_daily_logs():
    branch_id = get_user_branch()
    try:
        db = get_db()
        cur = db.cursor()
        
        if branch_id is not None:
            cur.execute("SELECT id, date, branch_id, customers, remarks FROM daily_logs WHERE branch_id = ? ORDER BY date DESC", (branch_id,))
        else:
            cur.execute("SELECT id, date, branch_id, customers, remarks FROM daily_logs ORDER BY date DESC")
            
        logs = [dict(row) for row in cur.fetchall()]
        for log in logs:
            cur.execute("SELECT ingredient, qty, waste FROM daily_log_items WHERE log_id = ?", (log['id'],))
            db_items = cur.fetchall()
            
            # Separate the consumed qty and the waste qty into two dictionaries
            log['items'] = {row['ingredient']: row['qty'] for row in db_items if row['qty'] > 0}
            log['waste'] = {row['ingredient']: row['waste'] for row in db_items if row['waste'] > 0}
            
        return jsonify({"success": True, "logs": logs}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/daily-logs', methods=['POST'])
@login_required
def save_daily_log():
    try:
        data = request.get_json()
        db = get_db()
        cur = db.cursor()
        
        log_branch_id = int(data.get('branch_id', session.get('branch_id')))
        if session.get('role') != 'admin' and log_branch_id != session.get('branch_id'):
            return jsonify({"success": False, "error": "Unauthorized branch action"}), 403

        # 1. Insert or update the main log entry
        cur.execute("""
            INSERT INTO daily_logs (date, branch_id, customers, remarks) VALUES (?, ?, ?, ?)
            ON CONFLICT(date, branch_id) DO UPDATE SET customers=excluded.customers, remarks=excluded.remarks
        """, (data['date'], log_branch_id, float(data.get('customers', 0)), data.get('remarks', 'Normal')))
        
        cur.execute("SELECT id FROM daily_logs WHERE date=? AND branch_id=?", (data['date'], log_branch_id))
        log_id = cur.fetchone()['id']
        current_time = datetime.now().isoformat()
        
        # 2. Handle Items & Waste (Deducting ONLY 'Consumed' from live inventory)
        items_data = data.get('items', {})
        waste_data = data.get('waste', {})
        all_ingredients = set(items_data.keys()).union(set(waste_data.keys()))

        for ingredient in all_ingredients:
            new_qty = float(items_data.get(ingredient, 0))
            new_waste = float(waste_data.get(ingredient, 0))
            
            cur.execute("SELECT qty, waste FROM daily_log_items WHERE log_id = ? AND ingredient = ?", (log_id, ingredient))
            old_row = cur.fetchone()
            old_qty = old_row['qty'] if old_row else 0.0
            
            # MATH FIX: Only calculate the difference in Consumed (qty) to deduct from inventory
            # We explicitly ignore new_waste for the inventory deduction math!
            qty_difference = new_qty - old_qty
            
            cur.execute("""
                INSERT INTO daily_log_items (log_id, ingredient, qty, waste) VALUES (?, ?, ?, ?)
                ON CONFLICT(log_id, ingredient) DO UPDATE SET qty=excluded.qty, waste=excluded.waste
            """, (log_id, ingredient, new_qty, new_waste))
            
            # Deduct ONLY the consumed amount from the inventory table
            if qty_difference != 0:
                cur.execute("""
                    UPDATE inventory 
                    SET stock = stock - ?, updated_at = ?
                    WHERE name = ? AND branch_id = ?
                """, (qty_difference, current_time, ingredient, log_branch_id))
                
        db.commit()
        return jsonify({"success": True, "log_id": log_id}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/daily-logs/<int:log_id>', methods=['DELETE'])
@login_required
def delete_single_daily_log(log_id):
    try:
        db = get_db()
        cur = db.cursor()
        
        cur.execute("SELECT branch_id FROM daily_logs WHERE id = ?", (log_id,))
        log = cur.fetchone()
        
        if not log: return jsonify({"success": False, "error": "Log not found."}), 404
        if session.get('role') != 'admin' and log['branch_id'] != session.get('branch_id'):
            return jsonify({"success": False, "error": "Unauthorized"}), 403

        # 1. Refund ONLY the consumed qty back to inventory
        cur.execute("SELECT ingredient, qty FROM daily_log_items WHERE log_id = ?", (log_id,))
        items = cur.fetchall()
        
        current_time = datetime.now().isoformat()
        for item in items:
            cur.execute("""
                UPDATE inventory 
                SET stock = stock + ?, updated_at = ?
                WHERE name = ? AND branch_id = ?
            """, (item['qty'], current_time, item['ingredient'], log['branch_id']))

        cur.execute("DELETE FROM daily_log_items WHERE log_id = ?", (log_id,))
        cur.execute("DELETE FROM daily_logs WHERE id = ?", (log_id,))
        
        db.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
#delete all logs (Admin Only)
@app.route('/api/daily-logs/clear', methods=['DELETE'])
@login_required
def clear_all_daily_logs():
    try:
        # Security Check: Only the Admin should be allowed to nuke the entire database
        if session.get('role') != 'admin':
            return jsonify({"success": False, "error": "Unauthorized. Only admins can clear all logs."}), 403

        db = get_db()
        cur = db.cursor()
        
        # Execute the delete command on the whole table
        cur.execute("DELETE FROM daily_logs")
        db.commit()
        
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
#==========================================
# Delete the Prediction Runs (Admin Only)
#==========================================

@app.route('/api/prediction-history/<int:id>', methods=['DELETE'])
@login_required
def delete_prediction_history(id):
    try:
        db = get_db()
        cur = db.cursor()
        
        # Security: Ensure branch managers only delete their own forecasts
        if session.get('role') != 'admin':
            cur.execute("SELECT branch_id FROM prediction_runs WHERE id = ?", (id,))
            run = cur.fetchone()
            if run and run['branch_id'] != session.get('branch_id'):
                return jsonify({"success": False, "error": "Unauthorized"}), 403

        # PRAGMA foreign_keys = ON will automatically delete the daily items (Cascade)
        cur.execute("DELETE FROM prediction_runs WHERE id = ?", (id,))
        db.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/prediction-history/clear', methods=['DELETE'])
@login_required
def clear_prediction_history():
    try:
        db = get_db()
        cur = db.cursor()
        
        if session.get('role') != 'admin':
            # Managers can only clear their own branch's history
            branch_id = session.get('branch_id')
            cur.execute("DELETE FROM prediction_runs WHERE branch_id = ?", (branch_id,))
        else:
            # Admins clear everything
            cur.execute("DELETE FROM prediction_runs")
            
        db.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
# ==========================================
# API Routes: REPORTS ENGINE
# ==========================================
@app.route('/reports')
@login_required
def reports_page():
    return render_template('reports.html')

@app.route('/api/reports/generate', methods=['POST'])
@login_required
def generate_report():
    data = request.json
    rep_type = data.get('type')
    requested_branch_id = data.get('branch_id')
    
    # --- SECURITY OVERRIDE ---
    user_role = session.get('role')
    user_branch_id = session.get('branch_id')
    
    if user_role != 'admin':
        branch_id = str(user_branch_id)
    else:
        branch_id = str(requested_branch_id)
    # -------------------------

    db = get_db()
    db.row_factory = sqlite3.Row 
    cur = db.cursor()
    params = []
    
    try:
        # REPORT 1: Inventory Status Report
        if rep_type == "inventory_status":
            branch_filter = ""
            if branch_id != "all":
                branch_filter = "WHERE branch_id = ?"
                params.append(int(branch_id))
                
            cur.execute(f"SELECT branch_id, name, unit, stock, min_level, max_level FROM inventory {branch_filter} ORDER BY name", tuple(params))
            rows = cur.fetchall()
            columns = ["Branch", "Item Name", "Unit", "Current Stock", "Min Level", "Max Level", "Status"]
            
            report_data = []
            for r in rows:
                status = "OK"
                if r['stock'] <= 0: status = "Out of Stock"
                elif r['stock'] <= r['min_level']: status = "Low Stock"
                
                b_name = "Malvar" if r['branch_id'] == 1 else "Lipa"
                report_data.append([b_name, r['name'], r['unit'], round(r['stock'], 2), r['min_level'], r['max_level'], status])
            
            return jsonify({"success": True, "title": "Inventory Status Report", "columns": columns, "data": report_data})

        # REPORT 2: Inventory Consumption Report
        elif rep_type == "inventory_consumption":
            branch_filter = ""
            if branch_id != "all":
                branch_filter = "AND dl.branch_id = ?"
                params.append(int(branch_id))

            # Fetch date, branch, customers, ingredients, and consumed qty (ignoring 0 consumption)
            query = f"""
                SELECT dl.date, dl.branch_id, dl.customers, dli.ingredient, dli.qty, i.unit
                FROM daily_logs dl
                JOIN daily_log_items dli ON dl.id = dli.log_id
                LEFT JOIN inventory i ON dli.ingredient = i.name AND dl.branch_id = i.branch_id
                WHERE dli.qty > 0 {branch_filter}
                ORDER BY dl.date DESC, dli.ingredient ASC
            """
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            columns = ["Date", "Branch", "Daily Customers", "Ingredient", "Consumed Qty", "Unit"]

            report_data = []
            for r in rows:
                b_name = "Malvar" if r['branch_id'] == 1 else "Lipa"
                report_data.append([r['date'], b_name, round(r['customers']), r['ingredient'], round(r['qty'], 2), r['unit'] or ""])

            return jsonify({"success": True, "title": "Inventory Consumption Report", "columns": columns, "data": report_data})

        # REPORT 3: Inventory Waste Report
        elif rep_type == "inventory_waste":
            branch_filter = ""
            if branch_id != "all":
                branch_filter = "AND dl.branch_id = ?"
                params.append(int(branch_id))

            # Fetch date, branch, ingredients, and waste qty (ignoring 0 waste)
            query = f"""
                SELECT dl.date, dl.branch_id, dli.ingredient, dli.waste, i.unit
                FROM daily_logs dl
                JOIN daily_log_items dli ON dl.id = dli.log_id
                LEFT JOIN inventory i ON dli.ingredient = i.name AND dl.branch_id = i.branch_id
                WHERE dli.waste > 0 {branch_filter}
                ORDER BY dl.date DESC, dli.ingredient ASC
            """
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            columns = ["Date", "Branch", "Ingredient", "Waste Qty", "Unit"]

            report_data = []
            for r in rows:
                b_name = "Malvar" if r['branch_id'] == 1 else "Lipa"
                report_data.append([r['date'], b_name, r['ingredient'], round(r['waste'], 2), r['unit'] or ""])

            return jsonify({"success": True, "title": "Inventory Waste Report", "columns": columns, "data": report_data})

        else:
            return jsonify({"success": False, "error": "Invalid report type selected."}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
# ==========================================
# API Routes: Prediction & Forecasting (Branch Aware)
# ==========================================
def save_prediction_to_db(result, start_date, end_date, branch_id, remarks):
    db = get_db()
    daily = result.get("daily", [])
    cur = db.cursor()
    cur.execute("""
        INSERT INTO prediction_runs (start_date, end_date, horizon_days, branch_id, remarks) 
        VALUES (?, ?, ?, ?, ?)
    """, (start_date, end_date, len(daily), int(branch_id), remarks))
    run_id = cur.lastrowid
    for day in daily:
        cur.execute("INSERT INTO prediction_daily (run_id, date, customers) VALUES (?, ?, ?)", 
                    (run_id, day["date"], float(day.get("customers", 0))))
        daily_id = cur.lastrowid
        for ingredient, qty in day.get("ingredients", {}).items():
            unit = "L" if "juice" in ingredient.lower() else "kg"
            cur.execute("INSERT INTO prediction_daily_items (daily_id, ingredient, unit, qty) VALUES (?, ?, ?, ?)", 
                        (daily_id, ingredient, unit, float(qty or 0)))
    db.commit()
    return run_id

@app.route('/api/predict-range', methods=['POST'])
@login_required
def api_predict_range():
    data = request.get_json(silent=True) or {}
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    remarks = data.get("remarks", "Normal")
    
    # Force branch ID based on the logged-in user
    if session.get('role') == 'admin':
        branch_id = int(data.get("branch_id", session.get('branch_id', 0)))
    else:
        branch_id = int(session.get('branch_id', 0))
    
    if not start_date or not end_date:
        return jsonify({"success": False, "error": "Missing inputs"}), 400
        
    try:
        db = get_db()
        cur = db.cursor()
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        total_customers, total_ingredients, daily = 0, {}, []
        last_day_customers = 0 
        cur_date = sd
        
        while cur_date <= ed:
            date_str = cur_date.strftime("%Y-%m-%d")
            
            yesterday = (cur_date - timedelta(days=1)).strftime("%Y-%m-%d")
            last_week = (cur_date - timedelta(days=7)).strftime("%Y-%m-%d")
            
            def get_hist(target_date):
                row = db.execute("SELECT customers FROM daily_logs WHERE date=? AND branch_id=?", 
                                (target_date, branch_id)).fetchone()
                return float(row['customers']) if row else 0

            lag1 = last_day_customers if last_day_customers > 0 else get_hist(yesterday)
            lag7 = get_hist(last_week)

            out = predict_all(date_str=date_str, branch_id=branch_id, cust_lag_1=lag1, cust_lag_7=lag7, remarks=remarks)
            
            cust = out.get("customers_pred", 0)
            ing = out.get("ingredients_pred", {})
            
            last_day_customers = cust
            total_customers += cust
            for k, v in ing.items():
                total_ingredients[k] = total_ingredients.get(k, 0.0) + float(v)
                
            daily.append({"date": date_str, "customers": cust, "ingredients": ing})
            cur_date += timedelta(days=1)
            
        res = {
            "success": True, 
            "range": {"start_date": start_date, "end_date": end_date, "days": (ed - sd).days + 1}, 
            "totals": {"customers": total_customers, "ingredients": total_ingredients}, 
            "daily": daily
        }
        
        res["prediction_id"] = save_prediction_to_db(res, start_date, end_date, branch_id, remarks)
        return jsonify(res), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/latest-prediction', methods=['GET'])
@login_required
def get_latest_prediction():
    branch_id = get_user_branch()
    if branch_id is None:
        branch_id = 0 # Default to 0 if an admin searches generically
        
    try:
        db = get_db()
        cur = db.cursor()
        
        cur.execute("""
            SELECT id, start_date, end_date FROM prediction_runs 
            WHERE branch_id = ? ORDER BY id DESC LIMIT 1
        """, (branch_id,))
        run = cur.fetchone()
        
        if not run:
            return jsonify({"success": False, "error": "No predictions found"}), 404
            
        run_id = run['id']
        cur.execute("SELECT id, date, customers FROM prediction_daily WHERE run_id = ?", (run_id,))
        days = cur.fetchall()
        
        daily_data = []
        for day in days:
            daily_id = day['id']
            cur.execute("SELECT ingredient, qty FROM prediction_daily_items WHERE daily_id = ?", (daily_id,))
            items = cur.fetchall()
            
            ingredients = {item['ingredient']: item['qty'] for item in items}
            daily_data.append({
                "date": day['date'],
                "customers": day['customers'],
                "ingredients": ingredients
            })
            
        return jsonify({
            "success": True,
            "start_date": run['start_date'],
            "end_date": run['end_date'],
            "daily": daily_data
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/prediction-history', methods=['GET'])
@login_required
def get_prediction_history():
    branch_id = get_user_branch()
    try:
        db = get_db()
        cur = db.cursor()
        
        if branch_id is not None:
            cur.execute("""
                SELECT r.id, r.start_date, r.end_date, r.branch_id, r.remarks, COALESCE(SUM(d.customers), 0) as total_customers
                FROM prediction_runs r LEFT JOIN prediction_daily d ON r.id = d.run_id 
                WHERE r.branch_id = ?
                GROUP BY r.id ORDER BY r.id DESC LIMIT 50
            """, (branch_id,))
        else:
            cur.execute("""
                SELECT r.id, r.start_date, r.end_date, r.branch_id, r.remarks, COALESCE(SUM(d.customers), 0) as total_customers
                FROM prediction_runs r LEFT JOIN prediction_daily d ON r.id = d.run_id 
                GROUP BY r.id ORDER BY r.id DESC LIMIT 50
            """)
            
        runs = [dict(row) for row in cur.fetchall()]
        for run in runs:
            cur.execute("""
                SELECT pdi.ingredient, pdi.unit, SUM(pdi.qty) as total_qty FROM prediction_daily_items pdi
                JOIN prediction_daily pd ON pdi.daily_id = pd.id 
                WHERE pd.run_id = ? GROUP BY pdi.ingredient, pdi.unit ORDER BY total_qty DESC LIMIT 3
            """, (run['id'],))
            items = cur.fetchall()
            run['top_items'] = ", ".join([f"{i['ingredient']}: {i['total_qty']:.1f}{i['unit']}" for i in items]) if items else "-"
        return jsonify({"success": True, "history": runs}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
