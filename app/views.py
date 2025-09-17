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
    
    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Vertical and role == QtCore.Qt.DisplayRole:
            # Нумерация строк 1..N в текущем порядке (после сорт/фильтра)
            return section + 1
        return super().headerData(section, orientation, role)

class WrapDelegate(QtWidgets.QStyledItemDelegate):
    """
    Делегат, который рассчитывает высоту строки под многострочный текст.
    Применим к колонке 'description'.
    """
    def __init__(self, view, parent=None):
        super().__init__(parent)
        self.view = view
        self.margin = 6  # небольшой отступ

    def sizeHint(self, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        # ширина текущей колонки
        col_w = self.view.columnWidth(index.column())
        if col_w <= 0:
            col_w = 300

        doc = QtGui.QTextDocument()
        doc.setDefaultFont(opt.font)
        doc.setPlainText(opt.text)
        # Вычтем небольшой отступ под паддинги
        doc.setTextWidth(max(10, col_w - self.margin))
        sz = doc.size().toSize()
        return QtCore.QSize(col_w, sz.height() + self.margin)

    def paint(self, painter, option, index):
        # Отключим эллипсисы, чтобы текст не обрезался ...
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.textElideMode = QtCore.Qt.ElideNone
        # … и отрисуем стандартным способом
        style = opt.widget.style() if opt.widget else QtWidgets.QApplication.style()
        style.drawControl(QtWidgets.QStyle.CE_ItemViewItem, opt, painter, opt.widget)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("Планировщик задач")
        self.resize(900, 550)

        # Настройки (для сохранения ширин колонок и геометрии окна)
        self.settings = QtCore.QSettings("YourCompany", "PlanBoard")

        # Попробуем восстановить геометрию окна (размер/позицию)
        state_geom = self.settings.value("window_geometry")
        if state_geom is not None:
            try:
                self.restoreGeometry(state_geom)
            except Exception:
                pass

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
        self.view.setWordWrap(True)
        self.view.setTextElideMode(QtCore.Qt.ElideNone)

        # Заголовки
        hdr = self.view.horizontalHeader()
        hdr.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)

        vhdr = self.view.verticalHeader()
        vhdr.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        vhdr.setDefaultAlignment(QtCore.Qt.AlignCenter)

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

        # Компоновка
        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.search_edit)
        top.addWidget(self.filter_combo)

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.addLayout(top)
        layout.addWidget(self.view)
        self.setCentralWidget(central)

        # Делегат для многострочного описания
        self.desc_col = getattr(self.model, "column_index", lambda k: -1)("description")
        if isinstance(self.desc_col, int) and self.desc_col >= 0:
            # Убедись, что класс WrapDelegate определён в файле (как мы делали ранее)
            self.view.setItemDelegateForColumn(self.desc_col, WrapDelegate(self.view, self))
            hdr.sectionResized.connect(self._on_section_resized)

        # Восстановим ширины колонок (если сохранены)
        state = self.settings.value("header_state")
        if state is not None:
            try:
                hdr.restoreState(state)
            except Exception:
                pass

        # Инициализация поиска/фильтра
        self.apply_search(self.search_edit.text())
        self.apply_filter()

        # Подгон высоты строк
        self.view.resizeRowsToContents()

    def _on_section_resized(self, logicalIndex, oldSize, newSize):
        # Если менялась ширина колонки описания — пересчитать высоту строк
        if isinstance(self.desc_col, int) and self.desc_col >= 0 and logicalIndex == self.desc_col:
            self.view.resizeRowsToContents()

    def closeEvent(self, e):
        try:
            hdr_state = self.view.horizontalHeader().saveState()
            self.settings.setValue("header_state", hdr_state)
            self.settings.setValue("window_geometry", self.saveGeometry())
        finally:
            super().closeEvent(e)

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
            task_id = task["id"] if isinstance(task, dict) else task[0]
            self.repo.update_task(task_id, title, desc, due, completed, priority)
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
        col_title = getattr(self.model, "column_index", lambda k: 0)("title")
        self.proxy.setFilterKeyColumn(col_title if isinstance(col_title, int) and col_title >= 0 else 0)
        self.proxy.setFilterFixedString(text)

    def apply_filter(self):
        mode = self.filter_combo.currentText()
        self.proxy.setMode(mode)

    def refresh(self):
        self.model.load()
        self.apply_search(self.search_edit.text())
        self.apply_filter()
        self.view.resizeRowsToContents()



