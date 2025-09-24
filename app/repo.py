# # Работа с базой данных


import sqlite3
from contextlib import contextmanager
from app.paths import db_path

class TaskRepo:
    def __init__(self, path=None):
        self.path = str(path or db_path())
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")

    def close(self):
        if getattr(self, "conn", None):
            self.conn.close()
            self.conn = None

    @contextmanager
    def transaction(self):
        cur = self.conn.cursor()
        try:
            yield cur
        except Exception:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()
        finally:
            cur.close()

    def list_tasks(self, order_by="due_date ASC, priority DESC, id DESC"):
        allowed_cols = {"id", "title", "description", "due_date", "created_at", "completed", "priority"}
        clauses = []
        for part in (order_by or "").split(","):
            part = part.strip()
            if not part:
                continue
            bits = part.split()
            col = bits[0]
            direction = bits[1].upper() if len(bits) > 1 else "ASC"
            if col in allowed_cols and direction in ("ASC", "DESC"):
                clauses.append(f"{col} {direction}")
        if not clauses:
            clauses = ["due_date ASC", "priority DESC", "id DESC"]

        sql = f"""
            SELECT id, title, description, due_date, created_at, completed, priority
            FROM tasks
            ORDER BY {", ".join(clauses)}
        """
        cur = self.conn.cursor()
        try:
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()

    def add_task(self, title, description, due_date, priority=0):
        sql = """
            INSERT INTO tasks(title, description, due_date, created_at, completed, priority)
            VALUES (?, ?, ?, DATE('now'), 0, ?)
        """
        with self.transaction() as cur:
            cur.execute(sql, (title, description, due_date, int(priority)))
            return cur.lastrowid

    def update_task(self, task_id, title=None, description=None, due_date=None, completed=None, priority=None):
        parts, params = [], []
        if title is not None:
            parts.append("title = ?"); params.append(title)
        if description is not None:
            parts.app ("description = ?"); params.append(description)
        if due_date is not None:
            parts.append("due_date = ?"); params.append(due_date)
        if completed is not None:
            parts.append("completed = ?"); params.append(1 if completed else 0)
        if priority is not None:
            parts.append("priority = ?"); params.append(int(priority))

        if not parts:
            return False

        params.append(int(task_id))
        sql = f"UPDATE tasks SET {', '.join(parts)} WHERE id = ?"
        with self.transaction() as cur:
            cur.execute(sql, params)
            return cur.rowcount > 0

    def delete_task(self, task_id):
        with self.transaction() as cur:
            cur.execute("DELETE FROM tasks WHERE id = ?", (int(task_id),))
            return cur.rowcount > 0

    def get_task(self, task_id):
        cur = self.conn.cursor()
        try:
            cur.execute("""
                SELECT id, title, description, due_date, created_at, completed, priority
                FROM tasks
                WHERE id = ?
            """, (int(task_id),))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            cur.close()

# import sqlite3
# from contextlib import contextmanager
# from app.db import DB_PATH

# class TaskRepo:
#     def __init__(self, path=DB_PATH):
#         self.path = str(path)
#         self.conn = sqlite3.connect(self.path)
#         self.conn.row_factory = sqlite3.Row
#         self.conn.execute("PRAGMA foreign_keys = ON")
#         self.conn.execute("PRAGMA journal_mode = WAL")
#         self.conn.execute("PRAGMA synchronous = NORMAL")

#     def close(self):
#         if getattr(self, "conn", None):
#             self.conn.close()
#             self.conn = None

#     @contextmanager
#     def transaction(self):
#         cur = self.conn.cursor()
#         try:
#             yield cur
#         except Exception:
#             self.conn.rollback()
#             raise
#         else:
#             self.conn.commit()
#         finally:
#             cur.close()

#     def list_tasks(self, order_by="due_date ASC, priority DESC, id DESC"):
#         allowed_cols = {"id", "title", "description", "due_date", "created_at", "completed", "priority"}
#         clauses = []
#         for part in (order_by or "").split(","):
#             part = part.strip()
#             if not part:
#                 continue
#             bits = part.split()
#             col = bits[0]
#             direction = bits[1].upper() if len(bits) > 1 else "ASC"
#             if col in allowed_cols and direction in ("ASC", "DESC"):
#                 clauses.append(f"{col} {direction}")
#         if not clauses:
#             clauses = ["due_date ASC", "priority DESC", "id DESC"]

#         sql = f"""
#             SELECT id, title, description, due_date, created_at, completed, priority
#             FROM tasks
#             ORDER BY {", ".join(clauses)}
#         """
#         cur = self.conn.cursor()
#         try:
#             cur.execute(sql)
#             return [dict(r) for r in cur.fetchall()]
#         finally:
#             cur.close()

#     def add_task(self, title, description, due_date, priority=0):
#         sql = """
#             INSERT INTO tasks(title, description, due_date, created_at, completed, priority)
#             VALUES (?, ?, ?, DATE('now'), 0, ?)
#         """
#         with self.transaction() as cur:
#             cur.execute(sql, (title, description, due_date, int(priority)))
#             return cur.lastrowid

#     def update_task(self, task_id, title=None, description=None, due_date=None, completed=None, priority=None):
#         parts, params = [], []
#         if title is not None:
#             parts.append("title = ?"); params.append(title)
#         if description is not None:
#             parts.append("description = ?"); params.append(description)
#         if due_date is not None:
#             parts.append("due_date = ?"); params.append(due_date)
#         if completed is not None:
#             parts.append("completed = ?"); params.append(1 if completed else 0)
#         if priority is not None:
#             parts.append("priority = ?"); params.append(int(priority))

#         if not parts:
#             return False

#         params.append(int(task_id))
#         sql = f"UPDATE tasks SET {', '.join(parts)} WHERE id = ?"
#         with self.transaction() as cur:
#             cur.execute(sql, params)
#             return cur.rowcount > 0

#     def delete_task(self, task_id):
#         with self.transaction() as cur:
#             cur.execute("DELETE FROM tasks WHERE id = ?", (int(task_id),))
#             return cur.rowcount > 0

#     def get_task(self, task_id):
#         cur = self.conn.cursor()
#         try:
#             cur.execute("""
#                 SELECT id, title, description, due_date, created_at, completed, priority
#                 FROM tasks
#                 WHERE id = ?
#             """, (int(task_id),))
#             row = cur.fetchone()
#             return dict(row) if row else None
#         finally:
#             cur.close()