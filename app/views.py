from PyQt5 import QtWidgets, QtCore, QtGui
import sys
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

        # Настройки (для сохранения ширин колонок и геометрии окна/состояния колонок)
        self.settings = QtCore.QSettings("YourCompany", "PlanBoard")

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

        # ДЕЙСТВИЯ (используются в меню-кнопке)
        self.add_act = QtWidgets.QAction("Добавить", self)
        self.edit_act = QtWidgets.QAction("Редактировать", self)
        self.del_act = QtWidgets.QAction("Удалить", self)
        self.refresh_act = QtWidgets.QAction("Обновить", self)

        self.add_act.triggered.connect(self.add_task)
        self.edit_act.triggered.connect(self.edit_task)
        self.del_act.triggered.connect(self.delete_task)
        self.refresh_act.triggered.connect(self.refresh)

        # Кнопка "О программе"
        self.act_about = QtWidgets.QAction("О программе", self)
        self.act_about.setToolTip("Информация о программе")
        self.act_about.triggered.connect(self.show_about)

        # Действие переключения темы
        self.act_dark = QtWidgets.QAction("Тёмная тема", self)
        self.act_dark.setCheckable(True)
        cur_theme = self.settings.value("theme", "dark")
        self.act_dark.setChecked(cur_theme == "dark")
        self.act_dark.toggled.connect(self.on_toggle_theme)

        # КНОПКА-МЕНЮ В ТУЛБАРЕ
        self.menu_btn = QtWidgets.QToolButton(self)
        self.menu_btn.setText("Меню  ")
        self.menu_btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.menu_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        # Корневое меню кнопки
        self.main_menu = QtWidgets.QMenu(self.menu_btn)
        self.main_menu.addAction(self.add_act)
        self.main_menu.addAction(self.edit_act)
        self.main_menu.addAction(self.del_act)
        self.main_menu.addSeparator()
        self.main_menu.addAction(self.refresh_act)
        self.main_menu.addSeparator()

        # Подменю "Колонки" с чекбоксами
        self.columns_menu = self.main_menu.addMenu("Колонки")
        self._build_columns_menu(self.columns_menu)

        self.menu_btn.setMenu(self.main_menu)

        # ТУЛБАР (один-единственный)
        toolbar= self.findChild(QtWidgets.QToolBar, "Main")
        if toolbar is None:
            toolbar = self.addToolBar("Main")
            toolbar.setObjectName("Main")
        # Хотим одну "ручку" — значит оставляем перемещение включённым;
        # если не нужна ручка — поставьте False / False.
        toolbar.setMovable(True)
        toolbar.setFloatable(True)
        toolbar.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)

        # ВАЖНО: не добавляем отдельные действия (add/edit/del/refresh) в тулбар,
        # вместо этого добавляем одну кнопку-меню, затем доп. действия справа.
        toolbar.addWidget(self.menu_btn)
        toolbar.addSeparator()
        toolbar.addAction(self.act_about)
        toolbar.addSeparator()
        toolbar.addAction(self.act_dark)

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
            # Убедитесь, что класс WrapDelegate определён
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


    def _build_columns_menu(self, menu: QtWidgets.QMenu):
        # Построение меню "Колонки" с чекбоксами, применение сохранённого состояния
        menu.clear()
        view = self.view
        model = self.model
        if view is None or model is None:
            return

        settings = self.settings
        val = settings.value("columns_hidden", None)
        hidden_map = {}

        # Попытки интерпретации сохранённого значения
        try:
            if val is None:
                hidden_map = {}
            elif isinstance(val, dict):
                # Старый/некоторые случаи QSettings уже вернули dict
                hidden_map = {str(k): bool(v) for k, v in val.items()}
            elif isinstance(val, (bytes, bytearray)):
                import json
                hidden_map = json.loads(val.decode("utf-8"))
            elif isinstance(val, QtCore.QByteArray):
                import json
                hidden_map = json.loads(bytes(val).decode("utf-8"))
            elif isinstance(val, str):
                import json
                hidden_map = json.loads(val)
            else:
                # Например, QVariantMap и т.п. — приведём к строке и попробуем распарсить
                s = str(val)
                try:
                    import json
                    hidden_map = json.loads(s)
                except Exception:
                    hidden_map = {}
        except Exception:
            hidden_map = {}

        # Применим видимость
        col_count = model.columnCount()
        for col in range(col_count):
            header = model.headerData(col, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole)
            text = str(header) if header is not None else f"Колонка {col + 1}"

            hidden = bool(hidden_map.get(str(col), view.isColumnHidden(col)))
            view.setColumnHidden(col, hidden)

            act = QtWidgets.QAction(text, menu)
            act.setCheckable(True)
            act.setChecked(not hidden if hidden in (True, False) else True)
            act.setChecked(not hidden)  # галка = колонка видима

            def on_toggled(checked, c=col):
                self.view.setColumnHidden(c, not checked)
                self._save_columns_state()

            act.toggled.connect(on_toggled)
            menu.addAction(act)

        # На всякий случай пересохраним в нормальном формате (JSON-строка)
        self._save_columns_state()


    def _save_columns_state(self):
        # Сохранение текущего состояния видимости колонок
        view = self.view
        model = self.model
        if view is None or model is None:
            return
        col_count = model.columnCount()
        hidden_map = {}
        for col in range(col_count):
            hidden_map[str(col)] = view.isColumnHidden(col)

        try:
            import json
            self.settings.setValue("columns_hidden", json.dumps(hidden_map))
        except Exception:
            self.settings.setValue("columns_hidden", hidden_map)

    def on_toggle_theme(self, checked):
        app = QtWidgets.QApplication.instance()
        try:
            if checked:
                enable_dark_theme(app)
                self.settings.setValue("theme", "dark")
            else:
                enable_light_theme(app)
                self.settings.setValue("theme", "light")
        except NameError:
            # Если функции темы не импортированы — просто игнорируем переключение
            pass

    def _on_section_resized(self, logicalIndex, oldSize, newSize):
        # Если менялась ширина колонки описания — пересчитать высоту строк
        if isinstance(self.desc_col, int) and self.desc_col >= 0 and logicalIndex == self.desc_col:
            self.view.resizeRowsToContents()

    def closeEvent(self, e):
        try:
            hdr_state = self.view.horizontalHeader().saveState()
            self.settings.setValue("header_state", hdr_state)
            # Если нужно сохранять геометрию окна, раскомментируйте:
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
        # Пересоберём меню колонок на случай изменения состава колонок
        self._build_columns_menu(self.columns_menu)

    def show_about(self):
        QtWidgets.QMessageBox.about(
            self,
            "О программе",
            "Программа для планирования задач\n\n© Ваша компания, 2025"
        )

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