# Пояснения коротко:
# - Сохранение ширин: QSettings хранит состояние заголовка таблицы. При закрытии окна saveState(), при запуске restoreState().
# - Многострочное описание:
#   - setWordWrap(True) + setTextElideMode(ElideNone) чтобы текст не обрезался;
#   - вертикальный заголовок ResizeToContents, чтобы высота строк бралась по sizeHint;
#   - делегат WrapDelegate рассчитывает высоту на основе ширины колонки и текста (QTextDocument), поэтому описания любого размера будут видны целиком;
#   - при изменении ширины колонки с описанием пересчитываем высоты строк.











# from PyQt5 import QtWidgets, QtCore, QtGui
# from app.models import TaskTableModel
# from app.dialogs import TaskDialog
# from datetime import date


# class FilterProxy(QtCore.QSortFilterProxyModel):
#     def __init__(self, source_model, parent=None):
#         super().__init__(parent)
#         self._model = source_model
#         self.mode = "Все"

#     def setMode(self, mode):
#         if self.mode != mode:
#             self.mode = mode
#             self.invalidateFilter()

#     def filterAcceptsRow(self, source_row, parent):
#         # 1) Сначала применяем строковый фильтр (поиск)
#         if not super().filterAcceptsRow(source_row, parent):
#             return False

#         # 2) Затем применяем фильтр по режиму
#         r = self._model.rows[source_row]

#         # поддержка dict и tuple
#         if isinstance(r, dict):
#             completed = bool(r.get("completed"))
#             due = r.get("due_date")
#         else:
#             # (id, title, description, due_date, created_at, completed, priority)
#             completed = bool(r[5])
#             due = r[3]

#         try:
#             due_date = date.fromisoformat(due) if due else None
#         except Exception:
#             due_date = None

#         today = date.today()
#         m = self.mode

#         if m == "Все":
#             return True
#         if m == "Открытые":
#             return not completed
#         if m == "Просроченные":
#             return (not completed) and (due_date is not None) and (due_date < today)
#         if m == "На сегодня":
#             return (not completed) and (due_date is not None) and (due_date == today)
#         if m == "Выполненные":
#             return completed
#         return True


# class MainWindow(QtWidgets.QMainWindow):
#     def __init__(self, repo, parent=None):
#         super().__init__(parent)
#         self.repo = repo
#         self.setWindowTitle("Планировщик задач")
#         self.resize(900, 550)

#         # Модель
#         self.model = TaskTableModel(repo, self)

#         # Прокси (поиск + режим фильтра)
#         self.proxy = FilterProxy(self.model, self)
#         self.proxy.setSourceModel(self.model)
#         self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)

#         # Таблица
#         self.view = QtWidgets.QTableView()
#         self.view.setModel(self.proxy)

#         hdr = self.view.horizontalHeader()
#         hdr.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
#         # hdr.setSectionResizeMode(col_title, QtWidgets.QHeaderView.Stretch)    # чтобы текстовые колонки занимали всё доступное пространство
#         # hdr.setSectionResizeMode(col_desc, QtWidgets.QHeaderView.Stretch)

#         # индексы колонок по ключам модели
#         col_title = self.model.column_index("title")
#         col_desc = self.model.column_index("description")
#         col_due = self.model.column_index("due_date")
#         col_prio = self.model.column_index("priority")
#         col_done = self.model.column_index("completed")
#         col_created = self.model.column_index("created_at")

#         # примерные ширины
#         if col_title >= 0:
#             self.view.setColumnWidth(col_title, 220)
#         if col_desc >= 0:
#             self.view.setColumnWidth(col_desc, 400)
#         if col_due >= 0:
#             self.view.setColumnWidth(col_due, 110)
#         if col_prio >= 0:
#             self.view.setColumnWidth(col_prio, 110)
#         if col_done >= 0:
#             self.view.setColumnWidth(col_done, 110)
#         if col_created >= 0:
#             self.view.setColumnWidth(col_created, 110)

#         self.view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
#         self.view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
#         self.view.setSortingEnabled(True)

