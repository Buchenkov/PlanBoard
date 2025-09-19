from PyQt5 import QtWidgets, QtCore, QtGui
from datetime import date

from app.models import TaskTableModel
from app.dialogs import TaskDialog
from app.theme import enable_dark_theme, enable_light_theme


class FilterProxy(QtCore.QSortFilterProxyModel):
    def __init__(self, source_model, parent=None):
        super().__init__(parent)
        self._model = source_model
        self.mode = "Все"
        self.setDynamicSortFilter(True)

    def setSourceModel(self, model):
        super().setSourceModel(model)
        self._model = model

    def setMode(self, mode):
        if self.mode != mode:
            self.mode = mode
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row, parent):
        # 1) Сначала применяем текстовый фильтр (поиск)
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
        if orientation == QtCore.Qt.Vertical:
            if role == QtCore.Qt.DisplayRole:
                return str(section + 1)
            if role == QtCore.Qt.TextAlignmentRole:
                return int(QtCore.Qt.AlignCenter)
        return super(FilterProxy, self).headerData(section, orientation, role)
    

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

        # # Попробуем восстановить геометрию окна (размер/позицию)
        # state_geom = self.settings.value("window_geometry")
        # if state_geom is not None:
        #     try:
        #         self.restoreGeometry(state_geom)
        #     except Exception:
        #         pass

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
        # Контекстное меню для таблицы
        self.view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu)

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

        # Действие переключения темы
        self.act_dark = QtWidgets.QAction("Тёмная тема", self)
        self.act_dark.setCheckable(True)

        # Прочитаем текущее значение и отметим галочку
        cur_theme = self.settings.value("theme", "dark")
        self.act_dark.setChecked(cur_theme == "dark")

        toolbar.addSeparator()
        toolbar.addAction(self.act_dark)

        self.act_dark.toggled.connect(self.on_toggle_theme)

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

    def on_toggle_theme(self, checked):
        app = QtWidgets.QApplication.instance()
        if checked:
            enable_dark_theme(app)
            self.settings.setValue("theme", "dark")
        else:
            enable_light_theme(app)
            self.settings.setValue("theme", "light")

    def _on_section_resized(self, logicalIndex, oldSize, newSize):
        # Если менялась ширина колонки описания — пересчитать высоту строк
        if isinstance(self.desc_col, int) and self.desc_col >= 0 and logicalIndex == self.desc_col:
            self.view.resizeRowsToContents()

    def closeEvent(self, e):
        try:
            hdr_state = self.view.horizontalHeader().saveState()
            self.settings.setValue("header_state", hdr_state)
            # self.settings.setValue("window_geometry", self.saveGeometry())
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

    def show_context_menu(self, pos):
        index = self.view.indexAt(pos)
        has_sel = index.isValid()
        if has_sel:
            # Выделим строку под курсором, чтобы команды работали по ней
            self.view.selectRow(index.row())

        menu = QtWidgets.QMenu(self)

        act_add = menu.addAction("Добавить")
        act_add.triggered.connect(self.add_task)

        act_edit = menu.addAction("Редактировать")
        act_edit.setEnabled(has_sel)
        act_edit.triggered.connect(self.edit_task)

        act_del = menu.addAction("Удалить")
        act_del.setEnabled(has_sel)
        act_del.triggered.connect(self.delete_task)

        # Переключатель “Выполнено”
        task = self.selected_task() if has_sel else None
        if task:
            completed = bool(task.get("completed") if isinstance(task, dict) else task[5])
            toggle_text = "Отметить выполненной" if not completed else "Снять отметку выполнения"
            menu.addSeparator()
            act_toggle = menu.addAction(toggle_text)

            def toggle_completed():
                task_id = task["id"] if isinstance(task, dict) else task[0]
                title = task.get("title") if isinstance(task, dict) else task[1]
                desc = task.get("description") if isinstance(task, dict) else task[2]
                due = task.get("due_date") if isinstance(task, dict) else task[3]
                priority = task.get("priority") if isinstance(task, dict) else task[6]
                self.repo.update_task(task_id, title, desc, due, not completed, priority)
                self.refresh()

            act_toggle.triggered.connect(toggle_completed)

        menu.addSeparator()
        act_refresh = menu.addAction("Обновить")
        act_refresh.triggered.connect(self.refresh)

        global_pos = self.view.viewport().mapToGlobal(pos)
        menu.exec_(global_pos)