class TitleBar(QtWidgets.QWidget):
    height_hint = 36

    def __init__(self, parent=None, title="Планировщик задач"):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self._pressed = False
        self._start_pos = None

        self.setFixedHeight(self.height_hint)
        self.setAutoFillBackground(False)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setStyleSheet("font-weight: 600;")
        self.title_label.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)

        btn_size = 28
        self.btn_min = QtWidgets.QToolButton(self); self.btn_min.setObjectName("BtnMin")
        self.btn_max = QtWidgets.QToolButton(self); self.btn_max.setObjectName("BtnMax")
        self.btn_close = QtWidgets.QToolButton(self); self.btn_close.setObjectName("BtnClose")
        self.btn_min.setText("—")
        self.btn_max.setText("▢")
        self.btn_close.setText("✕")

        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setFixedSize(btn_size, btn_size)
            b.setStyleSheet("QToolButton { border: none; } QToolButton:hover { background: rgba(0,0,0,0.08); }")
            b.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)

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

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.LeftButton:
            self._pressed = True
            w = self._window()
            if w is not None:
                self._start_pos = e.globalPos() - w.frameGeometry().topLeft()
            e.accept()
            return
        # Правый клик не обрабатываем здесь — им займётся FramelessWindow.eventFilter
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if self._pressed:
            w = self._window()
            if w is not None and not w.isMaximized():
                w.move(e.globalPos() - (self._start_pos or QtCore.QPoint()))
                e.accept()
                return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        was_pressed = self._pressed
        self._pressed = False
        super().mouseReleaseEvent(e)
        if was_pressed and e.button() == QtCore.Qt.LeftButton:
            w = self._window()
            if w is not None and hasattr(w, "try_snap"):
                w.try_snap(e.globalPos(), margin=20)


