from PyQt5 import QtWidgets, QtCore, QtGui
from app.models import TaskTableModel
from app.dialogs import TaskDialog
from datetime import date


class FilterProxy(QtCore.QSortFilterProxyModel):
    def __init__(self, source_model, parent=None):
        super().__init__(parent)
        self._model = source_model
        self.mode = "Все"

    def setMode(self, mode):
        if self.mode != mode:
            self.mode = mode
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row, parent):
        # 1) Сначала применяем строковый фильтр (поиск)
        if not super().filterAcceptsRow(source_row, parent):
            return False

        # 2) Затем применяем фильтр по режиму
        r = self._model.rows[source_row]

        # поддержка dict и tuple
        if isinstance(r, dict):
            completed = bool(r.get("completed"))
            due = r.get("due_date")
        else:
            # (id, title, description, due_date, created_at, completed, priority)
            completed = bool(r[5])
            due = r[3]

        try:
            due_date = date.fromisoformat(due) if due else None
        except Exception:
            due_date = None

        today = date.today()
        m = self.mode

        if m == "Все":
            return True
        if m == "Открытые":
            return not completed
        if m == "Просроченные":
            return (not completed) and (due_date is not None) and (due_date < today)
        if m == "На сегодня":
            return (not completed) and (due_date is not None) and (due_date == today)
        if m == "Выполненные":
            return completed
        return True


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("Планировщик задач")
        self.resize(900, 550)

        # Модель
        self.model = TaskTableModel(repo, self)

        # Прокси (поиск + режим фильтра)
        self.proxy = FilterProxy(self.model, self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)

        # Таблица
        self.view = QtWidgets.QTableView()
        self.view.setModel(self.proxy)
        self.view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.view.setSortingEnabled(True)

        # Сортировка по сроку
        col_due = getattr(self.model, "column_index", lambda k: 1)("due_date")
        self.view.sortByColumn(col_due if isinstance(col_due, int) and col_due >= 0 else 1,
                               QtCore.Qt.AscendingOrder)

        # Панель инструментов
        add_act = QtWidgets.QAction("Добавить", self)
        edit_act = QtWidgets.QAction("Редактировать", self)
        del_act = QtWidgets.QAction("Удалить", self)
        refresh_act = QtWidgets.QAction("Обновить", self)

        toolbar = self.addToolBar("Main")
        toolbar.addAction(add_act)
        toolbar.addAction(edit_act)
        toolbar.addAction(del_act)
        toolbar.addSeparator()
        toolbar.addAction(refresh_act)

        add_act.triggered.connect(self.add_task)
        edit_act.triggered.connect(self.edit_task)
        del_act.triggered.connect(self.delete_task)
        refresh_act.triggered.connect(self.refresh)

        # Поиск
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по названию...")
        self.search_edit.textChanged.connect(self.apply_search)

        # Фильтры
        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.addItems(["Все", "Открытые", "Просроченные", "На сегодня", "Выполненные"])
        self.filter_combo.currentIndexChanged.connect(self.apply_filter)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.search_edit)
        top.addWidget(self.filter_combo)

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.addLayout(top)
        layout.addWidget(self.view)
        self.setCentralWidget(central)

        # Инициализация поиска/фильтра
        self.apply_search(self.search_edit.text())
        self.apply_filter()

    def source_row(self, proxy_index):
        if not proxy_index.isValid():
            return None
        return self.proxy.mapToSource(proxy_index).row()

    def selected_task(self):
        idx = self.view.currentIndex()
        if not idx.isValid():
            return None
        row = self.source_row(idx)
        return self.model.rows[row] if row is not None else None

    def add_task(self):
        dlg = TaskDialog(self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            title, desc, due, completed, priority = dlg.get_data()
            if title and due:
                self.repo.add_task(title, desc, due, priority)
                self.refresh()

    def edit_task(self):
        task = self.selected_task()
        if not task:
            return
        dlg = TaskDialog(self, task=task)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            title, desc, due, completed, priority = dlg.get_data()
            # task может быть dict или tuple
            task_id = task["id"] if isinstance(task, dict) else task[0]
            try:
                # если update_task поддерживает именованные аргументы
                self.repo.update_task(task_id, title, desc, due, completed, priority)
            finally:
                self.refresh()

    def delete_task(self):
        task = self.selected_task()
        if not task:
            return
        res = QtWidgets.QMessageBox.question(self, "Удаление", "Удалить выбранную задачу?")
        if res == QtWidgets.QMessageBox.Yes:
            task_id = task["id"] if isinstance(task, dict) else task[0]
            self.repo.delete_task(task_id)
            self.refresh()

    def apply_search(self, text):
        # Колонка "Название"
        col_title = getattr(self.model, "column_index", lambda k: 0)("title")
        self.proxy.setFilterKeyColumn(col_title if isinstance(col_title, int) and col_title >= 0 else 0)
        self.proxy.setFilterFixedString(text)

    def apply_filter(self):
        mode = self.filter_combo.currentText()
        self.proxy.setMode(mode)

    def refresh(self):
        self.model.load()
        # после перезагрузки убедимся, что параметры фильтра/поиска применены
        self.apply_search(self.search_edit.text())
        self.apply_filter()