import sqlite3, datetime
from app.db import DB_PATH

class TaskRepo:
    def __init__(self, path=DB_PATH):
        self.path = path

    def _conn(self):
        return sqlite3.connect(self.path)

    def list_tasks(self, order_by="due_date ASC, priority DESC, id DESC"):
        with self._conn() as c:
            cur = c.cursor()
            cur.execute(f"SELECT id, title, description, due_date, created_at, completed, priority FROM tasks ORDER BY {order_by}")
            return cur.fetchall()

    def add_task(self, title, description, due_date, priority=0):
        today = datetime.date.today().isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT INTO tasks(title, description, due_date, created_at, completed, priority) VALUES (?,?,?,?,?,?)",
                (title, description, due_date, today, 0, priority)
            )

    def update_task(self, task_id, title, description, due_date, completed, priority):
        with self._conn() as c:
            c.execute(
                "UPDATE tasks SET title=?, description=?, due_date=?, completed=?, priority=? WHERE id=?",
                (title, description, due_date, int(completed), int(priority), int(task_id))
            )

    def delete_task(self, task_id):
        with self._conn() as c:
            c.execute("DELETE FROM tasks WHERE id=?", (int(task_id),))

    def get_task(self, task_id):
        with self._conn() as c:
            cur = c.cursor()
            cur.execute("SELECT id, title, description, due_date, created_at, completed, priority FROM tasks WHERE id=?", (int(task_id),))
            return cur.fetchone()