class TitleBar(QtWidgets.QWidget):
    height_hint = 36

    def __init__(self, parent=None, title="Планировщик задач"):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self._pressed = False
        self._start_pos = None

        self.setFixedHeight(self.height_hint)
        self.setAutoFillBackground(False)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setStyleSheet("font-weight: 600;")
        self.title_label.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)

        btn_size = 28
        self.btn_min = QtWidgets.QToolButton(self); self.btn_min.setObjectName("BtnMin")
        self.btn_max = QtWidgets.QToolButton(self); self.btn_max.setObjectName("BtnMax")
        self.btn_close = QtWidgets.QToolButton(self); self.btn_close.setObjectName("BtnClose")

        self.btn_min.setText("—")
        self.btn_max.setText("▢")
        self.btn_close.setText("✕")

        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setFixedSize(btn_size, btn_size)
            b.setStyleSheet("QToolButton { border: none; } QToolButton:hover { background: rgba(0,0,0,0.08); }")
            b.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)

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
        w = self._window()
        if w is not None:
            w.showMinimized()

    def _on_max_restore(self):
        w = self._window()
        if w is None:
            return
        if w.isMaximized():
            w.showNormal()
            self.btn_max.setText("▢")
        else:
            w.showMaximized()
            self.btn_max.setText("❐")

    def _on_close(self):
        w = self._window()
        if w is not None:
            w.close()

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.LeftButton:
            self._pressed = True
            w = self._window()
            if w is not None:
                self._start_pos = e.globalPos() - w.frameGeometry().topLeft()
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if self._pressed:
            w = self._window()
            if w is not None and not w.isMaximized():
                w.move(e.globalPos() - (self._start_pos or QtCore.QPoint()))
                e.accept()
                return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        self._pressed = False
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.LeftButton:
            self._on_max_restore()
            e.accept()
            return
        super().mouseDoubleClickEvent(e)

