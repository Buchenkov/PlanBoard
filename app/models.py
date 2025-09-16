# Модель таблицы + раскраска строк.

from PyQt5 import QtWidgets, QtCore, QtGui
import datetime

class TaskTableModel(QtCore.QAbstractTableModel):
    headers = ["Название", "Срок", "Статус", "Приоритет", "ID"]

    def init(self, repo):
        super().init()
        self.repo = repo
        self.rows = []
        self.order_by = "due_date ASC, priority DESC, id DESC"
        self.load()

    def load(self):
        self.beginResetModel()
        self.rows = self.repo.list_tasks(self.order_by)
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self.rows)

    def columnCount(self, parent=None):
        return len(self.headers)

    def data(self, index, role):
        if not index.isValid():
            return None
        r = self.rows[index.row()]
        task_id, title, desc, due, created, completed, priority = r
        col = index.column()

        if role == QtCore.Qt.DisplayRole:
            if col == 0: return title
            if col == 1: return due
            if col == 2: return "Готово" if completed else "Открыта"
            if col == 3: return str(priority)
            if col == 4: return str(task_id)

        if role == QtCore.Qt.ForegroundRole:
            try:
                today = datetime.date.today()
                due_date = datetime.date.fromisoformat(due)
                if completed:
                    return QtGui.QBrush(QtGui.QColor("#777777"))
                elif due_date < today:
                    return QtGui.QBrush(QtGui.QColor("red"))
                elif due_date == today:
                    return QtGui.QBrush(QtGui.QColor("green"))
            except Exception:
                pass

        return None

    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.headers[section]
        return None

    def task_at_row(self, row):
        return self.rows[row]