# Кастомная шапка окна
class TitleBar(QtWidgets.QWidget):
    height_hint = 36

    def __init__(self, parent=None, title="Планировщик задач"):
        super().__init__(parent)
        self._pressed = False
        self._start_pos = None
        self._maximized = False

        self.setFixedHeight(self.height_hint)
        self.setAutoFillBackground(False)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setStyleSheet("font-weight: 600;")

        btn_size = 28
        self.btn_min = QtWidgets.QToolButton(self)
        self.btn_max = QtWidgets.QToolButton(self)
        self.btn_close = QtWidgets.QToolButton(self)

        self.btn_min.setText("—")
        self.btn_max.setText("▢")
        self.btn_close.setText("✕")

        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setFixedSize(btn_size, btn_size)
            b.setStyleSheet("QToolButton { border: none; } QToolButton:hover { background: rgba(0,0,0,0.08); }")

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 6, 0)
        lay.setSpacing(6)
        lay.addWidget(self.title_label, 1)
        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_max)
        lay.addWidget(self.btn_close)

        self.btn_min.clicked.connect(self._on_min)
        self.btn_max.clicked.connect(self._on_max_restore)
        self.btn_close.clicked.connect(self._on_close)

    def _window(self):
        return self.window()

    def _on_min(self):
        self._window().showMinimized()

    def _on_max_restore(self):
        w = self._window()
        if w.isMaximized():
            w.showNormal()
            self.btn_max.setText("▢")
        else:
            w.showMaximized()
            self.btn_max.setText("❐")

    def _on_close(self):
        self._window().close()

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._pressed = True
            self._start_pos = e.globalPos() - self._window().frameGeometry().topLeft()
            e.accept()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._pressed and not self._window().isMaximized():
            self._window().move(e.globalPos() - self._start_pos)
            e.accept()
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._pressed = False
        super().mouseReleaseEvent(e)

# Безрамочный контейнер поверх вашего MainWindow
class FramelessWindow(QtWidgets.QWidget):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        self.settings = QtCore.QSettings("YourCompany", "PlanBoard")

        self.frame = QtWidgets.QFrame()
        self.frame.setObjectName("frameRoot")
        self.frame.setStyleSheet("""
            QFrame#frameRoot {
                background: palette(base);
                border-radius: 10px;
            }
        """)
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setOffset(0, 8)
        shadow.setBlurRadius(24)
        shadow.setColor(QtGui.QColor(0, 0, 0, 90))
        self.frame.setGraphicsEffect(shadow)

        self.titlebar = TitleBar(self, title="Планировщик задач")

        # ВАЖНО: вставляем ваш MainWindow как дочерний виджет
        self.content = MainWindow(repo, parent=self.frame)
        # Гарантируем, что он ведёт себя как виджет в layout
        self.content.setWindowFlags(QtCore.Qt.Widget)
        self.content.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        # Компоновки
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(0)
        root.addWidget(self.frame)

        content_layout = QtWidgets.QVBoxLayout(self.frame)
        content_layout.setContentsMargins(1, 1, 1, 1)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.titlebar)
        content_layout.addWidget(self.content, 1)

        # Грип для изменения размера
        self.size_grip = QtWidgets.QSizeGrip(self.frame)
        self.size_grip.setFixedSize(14, 14)
        corner = QtWidgets.QHBoxLayout()
        corner.setContentsMargins(0, 0, 0, 0)
        corner.addStretch(1)
        corner.addWidget(self.size_grip, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom)
        content_layout.addLayout(corner)

        # Восстановление геометрии
        geom = self.settings.value("window_geometry")
        if geom is not None:
            try:
                self.restoreGeometry(geom)
            except Exception:
                pass
        win_state = int(self.settings.value("window_state", int(QtCore.Qt.WindowNoState)))
        if win_state == int(QtCore.Qt.WindowMaximized):
            self.showMaximized()

        self.titlebar.mouseDoubleClickEvent = self._titlebar_double_click

        # Быстрая диагностика
        print("Frameless: frame has layout:", self.frame.layout() is not None)
        print("Frameless: content isVisible:", self.content.isVisible())
        # Если меню внутри MainWindow, покажет пункты:
        try:
            print("Frameless: menu actions:", [a.text() for a in self.content.menuBar().actions()])
        except Exception as ex:
            print("Frameless: menu inspect error:", ex)

    def _titlebar_double_click(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self.titlebar._on_max_restore()

    def closeEvent(self, e):
        try:
            self.settings.setValue("window_geometry", self.saveGeometry())
            self.settings.setValue(
                "window_state",
                int(QtCore.Qt.WindowMaximized if self.isMaximized() else QtCore.Qt.WindowNoState)
            )
        finally:
            super().closeEvent(e)