# Кастомная шапка окна
class FramelessWindow(QtWidgets.QWidget):
    RESIZE_MARGIN = 8  # ширина зоны ресайза по периметру окна

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.setObjectName("FramelessWindow")

        # Frameless окно; на Win7 с отключённым Aero возможны артефакты прозрачности.
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)  # при проблемах — закомментируйте

        self.settings = QtCore.QSettings("YourCompany", "PlanBoard")

        # Внешний контейнер с тенью и скруглениями
        self.frame = QtWidgets.QFrame()
        self.frame.setObjectName("frameRoot")
        self.frame.setStyleSheet("""
            QFrame#frameRoot {
                background: palette(base);
                border-radius: 10px;
            }
        """)

        # Тень может не работать без Aero. Если наблюдаете “черные углы” — закомментируйте эффект тени.
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setOffset(0, 8)
        shadow.setBlurRadius(24)
        shadow.setColor(QtGui.QColor(0, 0, 0, 90))
        self.frame.setGraphicsEffect(shadow)

        # Кастомная шапка
        self.titlebar = TitleBar(self, title="Планировщик задач")

        # Контент (ваш MainWindow)
        from app.views import MainWindow  # поправьте импорт под свой проект
        self.content = MainWindow(repo, parent=self.frame)
        self.content.setObjectName("MainWindowContent")
        self.content.setWindowFlags(QtCore.Qt.Widget)
        self.content.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        # Отключаем контекстное меню у тулбаров внутри MainWindow
        for tb in self.content.findChildren(QtWidgets.QToolBar):
            tb.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)

        # Компоновки
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)  # отступ под тень
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

        # Фильтр событий — только ПКМ для системного меню
        self.installEventFilter(self)
        self.frame.installEventFilter(self)
        self.titlebar.installEventFilter(self)
        # Не ставим app.installEventFilter, чтобы не перехватывать лишнего

        # Восстановление геометрии и состояния
        geom = self.settings.value("window_geometry")
        if geom is not None:
            try:
                self.restoreGeometry(geom)
            except Exception:
                pass
        win_state = int(self.settings.value("window_state", int(QtCore.Qt.WindowNoState)))
        if win_state == int(QtCore.Qt.WindowMaximized):
            self.showMaximized()

    # ПКМ: системное меню Windows
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonPress:
            me = event  # QMouseEvent
            if me.button() == QtCore.Qt.RightButton:
                if isinstance(obj, QtWidgets.QWidget) and self.isAncestorOf(obj):
                    self.show_system_menu(me.globalPos())
                    return True
        return super().eventFilter(obj, event)

    def contextMenuEvent(self, e: QtGui.QContextMenuEvent):
        self.show_system_menu(e.globalPos())

    def show_system_menu(self, global_pos: QtCore.QPoint):
        if sys.platform != "win32":
            menu =QtWidgets.QMenu(self)
            act_min = menu.addAction("Свернуть")
            act_max = menu.addAction("Восстановить" if self.isMaximized() else "Развернуть")
            menu.addSeparator()
            act_close = menu.addAction("Закрыть")
            chosen = menu.exec_(global_pos)
            if chosen == act_min:
                self.showMinimized()
            elif chosen == act_max:
                self.showNormal() if self.isMaximized() else self.showMaximized()
            elif chosen == act_close:
                self.close()
            return

        # Windows 7/10: системное меню через WinAPI
        try:
            import ctypes
            user32 = ctypes.windll.user32
            GWL_STYLE = -16
            WS_SYSMENU = 0x00080000
            WM_SYSCOMMAND = 0x0112
            TPM_LEFTALIGN = 0x0000
            TPM_RETURNCMD = 0x0100
            TPM_RIGHTBUTTON = 0x0002

            hwnd = int(self.winId())

            # Добавим WS_SYSMENU, если его нет (актуально для frameless)
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            if (style & WS_SYSMENU) == 0:
                user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_SYSMENU)

            # Активируем окно перед показом меню — иначе TrackPopupMenu может вернуть 0
            user32.SetForegroundWindow(hwnd)

            hMenu = user32.GetSystemMenu(hwnd, False)
            cmd = user32.TrackPopupMenu(
                hMenu,
                TPM_LEFTALIGN | TPM_RETURNCMD | TPM_RIGHTBUTTON,
                int(global_pos.x()),
                int(global_pos.y()),
                0,
                hwnd,
                None
            )
            if cmd:
                user32.PostMessageW(hwnd, WM_SYSCOMMAND, cmd, 0)
                return
        except Exception:
            pass

        # Fallback меню Qt, если системное не сработало
        menu = QtWidgets.QMenu(self)
        act_min = menu.addAction("Свернуть")
        act_max = menu.addAction("Восстановить" if self.isMaximized() else "Развернуть")
        menu.addSeparator()
        act_close = menu.addAction("Закрыть")
        chosen = menu.exec_(global_pos)
        if chosen == act_min:
            self.showMinimized()
        elif chosen == act_max:
            self.showNormal() if self.isMaximized() else self.showMaximized()
        elif chosen == act_close:
            self.close()

    # Windows: системный ресайз по краям/углам

    def nativeEvent(self, eventType, message):
        import sys
        if sys.platform != "win32":
            return False, 0
        if eventType not in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            return False, 0
        try:
            WM_NCHITTEST = 0x0084
            HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT, HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 10, 11, 12, 13, 14, 15, 16, 17

            from ctypes import wintypes, Structure, c_long

            class POINT(Structure):
                _fields_ = [("x", c_long), ("y", c_long)]

            class MSG(Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("message", wintypes.UINT),
                    ("wParam", wintypes.WPARAM),
                    ("lParam", wintypes.LPARAM),
                    ("time", wintypes.DWORD),
                    ("pt", POINT),
                ]

            ptr_val = message.__int__() if hasattr(message, "__int__") else int(message)
            msg = MSG.from_address(ptr_val)

            if msg.message != WM_NCHITTEST:
                return False, 0
            if self.isMaximized():
                return False, 0

            # Позиция курсора
            pos = QtGui.QCursor.pos()
            x, y = pos.x(), pos.y()

            # Геометрия всего окна (в глобальных координатах)
            win_rect = self.frameGeometry()
            wl, wr = win_rect.left(), win_rect.right()
            wt, wb = win_rect.top(), win_rect.bottom()

            # Геометрия видимой рамки (frameRoot) в глобальных координатах
            frame_rect = self.frame.geometry()
            frame_top_left = self.frame.mapToGlobal(QtCore.QPoint(0, 0))
            fl, ft = frame_top_left.x(), frame_top_left.y()
            fr, fb = fl + frame_rect.width() - 1, ft + frame_rect.height() - 1

            m = max(10, getattr(self, "RESIZE_MARGIN", 8))  # зона захвата, чуть шире

            # Хит-тест по видимой рамке (удобнее для пользователя)
            on_left = fl <= x <= fl + m
            on_right = fr - m <= x <= fr
            on_top = ft <= y <= ft + m
            on_bottom = fb - m <= y <= fb

            # Если курсор в зоне видимой рамки — отдаём коды ресайза
            if on_left and on_top:
                return True, HTTOPLEFT
            if on_right and on_top:
                return True, HTTOPRIGHT
            if on_left and on_bottom:
                return True, HTBOTTOMLEFT
            if on_right and on_bottom:
                return True, HTBOTTOMRIGHT
            if on_left:
                return True, HTLEFT
            if on_right:
                return True, HTRIGHT
            if on_top:
                return True, HTTOP
            if on_bottom:
                return True, HTBOTTOM

            # Резерв: если вдруг курсор у самого края окна (за пределами тени)
            on_left_w = wl <= x <= wl + m
            on_right_w = wr - m <= x <= wr
            on_top_w = wt <= y <= wt + m
            on_bottom_w = wb - m <= y <= wb

            if on_left_w and on_top_w:
                return True, HTTOPLEFT
            if on_right_w and on_top_w:
                return True, HTTOPRIGHT
            if on_left_w and on_bottom_w:
                return True, HTBOTTOMLEFT
            if on_right_w and on_bottom_w:
                return True, HTBOTTOMRIGHT
            if on_left_w:
                return True, HTLEFT
            if on_right_w:
                return True, HTRIGHT
            if on_top_w:
                return True, HTTOP
            if on_bottom_w:
                return True, HTBOTTOM

            return False, 0
        except Exception:
            return False, 0


    def closeEvent(self, e):
        try:
            self.settings.setValue("window_geometry", self.saveGeometry())
            self.settings.setValue(
                "window_state",
                int(QtCore.Qt.WindowMaximized if self.isMaximized() else QtCore.Qt.WindowNoState)
            )
        finally:
            super().closeEvent(e)




















