# Главное окно, таблица, кнопки, простые фильтры и сортировка.

from PyQt5 import QtWidgets, QtCore, QtGui
from app.models import TaskTableModel
from app.dialogs import TaskDialog

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("Планировщик задач")
        self.resize(900, 550)

        self.model = TaskTableModel(repo)

        self.proxy = QtCore.QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)

        self.view = QtWidgets.QTableView()
        self.view.setModel(self.proxy)
        self.view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(1, QtCore.Qt.AscendingOrder)  # по сроку

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
        refresh_act.triggered.connect(self.model.load)

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
                self.model.load()

    def edit_task(self):
        task = self.selected_task()
        if not task:
            return
        dlg = TaskDialog(self, task=task)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            title, desc, due, completed, priority = dlg.get_data()
            task_id = task[0]
            self.repo.update_task(task_id, title, desc, due, completed, priority)
            self.model.load()

    def delete_task(self):
        task = self.selected_task()
        if not task:
            return
        res = QtWidgets.QMessageBox.question(self, "Удаление", "Удалить выбранную задачу?")
        if res == QtWidgets.QMessageBox.Yes:
            self.repo.delete_task(task[0])
            self.model.load()

    def apply_search(self, text):
        # Фильтрация по названию (колонка 0)
        self.proxy.setFilterKeyColumn(0)
        self.proxy.setFilterFixedString(text)

    def apply_filter(self):
        mode = self.filter_combo.currentText()

        def accept(source_row, parent):
            r = self.model.rows[source_row]
            task_id, title, desc, due, created, completed, priority = r
            from datetime import date
            try:
                due_date = date.fromisoformat(due)
            except Exception:
                return True
            today = date.today()

            if mode == "Все":
                return True
            if mode == "Открытые":
                return not completed
            if mode == "Просроченные":
                return (not completed) and (due_date < today)
            if mode == "На сегодня":
                return (not completed) and (due_date == today)
            if mode == "Выполненные":
                return bool(completed)
            return True

        class FilterProxy(QtCore.QSortFilterProxyModel):
            def __init__(self, parent=None, predicate=None):
                super().__init__(parent)
                self.predicate = predicate
            def filterAcceptsRow(self, source_row, parent):
                if self.predicate:
                    return self.predicate(source_row, parent)
                return True

        # Переустановим прокси, чтобы обновить кастомную фильтрацию
        pred = accept
        self.proxy = FilterProxy(self, predicate=pred)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.view.setModel(self.proxy)
        # применим текущий текст поиска
        self.apply_search(self.search_edit.text())