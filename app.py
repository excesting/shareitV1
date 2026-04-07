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

# Railway / Hosted Postgres URL
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ims")

# Set a secret key for session encryption (Required for logins)
app.secret_key = 'your_super_secret_key_here'

# ==========================================
# Database Management & Setup
# ==========================================
def init_db():
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
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
                cursor.execute("SELECT COUNT(*) FROM users")
                if cursor.fetchone()[0] == 0:
                    default_users = [
                        ('admin', generate_password_hash('admin123'), 'admin', 0),
                        ('lipa_mgr', generate_password_hash('lipa123'), 'manager', 0),
                        ('malvar_mgr', generate_password_hash('malvar123'), 'manager', 1)
                    ]
                    cursor.executemany(
                        "INSERT INTO users (username, password_hash, role, branch_id) VALUES (%s, %s, %s, %s)", 
                        default_users
                    )
            conn.commit()
    except Exception as e:
        print(f"DB Init error: {e}")

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
    if session.get('role') == 'admin':
        branch_req = request.args.get('branch_id')
        if branch_req is not None and branch_req != 'all':
            return int(branch_req)
        return None
    else:
        return int(session.get('branch_id', 0))

# ==========================================
# Authentication Routes
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE username = %s", (username,))
                user = cur.fetchone()
                
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
        cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        branch_id = get_user_branch()
        
        if branch_id is not None:
            cur.execute("SELECT name, stock, min_level, unit, branch_id FROM inventory WHERE branch_id = %s ORDER BY name ASC", (branch_id,))
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
        cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if branch_id is not None:
            cur.execute("SELECT COUNT(*) as count FROM inventory WHERE branch_id = %s", (branch_id,))
            total_products = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM inventory WHERE stock <= min_level AND stock > 0 AND branch_id = %s", (branch_id,))
            low_stock = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM inventory WHERE stock <= 0 AND branch_id = %s", (branch_id,))
            out_of_stock = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM daily_logs WHERE branch_id = %s", (branch_id,))
            total_logs = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM prediction_runs WHERE branch_id = %s", (branch_id,))
            total_predictions = cur.fetchone()['count']
        else:
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
        cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if branch_id is not None:
            cur.execute("SELECT * FROM inventory WHERE branch_id = %s ORDER BY name ASC", (branch_id,))
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
        
        item_branch_id = int(data.get('branch_id', session.get('branch_id')))
        if session.get('role') != 'admin' and item_branch_id != session.get('branch_id'):
            return jsonify({"success": False, "error": "Unauthorized branch action"}), 403

        cur.execute("""
            INSERT INTO inventory (id, branch_id, name, unit, stock, min_level, max_level, reorder_model, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        if session.get('role') != 'admin':
            return jsonify({"success": False, "error": "Only administrators can delete items."}), 403
            
        db = get_db()
        cur = db.cursor()
        cur.execute("DELETE FROM inventory WHERE id = %s", (item_id,))
        db.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================
# API Routes: Daily Logs
# ==========================================
@app.route('/api/daily-logs', methods=['GET'])
@login_required
def get_daily_logs():
    branch_id = get_user_branch()
    try:
        db = get_db()
        cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if branch_id is not None:
            cur.execute("SELECT id, date, branch_id, customers, remarks FROM daily_logs WHERE branch_id = %s ORDER BY date DESC", (branch_id,))
        else:
            cur.execute("SELECT id, date, branch_id, customers, remarks FROM daily_logs ORDER BY date DESC")
            
        logs = [dict(row) for row in cur.fetchall()]
        for log in logs:
            cur.execute("SELECT ingredient, qty, waste FROM daily_log_items WHERE log_id = %s", (log['id'],))
            db_items = cur.fetchall()
            
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
        cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        log_branch_id = int(data.get('branch_id', session.get('branch_id')))
        if session.get('role') != 'admin' and log_branch_id != session.get('branch_id'):
            return jsonify({"success": False, "error": "Unauthorized branch action"}), 403

        cur.execute("""
            INSERT INTO daily_logs (date, branch_id, customers, remarks) VALUES (%s, %s, %s, %s)
            ON CONFLICT(date, branch_id) DO UPDATE SET customers=excluded.customers, remarks=excluded.remarks
            RETURNING id
        """, (data['date'], log_branch_id, float(data.get('customers', 0)), data.get('remarks', 'Normal')))
        
        log_id = cur.fetchone()['id']
        current_time = datetime.now().isoformat()
        
        items_data = data.get('items', {})
        waste_data = data.get('waste', {})
        all_ingredients = set(items_data.keys()).union(set(waste_data.keys()))

        for ingredient in all_ingredients:
            new_qty = float(items_data.get(ingredient, 0))
            new_waste = float(waste_data.get(ingredient, 0))
            
            cur.execute("SELECT qty, waste FROM daily_log_items WHERE log_id = %s AND ingredient = %s", (log_id, ingredient))
            old_row = cur.fetchone()
            old_qty = old_row['qty'] if old_row else 0.0
            
            qty_difference = new_qty - old_qty
            
            cur.execute("""
                INSERT INTO daily_log_items (log_id, ingredient, qty, waste) VALUES (%s, %s, %s, %s)
                ON CONFLICT(log_id, ingredient) DO UPDATE SET qty=excluded.qty, waste=excluded.waste
            """, (log_id, ingredient, new_qty, new_waste))
            
            if qty_difference != 0:
                cur.execute("""
                    UPDATE inventory 
                    SET stock = stock - %s, updated_at = %s
                    WHERE name = %s AND branch_id = %s
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
        cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cur.execute("SELECT branch_id FROM daily_logs WHERE id = %s", (log_id,))
        log = cur.fetchone()
        
        if not log: return jsonify({"success": False, "error": "Log not found."}), 404
        if session.get('role') != 'admin' and log['branch_id'] != session.get('branch_id'):
            return jsonify({"success": False, "error": "Unauthorized"}), 403

        cur.execute("SELECT ingredient, qty FROM daily_log_items WHERE log_id = %s", (log_id,))
        items = cur.fetchall()
        
        current_time = datetime.now().isoformat()
        for item in items:
            cur.execute("""
                UPDATE inventory 
                SET stock = stock + %s, updated_at = %s
                WHERE name = %s AND branch_id = %s
            """, (item['qty'], current_time, item['ingredient'], log['branch_id']))

        cur.execute("DELETE FROM daily_log_items WHERE log_id = %s", (log_id,))
        cur.execute("DELETE FROM daily_logs WHERE id = %s", (log_id,))
        
        db.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
@app.route('/api/daily-logs/clear', methods=['DELETE'])
@login_required
def clear_all_daily_logs():
    try:
        if session.get('role') != 'admin':
            return jsonify({"success": False, "error": "Unauthorized. Only admins can clear all logs."}), 403

        db = get_db()
        cur = db.cursor()
        cur.execute("DELETE FROM daily_logs")
        db.commit()
        
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

#==========================================
# PREDICTIONS DELETE API
#==========================================
@app.route('/api/prediction-history/<int:id>', methods=['DELETE'])
@login_required
def delete_prediction_history(id):
    try:
        db = get_db()
        cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if session.get('role') != 'admin':
            cur.execute("SELECT branch_id FROM prediction_runs WHERE id = %s", (id,))
            run = cur.fetchone()
            if run and run['branch_id'] != session.get('branch_id'):
                return jsonify({"success": False, "error": "Unauthorized"}), 403

        cur.execute("DELETE FROM prediction_runs WHERE id = %s", (id,))
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
            branch_id = session.get('branch_id')
            cur.execute("DELETE FROM prediction_runs WHERE branch_id = %s", (branch_id,))
        else:
            cur.execute("DELETE FROM prediction_runs")
            
        db.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

#==========================================
# SETTINGS & USERS
#==========================================
@app.route('/settings')
@login_required
def settings_page():
    if session.get('role') != 'admin':
        flash("Only administrators can access the settings page.")
        return redirect(url_for('home'))
    
    try:
        db = get_db()
        cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT id, username, role, branch_id FROM users ORDER BY id ASC")
        users = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        users = []
        print(f"Error loading users: {e}")

    return render_template('settings.html', users=users)

@app.route('/api/users/reset-password', methods=['POST'])
@login_required
def api_reset_password():
    if session.get('role') != 'admin':
        return jsonify({"success": False, "error": "Unauthorized"}), 403
        
    data = request.get_json()
    user_id = data.get('user_id')
    new_password = data.get('new_password')
    
    if not user_id or not new_password:
        return jsonify({"success": False, "error": "Missing data"}), 400
        
    try:
        hashed_pw = generate_password_hash(new_password)
        db = get_db()
        cur = db.cursor()
        cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hashed_pw, user_id))
        db.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        db.rollback()
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
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    user_role = session.get('role')
    user_branch_id = session.get('branch_id')
    
    if user_role != 'admin':
        branch_id = str(user_branch_id)
    else:
        branch_id = str(requested_branch_id)

    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    params = []
    
    try:
        if rep_type == "inventory_status":
            branch_filter = ""
            if branch_id != "all":
                branch_filter = "WHERE branch_id = %s"
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
            
            return jsonify({"success": True, "title": "Current Inventory Status Report", "columns": columns, "data": report_data})

        elif rep_type == "inventory_consumption":
            branch_filter = ""
            if branch_id != "all":
                branch_filter = "AND dl.branch_id = %s"
                params.append(int(branch_id))

            date_filter = ""
            if start_date and end_date:
                date_filter = "AND dl.date >= %s AND dl.date <= %s"
                params.extend([start_date, end_date])

            query = f"""
                SELECT dl.date, dl.branch_id, dl.customers, dli.ingredient, dli.qty, i.unit
                FROM daily_logs dl
                JOIN daily_log_items dli ON dl.id = dli.log_id
                LEFT JOIN inventory i ON dli.ingredient = i.name AND dl.branch_id = i.branch_id
                WHERE dli.qty > 0 {branch_filter} {date_filter}
                ORDER BY dl.date DESC, dli.ingredient ASC
            """
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            columns = ["Date", "Branch", "Daily Customers", "Ingredient", "Consumed Qty", "Unit"]

            report_data = []
            for r in rows:
                b_name = "Malvar" if r['branch_id'] == 1 else "Lipa"
                report_data.append([r['date'], b_name, round(r['customers']), r['ingredient'], round(r['qty'], 2), r['unit'] or ""])

            return jsonify({"success": True, "title": f"Consumption Report ({start_date} to {end_date})", "columns": columns, "data": report_data})

        elif rep_type == "inventory_waste":
            branch_filter = ""
            if branch_id != "all":
                branch_filter = "AND dl.branch_id = %s"
                params.append(int(branch_id))

            date_filter = ""
            if start_date and end_date:
                date_filter = "AND dl.date >= %s AND dl.date <= %s"
                params.extend([start_date, end_date])

            query = f"""
                SELECT dl.date, dl.branch_id, dli.ingredient, dli.waste, i.unit
                FROM daily_logs dl
                JOIN daily_log_items dli ON dl.id = dli.log_id
                LEFT JOIN inventory i ON dli.ingredient = i.name AND dl.branch_id = i.branch_id
                WHERE dli.waste > 0 {branch_filter} {date_filter}
                ORDER BY dl.date DESC, dli.ingredient ASC
            """
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            columns = ["Date", "Branch", "Ingredient", "Waste Qty", "Unit"]

            report_data = []
            for r in rows:
                b_name = "Malvar" if r['branch_id'] == 1 else "Lipa"
                report_data.append([r['date'], b_name, r['ingredient'], round(r['waste'], 2), r['unit'] or ""])

            return jsonify({"success": True, "title": f"Waste Report ({start_date} to {end_date})", "columns": columns, "data": report_data})

        else:
            return jsonify({"success": False, "error": "Invalid report type selected."}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
# ==========================================
# API Routes: Prediction & Forecasting
# ==========================================
def save_prediction_to_db(result, start_date, end_date, branch_id, remarks):
    db = get_db()
    daily = result.get("daily", [])
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute("""
        INSERT INTO prediction_runs (start_date, end_date, horizon_days, branch_id, remarks) 
        VALUES (%s, %s, %s, %s, %s) RETURNING id
    """, (start_date, end_date, len(daily), int(branch_id), remarks))
    run_id = cur.fetchone()['id']
    
    for day in daily:
        cur.execute("""
            INSERT INTO prediction_daily (run_id, date, customers) 
            VALUES (%s, %s, %s) RETURNING id
        """, (run_id, day["date"], float(day.get("customers", 0))))
        daily_id = cur.fetchone()['id']
        
        for ingredient, qty in day.get("ingredients", {}).items():
            unit = "L" if "juice" in ingredient.lower() else "kg"
            cur.execute("""
                INSERT INTO prediction_daily_items (daily_id, ingredient, unit, qty) 
                VALUES (%s, %s, %s, %s)
            """, (daily_id, ingredient, unit, float(qty or 0)))
    db.commit()
    return run_id

@app.route('/api/predict-range', methods=['POST'])
@login_required
def api_predict_range():
    data = request.get_json(silent=True) or {}
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    remarks = data.get("remarks", "Normal")
    
    if session.get('role') == 'admin':
        branch_id = int(data.get("branch_id", session.get('branch_id', 0)))
    else:
        branch_id = int(session.get('branch_id', 0))
    
    if not start_date or not end_date:
        return jsonify({"success": False, "error": "Missing inputs"}), 400
        
    try:
        db = get_db()
        cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
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
                cur.execute("SELECT customers FROM daily_logs WHERE date=%s AND branch_id=%s", (target_date, branch_id))
                row = cur.fetchone()
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
        branch_id = 0
        
    try:
        db = get_db()
        cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cur.execute("""
            SELECT id, start_date, end_date FROM prediction_runs 
            WHERE branch_id = %s ORDER BY id DESC LIMIT 1
        """, (branch_id,))
        run = cur.fetchone()
        
        if not run:
            return jsonify({"success": False, "error": "No predictions found"}), 404
            
        run_id = run['id']
        cur.execute("SELECT id, date, customers FROM prediction_daily WHERE run_id = %s", (run_id,))
        days = cur.fetchall()
        
        daily_data = []
        for day in days:
            daily_id = day['id']
            cur.execute("SELECT ingredient, qty FROM prediction_daily_items WHERE daily_id = %s", (daily_id,))
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
        cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if branch_id is not None:
            cur.execute("""
                SELECT r.id, r.start_date, r.end_date, r.branch_id, r.remarks, COALESCE(SUM(d.customers), 0) as total_customers
                FROM prediction_runs r LEFT JOIN prediction_daily d ON r.id = d.run_id 
                WHERE r.branch_id = %s
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
                WHERE pd.run_id = %s GROUP BY pdi.ingredient, pdi.unit ORDER BY total_qty DESC LIMIT 3
            """, (run['id'],))
            items = cur.fetchall()
            run['top_items'] = ", ".join([f"{i['ingredient']}: {i['total_qty']:.1f}{i['unit']}" for i in items]) if items else "-"
        return jsonify({"success": True, "history": runs}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
