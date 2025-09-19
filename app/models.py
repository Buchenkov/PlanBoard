# Модель таблицы + раскраска строк.

from PyQt5 import QtCore, QtGui
import datetime

class TaskTableModel(QtCore.QAbstractTableModel):
    # Ключи полей и заголовки колонок
    COLUMNS = [
        ("title", "Название"),
        ("description", "Описание"),   # добавлено второй колонкой
        ("due_date", "Срок"),
        ("completed", "Выполнено"),
        ("created_at", "Создано"),
        ("priority", "Приоритет"),
        # ("id", "ID"),  # больше не показываем ID в таблице
    ]

    # Индексация для варианта с кортежами:
    # (id, title, description, due_date, created_at, completed, priority)
    TUPLE_INDEX = {
        "id": 0,
        "title": 1,
        "description": 2,
        "due_date": 3,
        "created_at": 4,
        "completed": 5,
        "priority": 6,
    }

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.rows = []
        self.order_by = "due_date ASC, priority DESC, id DESC"

        # self.view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        # self.view.customContextMenuRequested.connect(self.show_context_menu)

        self.load()

    def load(self):
        self.beginResetModel()
        self.rows = self.repo.list_tasks(self.order_by)
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.COLUMNS)

    def column_index(self, key):
        for i, (k, _) in enumerate(self.COLUMNS):
            if k == key:
                return i
        return -1

    def _get_value(self, row, key):
        # Поддержка и dict, и tuple
        if isinstance(row, dict):
            return row.get(key)
        idx = self.TUPLE_INDEX.get(key, None)
        if idx is None:
            return None
        try:
            return row[idx]
        except Exception:
            return None

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

        row = self.rows[index.row()]
        key = self.COLUMNS[index.column()][0]

        if role == QtCore.Qt.DisplayRole:
            if key == "completed":
                return "Готово" if self._get_value(row, "completed") else "Открыта"
            val = self._get_value(row, key)
            return "" if val is None else str(val)

        if role == QtCore.Qt.TextAlignmentRole:
            if key in ("priority", "id"):
                return int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            return int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        if role == QtCore.Qt.ForegroundRole:
            # Раскраска по срокам/статусу
            completed = bool(self._get_value(row, "completed"))
            due = self._get_value(row, "due_date")
            try:
                if not due:
                    return None
                today = datetime.date.today()
                due_date = datetime.date.fromisoformat(str(due))
                if completed:
                    return QtGui.QBrush(QtGui.QColor("#777777"))
                elif due_date < today:
                    return QtGui.QBrush(QtGui.QColor("red"))
                elif due_date == today:
                    return QtGui.QBrush(QtGui.QColor("green"))
            except Exception:
                pass

        return None

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal:
            return self.COLUMNS[section][1]
        return str(section + 1)

    def task_at_row(self, row):
        return self.rows[row]