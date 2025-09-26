from PyQt5 import QtCore, QtGui, QtWidgets
from app.models import TaskTableModel
from datetime import date
from app.dialogs import TaskEditDialog

import sys


class FilterProxy(QtCore.QSortFilterProxyModel):
    def __init__(self, source_model, parent=None):
        super().__init__(parent)
        self._model = source_model
        self.mode = "Все"
        # Поиск будет регистронезависимым
        self.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)

    def setMode(self, mode: str):
        if self.mode != mode:
            self.mode = mode
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row, parent):
        # 1) Строковый фильтр (поиск)
        if not super().filterAcceptsRow(source_row, parent):
            return False

        # 2) Фильтр по режиму
        try:
            r = self._model.rows[source_row]
        except Exception:
            return True

        # Поддержка dict и tuple
        if isinstance(r, dict):
            completed = bool(r.get("completed"))
            due = r.get("due_date") or r.get("due")
        else:
            # (id, title, description, due_date, created_at, completed, priority)
            try:
                completed = bool(r[5])
                due = r[3]
            except Exception:
                completed = False
                due = None

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
    

class WrapDelegate(QtWidgets.QStyledItemDelegate):
    """
    Делегат для переноса длинных строк по ширине колонки (включая без пробелов).
    """
    def __init__(self, view, parent=None):
        super().__init__(parent)
        self.view = view
        self.h_margin = 6
        self.v_margin = 4

    def _make_doc(self, option: QtWidgets.QStyleOptionViewItem, text: str, width: int, selected: bool):
        doc = QtGui.QTextDocument()
        doc.setDefaultFont(option.font)

        topt = QtGui.QTextOption()
        # перенос даже внутри «слова» (цифры подряд, без пробелов)
        topt.setWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        doc.setDefaultTextOption(topt)

        # цвет текста
        color = option.palette.highlightedText().color() if selected else option.palette.text().color()

        import html
        safe = html.escape(text or "").replace("\n", "<br/>")
        # white-space:pre-wrap сохраняет явные \n, переносит остальное
        doc.setHtml(f'<div style="color:{color.name()}; white-space:pre-wrap;">{safe}</div>')

        doc.setTextWidth(max(10, width))
        return doc

    def sizeHint(self, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        # Текст берём напрямую из модели (иногда opt.text бывает пустым)
        text = str(index.data(QtCore.Qt.DisplayRole) or "")
        col_w = max(10, self.view.columnWidth(index.column()) - self.h_margin)
        doc = self._make_doc(opt, text, col_w, selected=bool(opt.state & QtWidgets.QStyle.State_Selected))
        szf = doc.documentLayout().documentSize()
        return QtCore.QSize(col_w + self.h_margin, int(szf.height()) + self.v_margin)

    def paint(self, painter, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.textElideMode = QtCore.Qt.ElideNone

        # фон выделения
        if opt.state & QtWidgets.QStyle.State_Selected:
            painter.save()
            painter.fillRect(opt.rect, opt.palette.highlight())
            painter.restore()

        # текст напрямую из модели
        text = str(index.data(QtCore.Qt.DisplayRole) or "")
        rect = opt.rect.adjusted(self.h_margin // 2, self.v_margin // 2, -self.h_margin // 2, -self.v_margin // 2)
        doc = self._make_doc(opt, text, max(10, rect.width()), selected=bool(opt.state & QtWidgets.QStyle.State_Selected))

        painter.save()
        painter.translate(rect.topLeft())
        clip = QtCore.QRectF(0, 0, rect.width(), rect.height())
        doc.drawContents(painter, clip)
        painter.restore()

        # фокус, как в стандартном делегате
        if opt.state & QtWidgets.QStyle.State_HasFocus:
            opt2 = QtWidgets.QStyleOptionFocusRect()
            opt2.rect = opt.rect
            opt2.state = QtWidgets.QStyle.State_KeyboardFocusChange | QtWidgets.QStyle.State_Item
            opt2.backgroundColor = opt.palette.highlight().color()
            style = opt.widget.style() if opt.widget else QtWidgets.QApplication.style()
            style.drawPrimitive(QtWidgets.QStyle.PE_FrameFocusRect, opt2, painter, opt.widget)


class TitleBar(QtWidgets.QWidget):
    height_hint = 36
    def __init__(self, parent=None, title="Планировщик задач"):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self._pressed = False
        self._start_pos = None

        self.btn_min = QtWidgets.QToolButton(self); self.btn_min.setObjectName("BtnMin")
        self.btn_max = QtWidgets.QToolButton(self); self.btn_max.setObjectName("BtnMax")
        self.btn_close = QtWidgets.QToolButton(self); self.btn_close.setObjectName("BtnClose")
        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)

        self.btn_min.setText("–")
        self.btn_max.setText("□")
        self.btn_close.setText("×")

        self.label = QtWidgets.QLabel(title, self)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 6, 0)
        lay.setSpacing(6)
        lay.addWidget(self.label, 1)
        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_max)
        lay.addWidget(self.btn_close)

        self.btn_min.clicked.connect(self._on_minimize)
        self.btn_max.clicked.connect(self._on_max_restore)
        self.btn_close.clicked.connect(self._on_close)

    def _window(self):
        return self.window()
    def _on_minimize(self):
        w = self._window()
        if w: w.showMinimized()
    def _on_max_restore(self):
        w = self._window()
        if not w: return
        if w.isMaximized():
            w.showNormal(); self.btn_max.setText("□")
        else:
            w.showMaximized(); self.btn_max.setText("❐")
    def _on_close(self):
        w = self._window()
        if w: w.close()
    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.LeftButton:
            self._pressed = True
            w = self._window()
            if w is not None:
                self._start_pos = e.globalPos() - w.frameGeometry().topLeft()
            e.accept(); return
        super().mousePressEvent(e)
    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if self._pressed:
            w = self._window()
            if w is not None and not w.isMaximized():
                w.move(e.globalPos() - (self._start_pos or QtCore.QPoint()))
                e.accept(); return
        super().mouseMoveEvent(e)
    def mouseDoubleClickEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.LeftButton:
            self._on_max_restore()
            e.accept(); return
        super().mouseDoubleClickEvent(e)
    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        self._pressed = False
        super().mouseReleaseEvent(e)