# class FramelessWindow(QtWidgets.QWidget):
#     RESIZE_MARGIN = 8  # ширина зоны ресайза по периметру окна

#     def __init__(self, repo, parent=None):
#         super().__init__(parent)
#         self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
#         self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

#         # Настройки окна
#         self.settings = QtCore.QSettings("YourCompany", "PlanBoard")

#         # Внешний контейнер с тенью и скруглениями
#         self.frame = QtWidgets.QFrame()
#         self.frame.setObjectName("frameRoot")
#         self.frame.setStyleSheet("""
#             QFrame#frameRoot {
#                 background: palette(base);
#                 border-radius: 10px;
#             }
#         """)
#         shadow = QtWidgets.QGraphicsDropShadowEffect(self)
#         shadow.setOffset(0, 8)
#         shadow.setBlurRadius(24)
#         shadow.setColor(QtGui.QColor(0, 0, 0, 90))
#         self.frame.setGraphicsEffect(shadow)

#         # Кастомная шапка
#         self.titlebar = TitleBar(self, title="Планировщик задач")

#         # Контент (ваш MainWindow)
#         self.content = MainWindow(repo, parent=self.frame)
#         self.content.setWindowFlags(QtCore.Qt.Widget)
#         self.content.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

#         # Отключаем контекстное меню у всех тулбаров внутри MainWindow (чтобы не было чекбокса)
#         for tb in self.content.findChildren(QtWidgets.QToolBar):
#             tb.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)

