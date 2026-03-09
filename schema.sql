PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS prediction_runs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  start_date    TEXT NOT NULL,
  end_date      TEXT NOT NULL,
  branch_id     INTEGER NOT NULL,
  remarks       TEXT,
  model_version TEXT
);

CREATE TABLE IF NOT EXISTS prediction_days (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id              INTEGER NOT NULL,
  date                TEXT NOT NULL,
  predicted_customers  REAL NOT NULL DEFAULT 0,
  FOREIGN KEY (run_id) REFERENCES prediction_runs(id) ON DELETE CASCADE,
  UNIQUE(run_id, date)
);

CREATE TABLE IF NOT EXISTS prediction_items (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  day_id         INTEGER NOT NULL,
  ingredient     TEXT NOT NULL,
  unit           TEXT NOT NULL,
  predicted_qty  REAL NOT NULL DEFAULT 0,
  FOREIGN KEY (day_id) REFERENCES prediction_days(id) ON DELETE CASCADE,
  UNIQUE(day_id, ingredient)
);

CREATE INDEX IF NOT EXISTS idx_pred_runs_branch_dates
  ON prediction_runs(branch_id, start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_pred_days_date
  ON prediction_days(date);

CREATE INDEX IF NOT EXISTS idx_pred_items_ingredient
  ON prediction_items(ingredient);