class WrapDelegate(QtWidgets.QStyledItemDelegate):
    """
    Делегат для переноса длинных строк по ширине колонки (включая последовательности без пробелов).
    """
    def __init__(self, view, parent=None):
        super().__init__(parent)
        self.view = view
        self.h_margin = 6
        self.v_margin = 4

    def _make_doc(self, option: QtWidgets.QStyleOptionViewItem, text: str, width: int):
        doc = QtGui.QTextDocument()
        doc.setDefaultFont(option.font)

        topt = QtGui.QTextOption()
        # Перенос внутри длинных «слов» (WrapAnywhere — цифры и буквы без пробелов тоже переносятся)
        topt.setWrapMode(QtGui.QTextOption.WrapAnywhere)
        doc.setDefaultTextOption(topt)

        doc.setPlainText(text or "")
        doc.setTextWidth(max(10, width))
        return doc

    def sizeHint(self, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = str(index.data(QtCore.Qt.DisplayRole) or "")
        col_w = max(10, self.view.columnWidth(index.column()) - self.h_margin)
        doc = self._make_doc(opt, text, col_w)
        sz = doc.size().toSize()
        return QtCore.QSize(col_w + self.h_margin, sz.height() + self.v_margin)

    def paint(self, painter, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.textElideMode = QtCore.Qt.ElideNone

        rect = opt.rect.adjusted(self.h_margin // 2, self.v_margin // 2, -self.h_margin // 2, -self.v_margin // 2)

        # Фон выделения
        if opt.state & QtWidgets.QStyle.State_Selected:
            painter.save()
            painter.fillRect(opt.rect, opt.palette.highlight())
            painter.restore()

        text = str(index.data(QtCore.Qt.DisplayRole) or "")
        doc = self._make_doc(opt, text, max(10, rect.width()))

        # Цвет текста при выделении
        if opt.state & QtWidgets.QStyle.State_Selected:
            clr = opt.palette.highlightedText().color()
            cursor = QtGui.QTextCursor(doc)
            cursor.select(QtGui.QTextCursor.Document)
            fmt = QtGui.QTextCharFormat()
            fmt.setForeground(QtGui.QBrush(clr))
            cursor.mergeCharFormat(fmt)

        painter.save()
        painter.translate(rect.topLeft())
        doc.drawContents(painter, QtCore.QRectF(0, 0, rect.width(), rect.height()))
        painter.restore()

        # Фокусная рамка
        if opt.state & QtWidgets.QStyle.State_HasFocus:
            opt_focus = QtWidgets.QStyleOptionFocusRect()
            opt_focus.rect = opt.rect
            opt_focus.state = QtWidgets.QStyle.State_KeyboardFocusChange | QtWidgets.QStyle.State_Item
            opt_focus.backgroundColor = opt.palette.highlight().color()
            style = opt.widget.style() if opt.widget else QtWidgets.QApplication.style()
            style.drawPrimitive(QtWidgets.QStyle.PE_FrameFocusRect, opt_focus, painter, opt.widget)


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
        self.model.load()

        # Прокси (поиск + режим фильтра)
        # Важно: FilterProxy должен быть вашим кастомным классом с методом setMode
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
        self.view.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        # Контекстное меню для таблицы
        self.view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu)

        # Заголовки
        hdr = self.view.horizontalHeader()
        hdr.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)

        vhdr = self.view.verticalHeader()
        vhdr.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        vhdr.setDefaultAlignment(QtCore.Qt.AlignCenter)

        # Делегат для многострочного описания — ВАЖНО: это должно быть в init
        self.desc_col = getattr(self.model, "column_index", lambda k: -1)("description")
        if isinstance(self.desc_col, int) and self.desc_col >= 0:
            # Убедитесь, что класс WrapDelegate определён и импортирован
            self.view.setItemDelegateForColumn(self.desc_col, WrapDelegate(self.view, self))
            # чтобы высота строк обновлялась при ресайзе колонки
            hdr.sectionResized.connect(self._on_section_resized)
        # Диагностика делегата (оставляем как у вас)
        print("desc_col:", self.desc_col)
        assert isinstance(self.desc_col, int) and self.desc_col >= 0, "Колонка 'description' не найдена"
        print("delegate set:", isinstance(self.view.itemDelegateForColumn(self.desc_col), WrapDelegate))

        # Восстановим ширины колонок (если сохранены) — делать после создания view и модели
        state = self.settings.value("header_state")
        if state is not None:
            try:
                hdr.restoreState(state)
            except Exception:
                pass

        # Сортировка по сроку
        col_due = getattr(self.model, "column_index", lambda k: 1)("due_date")
        self.view.sortByColumn(
            col_due if isinstance(col_due, int) and col_due >= 0 else 1,
            QtCore.Qt.AscendingOrder
        )

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
        self.act_dark.setChecked(str(cur_theme) == "dark")
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
        toolbar = self.findChild(QtWidgets.QToolBar, "Main")
        if toolbar is None:
            toolbar = self.addToolBar("Main")
            toolbar.setObjectName("Main")
        toolbar.setMovable(True)
        toolbar.setFloatable(True)
        toolbar.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)

        # ВАЖНО: добавляем одну кнопку-меню, затем доп. действия справа.
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

        # Инициализация поиска/фильтра с восстановлением значений
        last_query = self.settings.value("search_query", "")
        self.search_edit.setText(str(last_query))
        last_filter = self.settings.value("filter_mode", "Все")
        ix = self.filter_combo.findText(str(last_filter))
        if ix >= 0:
            self.filter_combo.setCurrentIndex(ix)
        # Явно применим (если ничего не изменилось, всё равно актуализирует прокси)
        self.apply_search(self.search_edit.text())
        self.apply_filter()

        # Подгон высоты строк
        self.view.resizeRowsToContents()

        # Двойной клик — редактирование
        self.view.doubleClicked.connect(lambda idx: self.edit_task())

        # шорткаты
        self.add_act.setShortcut("Ctrl+N")
        self.edit_act.setShortcut("Ctrl+Return")
        self.del_act.setShortcut("Delete")
        self.refresh_act.setShortcut("F5")

        # Применение темы через окно-обёртку (если есть)
        mode = str(self.settings.value("theme", "dark"))
        w = self.window()
        if hasattr(w, "apply_theme"):
            w.apply_theme(mode)

    # обработчик пересчёта высоты — ДОЛЖЕН быть отдельным методом
    def _on_section_resized(self, logicalIndex, oldSize, newSize):
        if isinstance(self.desc_col, int) and self.desc_col >= 0 and logicalIndex == self.desc_col:
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
                s = str(val)
                try:
                    import json
                    hidden_map = json.loads(s)
                except Exception:
                    hidden_map = {}
        except Exception:
            hidden_map = {}

        # Применим видимость и создадим пункты меню
        col_count = model.columnCount()
        for col in range(col_count):
            header = model.headerData(col, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole)
            text = str(header) if header is not None else f"Колонка {col + 1}"

            hidden = bool(hidden_map.get(str(col), view.isColumnHidden(col)))
            view.setColumnHidden(col, hidden)

            act = QtWidgets.QAction(text, menu)
            act.setCheckable(True)
            act.setChecked(not hidden)

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
        # меняем тему через окно-обёртку (FramelessWindow.apply_theme)
        w = self.window()
        if checked:
            # тёмная тема
            if hasattr(w, "apply_theme"):
                w.apply_theme("dark")
            self.settings.setValue("theme", "dark")
        else:
            # светлая тема
            if hasattr(w, "apply_theme"):
                w.apply_theme("light")
            self.settings.setValue("theme", "light")

        # обновим шапку (если кастомная TitleBar умеет подстраиваться)
        if hasattr(w, "titlebar") and hasattr(w.titlebar, "update_theme"):
            w.titlebar.update_theme()

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
        dlg = TaskEditDialog(self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            title, desc, due, completed, priority = dlg.get_data()

            # Проверка названия
            if not title.strip():
                QtWidgets.QMessageBox.warning(self, "Внимание", "Название не может быть пустым.")
                return

            # Проверка срока (yyyy-MM-dd) и валидности даты
            if not due or not isinstance(due, str):
                QtWidgets.QMessageBox.warning(self, "Внимание", "Укажите срок выполнения в формате yyyy-MM-dd.")
                return

            qd = QtCore.QDate.fromString(due, "yyyy-MM-dd")
            if not qd.isValid():
                QtWidgets.QMessageBox.warning(self, "Внимание",
                    f"Дата '{due}' некорректна. Ожидается формат yyyy-MM-dd (например, {QtCore.QDate.currentDate().toString('yyyy-MM-dd')})."
                )
                return

            # Дополнительно: если дата в прошлом — спросим подтверждение
            today = QtCore.QDate.currentDate()
            if qd < today:
                res = QtWidgets.QMessageBox.question(
                    self, "Просроченный срок",
                    "Указан срок в прошлом. Всё равно создать задачу?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No
                )
                if res != QtWidgets.QMessageBox.Yes:
                    return

            # Создание задачи с поддержкой разных сигнатур репозитория
            try:
                # пробуем именованные аргументы
                self.repo.add_task(
                    title=title,
                    description=desc,
                    due_date=due,
                    completed=completed,
                    priority=priority
                )
            except TypeError:
                # если репозиторий ожидает позиционные аргументы
                try:
                    self.repo.add_task(title, desc, due, completed, priority)
                except TypeError:
                    # самый старый вариант (без completed)
                    self.repo.add_task(title, desc, due, priority)

            self.refresh()

    def edit_task(self):
        task = self.selected_task()
        if not task:
            return
        dlg = TaskEditDialog(self, task=task)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            title, desc, due, completed, priority = dlg.get_data()
            # поддержка dict и tuple
            task_id = task["id"] if isinstance(task, dict) else task[0]
            ok = False
            try:
                ok = self.repo.update_task(
                    task_id,
                    title=title,
                    description=desc,
                    due_date=due,
                    completed=completed,
                    priority=priority,
                )
            except TypeError:
                # если репозиторий ожидает позиционные аргументы
                self.repo.update_task(task_id, title, desc, due, completed, priority)
                ok = True
            finally:
                if ok:
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
        self.settings.setValue("search_query", text)

    def apply_filter(self):
        mode = self.filter_combo.currentText()
        self.proxy.setMode(mode)
        self.settings.setValue("filter_mode", mode)

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
            "Программа для планирования задач\n\n© Buchenkov Igor\n\n sarovchanin@internet.ru\n\n                2025"
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

        # Показать в глобальных координатах
        global_pos = self.view.viewport().mapToGlobal(pos)
        menu.exec_(global_pos)


class FramelessWindow(QtWidgets.QWidget):
    RESIZE_MARGIN = 8  # ширина зоны захвата по краям

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.setObjectName("FramelessWindow")
        # Без системной рамки + прозрачный фон для тени
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        # Настройки окна
        self.settings = QtCore.QSettings("YourCompany", "PlanBoard")

        # Корневой кадр с тенью и скруглениями
        self.frame = QtWidgets.QFrame(self)
        self.frame.setObjectName("frameRoot")
        self.frame.setStyleSheet("QFrame#frameRoot { background: palette(base); border-radius: 10px; }")

        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setOffset(0, 8)
        shadow.setBlurRadius(24)
        shadow.setColor(QtGui.QColor(0, 0, 0, 90))
        self.frame.setGraphicsEffect(shadow)

        # Шапка (TitleBar должен быть определён в модуле)
        self.titlebar = TitleBar(self, title="Планировщик задач")

        # Контент — ваш MainWindow
        self.content = MainWindow(repo, parent=self.frame)
        self.content.setObjectName("MainWindowContent")
        # Не отдельное окно, а виджет внутри frame
        self.content.setWindowFlags(QtCore.Qt.Widget)
        self.content.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        # Синхронизация заголовка из контента (если внутри меняется windowTitle)
        try:
            self.content.windowTitleChanged.connect(self._sync_title)
        except Exception:
            pass

        # Компоновка: внешний отступ под тень и внутренняя рамка 1px
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)  # место для тени
        root.setSpacing(0)
        root.addWidget(self.frame)

        fl = QtWidgets.QVBoxLayout(self.frame)
        fl.setContentsMargins(1, 1, 1, 1)
        fl.setSpacing(0)
        fl.addWidget(self.titlebar)
        fl.addWidget(self.content, 1)

        # Грип изменения размера (правый нижний угол)
        self.size_grip = QtWidgets.QSizeGrip(self.frame)
        self.size_grip.setFixedSize(14, 14)
        corner = QtWidgets.QHBoxLayout()
        corner.setContentsMargins(0, 0, 0, 0)
        corner.addStretch(1)
        corner.addWidget(self.size_grip, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom)
        fl.addLayout(corner)

        # Восстановление геометрии и состояния
        geom = self.settings.value("window_geometry")
        if geom is not None:
            try:
                self.restoreGeometry(geom)
            except Exception:
                pass
        else:
            self.resize(1000, 700)

        win_state = int(self.settings.value("window_state", int(QtCore.Qt.WindowNoState)))
        if win_state == int(QtCore.Qt.WindowMaximized):
            self.showMaximized()

        # Применение сохранённой темы
        mode = str(self.settings.value("theme", "dark"))
        self.apply_theme(mode)

    def _sync_title(self, text: str):
        # Обновляем текст в кастомной шапке, если контент меняет windowTitle
        if hasattr(self.titlebar, "label") and isinstance(self.titlebar.label, QtWidgets.QLabel):
            self.titlebar.label.setText(text or "Планировщик задач")

    def apply_theme(self, mode: str):
        try:
            self.settings.setValue("theme", mode)  # key "theme" совпадает с MainWindow
        except Exception:
            pass

        # Два лёгких пресета темы
        dark = """
        * { outline: none; }
        QWidget { color: #e6e6e6; background: #2b2b2b; }
        QFrame#frameRoot { background: #2f2f2f; border-radius: 10px; }
        QToolButton { color: #e6e6e6; background: transparent; }
        QToolButton:hover { background: rgba(255,255,255,0.08); }
        QMenu { background: #333; color: #eee; border: 1px solid #444; }
        QMenu::item:selected { background: #444; }
        QTableView { background: #2f2f2f; gridline-color: #444; }
        QHeaderView::section { background: #3a3a3a; color: #ddd; border: 0px; padding: 6px; }
        QScrollBar:vertical { background: #2f2f2f; width: 12px; margin: 0; }
        QScrollBar::handle:vertical { background: #555; min-height: 20px; border-radius: 6px; }
        QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
        """
        light = """
        * { outline: none; }
        QWidget { color: #232323; background: #f2f2f2; }
        QFrame#frameRoot { background: palette(base); border-radius: 10px; }
        QToolButton { color: #232323; background: transparent; }
        QToolButton:hover { background: rgba(0,0,0,0.08); }
        QMenu { background: #fff; color: #222; border: 1px solid #ccc; }
        QMenu::item:selected { background: #e6e6e6; }
        QTableView { background: palette(base); gridline-color: #ccc; }
        QHeaderView::section { background: #eaeaea; color: #333; border: 0px; padding: 6px; }
        QScrollBar:vertical { background: palette(base); width: 12px; margin: 0; }
        QScrollBar::handle:vertical { background: #bbb; min-height: 20px; border-radius: 6px; }
        QScrollBar:add-line, QScrollBar:sub-line { height: 0; }
        """

        app = QtWidgets.QApplication.instance()
        if app:
            app.setStyleSheet(dark if mode == "dark" else light)

        # Небольшой стиль заголовка
        if hasattr(self.titlebar, "label") and isinstance(self.titlebar.label, QtWidgets.QLabel):
            self.titlebar.label.setStyleSheet("font-weight: 600;")

    def closeEvent(self, e: QtGui.QCloseEvent):
        # Сохраняем геометрию и состояние
        try:
            self.settings.setValue("window_geometry", self.saveGeometry())
            self.settings.setValue(
                "window_state",
                int(QtCore.Qt.WindowMaximized if self.isMaximized() else QtCore.Qt.WindowNoState)
            )
        finally:
            super().closeEvent(e)

    def changeEvent(self, e: QtCore.QEvent):
        # Фикс артефактов: при максимизации отключаем прозрачность
        if e.type() == QtCore.QEvent.WindowStateChange:
            if self.isMaximized():
                self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)
            else:
                self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        super().changeEvent(e)

    # Ресайз по всем краям/углам на Windows
    def nativeEvent(self, eventType, message):
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

            ptr_val = message.int() if hasattr(message, "int") else int(message)
            msg = MSG.from_address(ptr_val)

            if msg.message != WM_NCHITTEST or self.isMaximized():
                return False, 0

            # Координаты курсора
            pos = QtGui.QCursor.pos()
            # Геометрия видимой рамки (frameRoot) в глобальных координатах
            frame_rect = self.frame.geometry()
            frame_top_left = self.frame.mapToGlobal(QtCore.QPoint(0, 0))
            fl, ft = frame_top_left.x(), frame_top_left.y()
            fr, fb = fl + frame_rect.width() - 1, ft + frame_rect.height() - 1

            m = max(10, getattr(self, "RESIZE_MARGIN", 8))  # удобная ширина зоны

            on_left = fl <= pos.x() <= fl + m
            on_right = fr - m <= pos.x() <= fr
            on_top = ft <= pos.y() <= ft + m
            on_bottom = fb - m <= pos.y() <= fb

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

            # Резервная зона по внешней границе окна, если вдруг тень мешает
            win_rect = self.frameGeometry()
            wl, wr = win_rect.left(), win_rect.right()
            wt, wb = win_rect.top(), win_rect.bottom()

            on_left_w = wl <= pos.x() <= wl + m
            on_right_w = wr - m <= pos.x() <= wr
            on_top_w = wt <= pos.y() <= wt + m
            on_bottom_w = wb - m <= pos.y() <= wb

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