#         # Сортировка по сроку
#         col_due = getattr(self.model, "column_index", lambda k: 1)("due_date")
#         self.view.sortByColumn(col_due if isinstance(col_due, int) and col_due >= 0 else 1,
#                                QtCore.Qt.AscendingOrder)

#         # Панель инструментов
#         add_act = QtWidgets.QAction("Добавить", self)
#         edit_act = QtWidgets.QAction("Редактировать", self)
#         del_act = QtWidgets.QAction("Удалить", self)
#         refresh_act = QtWidgets.QAction("Обновить", self)

#         toolbar = self.addToolBar("Main")
#         toolbar.addAction(add_act)
#         toolbar.addAction(edit_act)
#         toolbar.addAction(del_act)
#         toolbar.addSeparator()
#         toolbar.addAction(refresh_act)

#         add_act.triggered.connect(self.add_task)
#         edit_act.triggered.connect(self.edit_task)
#         del_act.triggered.connect(self.delete_task)
#         refresh_act.triggered.connect(self.refresh)

#         # Поиск
#         self.search_edit = QtWidgets.QLineEdit()
#         self.search_edit.setPlaceholderText("Поиск по названию...")
#         self.search_edit.textChanged.connect(self.apply_search)

#         # Фильтры
#         self.filter_combo = QtWidgets.QComboBox()
#         self.filter_combo.addItems(["Все", "Открытые", "Просроченные", "На сегодня", "Выполненные"])
#         self.filter_combo.currentIndexChanged.connect(self.apply_filter)

#         top = QtWidgets.QHBoxLayout()
#         top.addWidget(self.search_edit)
#         top.addWidget(self.filter_combo)

#         central = QtWidgets.QWidget()
#         layout = QtWidgets.QVBoxLayout(central)
#         layout.addLayout(top)
#         layout.addWidget(self.view)
#         self.setCentralWidget(central)

#         # Инициализация поиска/фильтра
#         self.apply_search(self.search_edit.text())
#         self.apply_filter()

#     def source_row(self, proxy_index):
#         if not proxy_index.isValid():
#             return None
#         return self.proxy.mapToSource(proxy_index).row()

#     def selected_task(self):
#         idx = self.view.currentIndex()
#         if not idx.isValid():
#             return None
#         row = self.source_row(idx)
#         return self.model.rows[row] if row is not None else None

#     def add_task(self):
#         dlg = TaskDialog(self)
#         if dlg.exec_() == QtWidgets.QDialog.Accepted:
#             title, desc, due, completed, priority = dlg.get_data()
#             if title and due:
#                 self.repo.add_task(title, desc, due, priority)
#                 self.refresh()

#     def edit_task(self):
#         task = self.selected_task()
#         if not task:
#             return
#         dlg = TaskDialog(self, task=task)
#         if dlg.exec_() == QtWidgets.QDialog.Accepted:
#             title, desc, due, completed, priority = dlg.get_data()
#             # task может быть dict или tuple
#             task_id = task["id"] if isinstance(task, dict) else task[0]
#             try:
#                 # если update_task поддерживает именованные аргументы
#                 self.repo.update_task(task_id, title, desc, due, completed, priority)
#             finally:
#                 self.refresh()

#     def delete_task(self):
#         task = self.selected_task()
#         if not task:
#             return
#         res = QtWidgets.QMessageBox.question(self, "Удаление", "Удалить выбранную задачу?")
#         if res == QtWidgets.QMessageBox.Yes:
#             task_id = task["id"] if isinstance(task, dict) else task[0]
#             self.repo.delete_task(task_id)
#             self.refresh()

#     def apply_search(self, text):
#         # Колонка "Название"
#         col_title = getattr(self.model, "column_index", lambda k: 0)("title")
#         self.proxy.setFilterKeyColumn(col_title if isinstance(col_title, int) and col_title >= 0 else 0)
#         self.proxy.setFilterFixedString(text)

#     def apply_filter(self):
#         mode = self.filter_combo.currentText()
#         self.proxy.setMode(mode)

#     def refresh(self):
#         self.model.load()
#         # после перезагрузки убедимся, что параметры фильтра/поиска применены
#         self.apply_search(self.search_edit.text())
#         self.apply_filter()