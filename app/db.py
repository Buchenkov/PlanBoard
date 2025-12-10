# инициализация Б/Д

import sqlite3
from app.paths import db_path  # хранение БД в %APPDATA%\PlanBoard

DDL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    due_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed);
"""

def init_db():
    path = db_path()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(DDL)  # выполняем весь DDL разом
        conn.commit()
    finally:
        conn.close()