#         # Компоновки
#         root = QtWidgets.QVBoxLayout(self)
#         root.setContentsMargins(18, 18, 18, 18)  # отступ под тень
#         root.setSpacing(0)
#         root.addWidget(self.frame)

#         content_layout = QtWidgets.QVBoxLayout(self.frame)
#         content_layout.setContentsMargins(1, 1, 1, 1)
#         content_layout.setSpacing(0)
#         content_layout.addWidget(self.titlebar)
#         content_layout.addWidget(self.content, 1)

#         # Грип для изменения размера
#         self.size_grip = QtWidgets.QSizeGrip(self.frame)
#         self.size_grip.setFixedSize(14, 14)
#         corner = QtWidgets.QHBoxLayout()
#         corner.setContentsMargins(0, 0, 0, 0)
#         corner.addStretch(1)
#         corner.addWidget(self.size_grip, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom)
#         content_layout.addLayout(corner)

#         # Кастомное контекстное меню по правому клику на всём окне (включая прозрачный верхний отступ)
#         self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
#         self.customContextMenuRequested.connect(
#             lambda pos: self.show_system_menu(self.mapToGlobal(pos))
#         )

#         # Восстановление геометрии
#         geom = self.settings.value("window_geometry")
#         if geom is not None:
#             try:
#                 self.restoreGeometry(geom)
#             except Exception:
#                 pass
#         win_state = int(self.settings.value("window_state", int(QtCore.Qt.WindowNoState)))
#         if win_state == int(QtCore.Qt.WindowMaximized):
#             self.showMaximized()

#         # Двойной клик по шапке — разворачивать/восстанавливать
#         self.titlebar.mouseDoubleClickEvent = self._titlebar_double_click

#     def contextMenuEvent(self, e: QtGui.QContextMenuEvent):
#         # Резервный путь показа системного меню
#         self.show_system_menu(e.globalPos())

#     def show_system_menu(self, global_pos: QtCore.QPoint):
#         # Показ системного меню Windows
#         if sys.platform != "win32":
#             # Fallback-меню для других ОС
#             menu = QtWidgets.QMenu(self)
#             act_min = menu.addAction("Свернуть")
#             act_max = menu.addAction("Восстановить" if self.isMaximized() else "Развернуть")
#             menu.addSeparator()
#             act_close = menu.addAction("Закрыть")
#             chosen = menu.exec_(global_pos)
#             if chosen == act_min:
#                 self.showMinimized()
#             elif chosen == act_max:
#                 self.showNormal() if self.isMaximized() else self.showMaximized()
#             elif chosen == act_close:
#                 self.close()
#             return

