
import os
import sys
import sqlite3
from pathlib import Path

APP_NAME = "PlanBoard"

def resource_path(rel_path: str) -> str:
    # В сборке PyInstaller файлы лежат в _MEIPASS
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel_path)
    # В режиме разработки строим путь от корня проекта (папка, где лежит app/)
    project_root = Path(__file__).resolve().parents[1]
    return str(project_root / rel_path)

def user_data_dir() -> str:
    base = os.getenv("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d

def db_path() -> str:
    return os.path.join(user_data_dir(), "planboard.sqlite3")

def init_db() -> str:
    path = db_path()
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.executescript("""
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
    """)
    con.commit()
    con.close()
    return path