#         try:
#             import ctypes
#             user32 = ctypes.windll.user32
#             WM_SYSCOMMAND = 0x0112
#             TPM_LEFTALIGN = 0x0000
#             TPM_RETURNCMD = 0x0100
#             TPM_RIGHTBUTTON = 0x0002

#             hwnd = int(self.winId())
#             hMenu = user32.GetSystemMenu(hwnd, False)
#             cmd = user32.TrackPopupMenu(
#                 hMenu,
#                 TPM_LEFTALIGN | TPM_RETURNCMD | TPM_RIGHTBUTTON,
#                 int(global_pos.x()),
#                 int(global_pos.y()),
#                 0,
#                 hwnd,
#                 None
#             )
#             if cmd:
#                 user32.PostMessageW(hwnd, WM_SYSCOMMAND, cmd, 0)
#         except Exception:
#             # Fallback, если WinAPI не сработал
#             menu = QtWidgets.QMenu(self)
#             act_min = menu.addAction("Свернуть")
#             act_max = menu.addAction("Восстановить" if self.isMaximized() else "Развернуть")
#             menu.addSeparator()
#             act_close = menu.addAction("Закрыть")
#             chosen = menu.exec_(global_pos)
#             if chosen == act_min:
#                 self.showMinimized()
#             elif chosen == act_max:
#                 self.showNormal() if self.isMaximized() else self.showMaximized()
#             elif chosen == act_close:
#                 self.close()

#     # Windows: системный ресайз по краям/углам
#     def nativeEvent(self, eventType, message):
#         if sys.platform != "win32":
#             return False, 0
#         if eventType not in ("windows_generic_MSG", "windows_dispatcher_MSG"):
#             return False, 0
#         try:
#             WM_NCHITTEST = 0x0084
#             HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT, HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 10, 11, 12, 13, 14, 15, 16, 17

#             from ctypes import wintypes, Structure, c_long

#             class POINT(Structure):
#                 _fields_ = [("x", c_long), ("y", c_long)]

#             class MSG(Structure):
#                 _fields_ = [
#                     ("hwnd", wintypes.HWND),
#                     ("message", wintypes.UINT),
#                     ("wParam", wintypes.WPARAM),
#                     ("lParam", wintypes.LPARAM),
#                     ("time", wintypes.DWORD),
#                     ("pt", POINT),
#                 ]

#             ptr_val = message.int() if hasattr(message, "int") else int(message)
#             msg = MSG.from_address(ptr_val)

#             if msg.message != WM_NCHITTEST:
#                 return False, 0
#             if self.isMaximized():
#                 return False, 0

#             pos = QtGui.QCursor.pos()
#             x, y = pos.x(), pos.y()

#             rect = self.frameGeometry()
#             lx, rx = rect.left(), rect.right()
#             ty, by = rect.top(), rect.bottom()

#             m = self.RESIZE_MARGIN
#             on_left = lx <= x <= lx + m
#             on_right = rx - m <= x <= rx
#             on_top = ty <= y <= ty + m
#             on_bottom = by - m <= y <= by

#             if on_left and on_top:
#                 return True, HTTOPLEFT
#             if on_right and on_top:
#                 return True, HTTOPRIGHT
#             if on_left and on_bottom:
#                 return True, HTBOTTOMLEFT
#             if on_right and on_bottom:
#                 return True, HTBOTTOMRIGHT
#             if on_left:
#                 return True, HTLEFT
#             if on_right:
#                 return True, HTRIGHT
#             if on_top:
#                 return True, HTTOP
#             if on_bottom:
#                 return True, HTBOTTOM

#             return False, 0
#         except Exception:
#             return False, 0

#     def _titlebar_double_click(self, e):
#         if e.button() == QtCore.Qt.LeftButton:
#             self.titlebar._on_max_restore()

#     def closeEvent(self, e):
#         try:
#             self.settings.setValue("window_geometry", self.saveGeometry())
#             self.settings.setValue(
#                 "window_state",
#                 int(QtCore.Qt.WindowMaximized if self.isMaximized() else QtCore.Qt.WindowNoState)
#             )
#         finally:
#             super().closeEvent(e)


# class TitleBar(QtWidgets.QWidget):
#     height_hint = 36

#     def __init__(self, parent=None, title="Планировщик задач"):
#         super().__init__(parent)
#         self._pressed = False
#         self._start_pos = None

#         self.setFixedHeight(self.height_hint)
#         self.setAutoFillBackground(False)
#         self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

#         self.title_label = QtWidgets.QLabel(title)
#         self.title_label.setStyleSheet("font-weight: 600;")

#         btn_size = 28
#         self.btn_min = QtWidgets.QToolButton(self)
#         self.btn_max = QtWidgets.QToolButton(self)
#         self.btn_close = QtWidgets.QToolButton(self)

#         self.btn_min.setText("—")
#         self.btn_max.setText("▢")
#         self.btn_close.setText("✕")

#         for b in (self.btn_min, self.btn_max, self.btn_close):
#             b.setFixedSize(btn_size, btn_size)
#             b.setStyleSheet("QToolButton { border: none; } QToolButton:hover { background: rgba(0,0,0,0.08); }")

#         lay = QtWidgets.QHBoxLayout(self)
#         lay.setContentsMargins(10, 0, 6, 0)
#         lay.setSpacing(6)
#         lay.addWidget(self.title_label, 1)
#         lay.addWidget(self.btn_min)
#         lay.addWidget(self.btn_max)
#         lay.addWidget(self.btn_close)

#         self.btn_min.clicked.connect(self._on_min)
#         self.btn_max.clicked.connect(self._on_max_restore)
#         self.btn_close.clicked.connect(self._on_close)

#         # Кастомное контекстное меню на шапке
#         self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
#         self.customContextMenuRequested.connect(
#             lambda pos: self._call_system_menu(self.mapToGlobal(pos))
#         )

#     def _window(self):
#         return self.window()

#     def _call_system_menu(self, global_pos):
#         w = self._window()
#         if hasattr(w, "show_system_menu"):
#             w.show_system_menu(global_pos)

#     def _on_min(self):
#         self._window().showMinimized()

#     def _on_max_restore(self):
#         w = self._window()
#         if w.isMaximized():
#             w.showNormal()
#             self.btn_max.setText("▢")
#         else:
#             w.showMaximized()
#             self.btn_max.setText("❐")

#     def _on_close(self):
#         self._window().close()

#     def mousePressEvent(self, e: QtGui.QMouseEvent):
#         # Обрабатываем и левую (перетаскивание), и правую (системное меню) кнопки
#         if e.button() == QtCore.Qt.RightButton:
#             self._call_system_menu(e.globalPos())
#             e.accept()
#             return
#         if e.button() == QtCore.Qt.LeftButton:
#             self._pressed = True
#             # безопасная проверка: если вдруг нет окна или оно None
#             w = self._window()
#             if w is not None:
#                 self._start_pos = e.globalPos() - w.frameGeometry().topLeft()
#             e.accept()
#             return
#         super().mousePressEvent(e)

#     def mouseMoveEvent(self, e: QtGui.QMouseEvent):
#         if self._pressed:
#             w = self._window()
#             if w is not None and not w.isMaximized():
#                 w.move(e.globalPos() - (self._start_pos or QtCore.QPoint()))
#                 e.accept()
#                 return
#         super().mouseMoveEvent(e)

#     def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
#         self._pressed = False
#         super().mouseReleaseEvent(e)

#     def contextMenuEvent(self, e: QtGui.QContextMenuEvent):
#         # Резервный вызов системного меню
#         self._call_system_menu(e.globalPos())


