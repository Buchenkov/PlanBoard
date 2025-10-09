import sys, os
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets, QtSvg
import datetime

from app.models import TaskTableModel
from app.dialogs import TaskDialog
from app.theme import enable_dark_theme, enable_light_theme


try:
    from PyQt5 import QtSvg  # noqa: F401
except Exception:
    pass

def resource_path(rel_path: str) -> str:
    """
    Универсальный путь к ресурсам: работает и в dev, и в PyInstaller.
    Предполагается структура: app/ (этот файл) и app/resources/...
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        base_path = Path(base)
    else:
        # views.py лежит в app/, поднимаемся в корень проекта, затем добавляем относительный путь
        base_path = Path(__file__).resolve().parent.parent
    return str((base_path / rel_path).resolve())


class FilterProxy(QtCore.QSortFilterProxyModel):
    def __init__(self, source_model=None, parent=None):
        super().__init__(parent)
        self._model = source_model
        self.mode = "Все"
        # Поиск регистронезависимый
        self.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        # Автообновление при изменении данных/сортировки
        self.setDynamicSortFilter(True)
        if source_model is not None:
            super().setSourceModel(source_model)

    def setSourceModel(self, model):
        super().setSourceModel(model)
        self._model = model

    def setMode(self, mode: str):
        if self.mode != mode:
            self.mode = mode
            self.invalidateFilter()

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Vertical:
            if role == QtCore.Qt.DisplayRole:
                return str(section + 1)
            if role == QtCore.Qt.TextAlignmentRole:
                return int(QtCore.Qt.AlignCenter)
        return super().headerData(section, orientation, role)

    def filterAcceptsRow(self, source_row, parent):
        # 1) Строковый фильтр (поиск)
        if not super().filterAcceptsRow(source_row, parent):
            return False

        # 2) Фильтр по режиму
        try:
            rows = getattr(self._model, "rows", None)
            if rows is None or source_row < 0 or source_row >= len(rows):
                return True
            r = rows[source_row]
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
            due_date = datetime.date.fromisoformat(due) if due else None
        except Exception:
            due_date = None

        today = datetime.date.today()
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
    
 
class TitleBar(QtWidgets.QWidget):
    height_hint = 36

    def __init__(self, parent=None, title="Планировщик задач"):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self._pressed = False
        self._start_pos = None
        self._icon_paths = {}

        # Кнопки управления окном
        self.btn_min = QtWidgets.QToolButton(self); self.btn_min.setObjectName("BtnMin")
        self.btn_max = QtWidgets.QToolButton(self); self.btn_max.setObjectName("BtnMax")
        self.btn_close = QtWidgets.QToolButton(self); self.btn_close.setObjectName("BtnClose")
        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
            b.setCursor(QtCore.Qt.ArrowCursor)
            b.setAutoRaise(True)

        # Fallback-текст
        self.btn_min.setText("–")
        self.btn_max.setText("□")
        self.btn_close.setText("×")

        # Заголовок
        self.label = QtWidgets.QLabel(title, self)
        self.label.setObjectName("TitleText")
        self.label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)

        # Компоновка
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 6, 0)
        lay.setSpacing(6)
        lay.addWidget(self.label, 1)
        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_max)
        lay.addWidget(self.btn_close)

        # Сигналы
        self.btn_min.clicked.connect(self._on_minimize)
        self.btn_max.clicked.connect(self._on_max_restore)
        self.btn_close.clicked.connect(self._on_close)

        # Стили и иконки
        self._apply_style()
        self._apply_icons()

    def _apply_style(self):
        self.setMinimumHeight(self.height_hint)
        self.setMaximumHeight(self.height_hint)
        self.setStyleSheet("""
            QWidget#TitleBar { background: transparent; }
            QLabel#TitleText { color: palette(windowText); font-weight: 600; }
            QToolButton#BtnMin, QToolButton#BtnMax, QToolButton#BtnClose {
                padding: 4px; border-radius: 4px; color: palette(buttonText);
            }
            QToolButton#BtnMin:hover, QToolButton#BtnMax:hover {
                background: rgba(128,128,128,0.25);
            }
            QToolButton#BtnClose:hover {
                background: rgba(255,0,0,0.25);
            }
        """)

    def _apply_icons(self):
        # Одинаковый размер иконок
        icon_size = QtCore.QSize(18, 18)
        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setIconSize(icon_size)

        # Пути к иконкам
        p_min = resource_path("app/resources/icons/minimize.svg")
        p_max = resource_path("app/resources/icons/maximize.svg")
        p_res = resource_path("app/resources/icons/restore.svg")
        p_close = resource_path("app/resources/icons/close.svg")

        def set_icon_safe(btn: QtWidgets.QToolButton, path: str, fallback: QtWidgets.QStyle.StandardPixmap):
            if os.path.isfile(path):
                btn.setIcon(QtGui.QIcon(path))
                btn.setText("")
            else:
                btn.setIcon(self.style().standardIcon(fallback))

        set_icon_safe(self.btn_min, p_min, QtWidgets.QStyle.SP_TitleBarMinButton)
        set_icon_safe(self.btn_close, p_close, QtWidgets.QStyle.SP_TitleBarCloseButton)

        # max/restore — по текущему состоянию окна
        if self.window() and self.window().isMaximized() and os.path.isfile(p_res):
            self.btn_max.setIcon(QtGui.QIcon(p_res)); self.btn_max.setText("")
        elif os.path.isfile(p_max):
            self.btn_max.setIcon(QtGui.QIcon(p_max)); self.btn_max.setText("")
        else:
            self.btn_max.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarMaxButton))

        self._icon_paths = {"maximize": p_max, "restore": p_res}

    def _window(self):
        return self.window()

    def _on_minimize(self):
        w = self._window()
        if w:
            w.showMinimized()

    def _on_max_restore(self):
        w = self._window()
        if not w:
            return
        if w.isMaximized():
            w.showNormal()
            p = self._icon_paths.get("maximize", "")
            if os.path.isfile(p):
                self.btn_max.setIcon(QtGui.QIcon(p)); self.btn_max.setText("")
            else:
                self.btn_max.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarMaxButton))
                self.btn_max.setText("")
        else:
            w.showMaximized()
            p = self._icon_paths.get("restore", "")
            if os.path.isfile(p):
                self.btn_max.setIcon(QtGui.QIcon(p)); self.btn_max.setText("")
            else:
                self.btn_max.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarNormalButton))
                self.btn_max.setText("")

    def _on_close(self):
        w = self._window()
        if w:
            w.close()

    # Перетаскивание окна
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
    Делегат для переноса длинных строк по ширине колонки
    (включая последовательности без пробелов).
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
        # Перенос по границе слов или где угодно (лучше, чем WrapAnywhere)
        topt.setWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        doc.setDefaultTextOption(topt)

        # Используем HTML, чтобы корректно отрисовать цвет и сохранить явные переносы
        import html
        safe = html.escape(text or "").replace("\n", "<br/>")
        color = option.palette.highlightedText().color() if selected else option.palette.text().color()
        doc.setHtml(f'<div style="color:{color.name()}; white-space:pre-wrap;">{safe}</div>')

        doc.setTextWidth(max(10, width))
        return doc

    def sizeHint(self, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        # Берём текст напрямую из модели (opt.text иногда пуст)
        text = str(index.data(QtCore.Qt.DisplayRole) or "")
        col_w = max(10, self.view.columnWidth(index.column()) - self.h_margin)
        doc = self._make_doc(opt, text, col_w, selected=bool(opt.state & QtWidgets.QStyle.State_Selected))
        szf = doc.documentLayout().documentSize()
        return QtCore.QSize(col_w + self.h_margin, int(szf.height()) + self.v_margin)

    def paint(self, painter, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.textElideMode = QtCore.Qt.ElideNone

        # Рисуем стандартный фон/selection без текста
        text = str(index.data(QtCore.Qt.DisplayRole) or "")
        opt_text_backup = opt.text
        opt.text = ""
        style = opt.widget.style() if opt.widget else QtWidgets.QApplication.style()
        style.drawControl(QtWidgets.QStyle.CE_ItemViewItem, opt, painter, opt.widget)
        opt.text = opt_text_backup

        # Подготовка документа
        rect = opt.rect.adjusted(self.h_margin // 2, self.v_margin // 2, -self.h_margin // 2, -self.v_margin // 2)
        doc = self._make_doc(opt, text, max(10, rect.width()), selected=bool(opt.state & QtWidgets.QStyle.State_Selected))

        painter.save()
        painter.translate(rect.topLeft())
        clip = QtCore.QRectF(0, 0, rect.width(), rect.height())
        doc.drawContents(painter, clip)
        painter.restore()

        # Фокусная рамка
        if opt.state & QtWidgets.QStyle.State_HasFocus:
            opt_focus = QtWidgets.QStyleOptionFocusRect()
            opt_focus.rect = opt.rect
            opt_focus.state = QtWidgets.QStyle.State_KeyboardFocusChange | QtWidgets.QStyle.State_Item
            opt_focus.backgroundColor = opt.palette.highlight().color()
            style.drawPrimitive(QtWidgets.QStyle.PE_FrameFocusRect, opt_focus, painter, opt.widget)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("Планировщик задач")
        self.resize(1000, 700)

        # QSettings
        self.settings = QtCore.QSettings("YourCompany", "PlanBoard")

        # Флаги старта/восстановления
        self._restoring_header = False
        self._startup_ignore_changes = True

        # ===== Действия =====
        self.add_act = QtWidgets.QAction("Добавить", self)
        self.edit_act = QtWidgets.QAction("Редактировать", self)
        self.del_act = QtWidgets.QAction("Удалить", self)
        self.refresh_act = QtWidgets.QAction("Обновить", self)
        self.act_help = QtWidgets.QAction("Справка", self)
        self.act_about = QtWidgets.QAction("О программе", self)

        self.act_help.setShortcut("F1")
        self.add_act.setShortcut("F2")
        self.edit_act.setShortcut("F3")
        self.del_act.setShortcut("Delete")
        self.refresh_act.setShortcut("F5")

        self.add_act.triggered.connect(self.add_task)
        self.edit_act.triggered.connect(self.edit_task)
        self.del_act.triggered.connect(self.delete_task)
        self.refresh_act.triggered.connect(self.refresh)
        self.act_help.triggered.connect(self.show_help)
        self.act_about.triggered.connect(self.show_about)

        # Тема приложения
        self.act_dark = QtWidgets.QAction("Тёмная тема", self)
        self.act_dark.setCheckable(True)
        cur_theme = str(self.settings.value("theme", "dark"))
        self.act_dark.setChecked(cur_theme == "dark")
        self.act_dark.toggled.connect(self.on_toggle_theme)

        # ===== Модель и прокси =====
        self.model = TaskTableModel(repo, self)
        self.proxy = FilterProxy(self.model, self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.proxy.setDynamicSortFilter(True)

        # ===== Вид (таблица) =====
        self.view = QtWidgets.QTableView()
        self.view.setObjectName("MainView")
        self.view.setModel(self.proxy)
        self.view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.view.setSortingEnabled(True)
        self.view.setWordWrap(True)
        self.view.setTextElideMode(QtCore.Qt.ElideNone)
        self.view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu)
        self.view.doubleClicked.connect(lambda idx: self.edit_task())

        # Заголовки
        hdr = self.view.horizontalHeader()
        hdr.setSectionsMovable(True)
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)

        vhdr = self.view.verticalHeader()
        vhdr.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        vhdr.setDefaultAlignment(QtCore.Qt.AlignCenter)

        # Делегат для "Описание" (если такая колонка есть)
        self.desc_col = getattr(self.model, "column_index", lambda k: -1)("description")
        if isinstance(self.desc_col, int) and self.desc_col >= 0:
            self.view.setItemDelegateForColumn(self.desc_col, WrapDelegate(self.view, self))

        # Верхняя панель (поиск + фильтр)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по названию...")
        self.search_edit.textChanged.connect(self.apply_search)

        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.addItems(["Все", "Открытые", "Просроченные", "На сегодня", "Выполненные"])
        self.filter_combo.currentIndexChanged.connect(self.apply_filter)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.search_edit)
        top.addWidget(self.filter_combo)

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.addLayout(top)
        layout.addWidget(self.view)
        self.setCentralWidget(central)

        # Тулбар
        toolbar = self.findChild(QtWidgets.QToolBar, "Main")
        if toolbar is None:
            toolbar = self.addToolBar("Main")
            toolbar.setObjectName("Main")
        toolbar.setMovable(True)
        toolbar.setFloatable(True)
        toolbar.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        toolbar.clear()

        self.menu_btn = QtWidgets.QToolButton(self)
        self.menu_btn.setText("Меню   ")
        self.menu_btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.menu_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        self.main_menu = QtWidgets.QMenu(self.menu_btn)
        self.main_menu.addAction(self.add_act)
        self.main_menu.addAction(self.edit_act)
        self.main_menu.addAction(self.del_act)
        self.main_menu.addSeparator()
        self.main_menu.addAction(self.refresh_act)
        self.main_menu.addSeparator()

        # Подменю "Столбцы"
        self.columns_menu = self.main_menu.addMenu("Столбцы")
        self._column_actions = {}

        self.main_menu.addSeparator()
        self.main_menu.addAction(self.act_help)
        self.main_menu.addSeparator()
        self.main_menu.addAction(self.act_about)

        self.menu_btn.setMenu(self.main_menu)
        toolbar.addWidget(self.menu_btn)
        toolbar.addSeparator()
        toolbar.addAction(self.act_dark)

        # Сигналы сохранения состояния:
        # - порядок и сортировка — единым saveState
        hdr.sectionMoved.connect(self._save_header_state)
        hdr.sortIndicatorChanged.connect(lambda *_: self._save_header_state())
        # - ширина конкретной колонки — отдельные ключи
        hdr.sectionResized.connect(self._on_section_resized_user)

        # Построение меню столбцов (видимость сохраняем отдельно по колонкам)
        self._rebuild_columns_menu()

        # Загрузка данных
        self.model.load()

        # Дефолтная сортировка (если нет сохранённой)
        try:
            col_due = getattr(self.model, "column_index", lambda k: 1)("due_date")
            if not isinstance(col_due, int) or col_due < 0:
                col_due = 1
            self.view.sortByColumn(col_due, QtCore.Qt.AscendingOrder)
            hdr.setSortIndicator(col_due, QtCore.Qt.AscendingOrder)
            hdr.setSortIndicatorShown(True)
        except Exception:
            pass

        # Поиск/фильтр — восстановление
        last_query = self.settings.value("search_query", "")
        self.search_edit.setText(str(last_query))
        last_filter = str(self.settings.value("filter_mode", "Все"))
        ix = self.filter_combo.findText(last_filter)
        if ix >= 0:
            self.filter_combo.setCurrentIndex(ix)
        self.apply_search(self.search_edit.text())
        self.apply_filter()

        # Пересчёт высоты строк
        self.view.resizeRowsToContents()

        # Применение темы
        app = QtWidgets.QApplication.instance()
        if app:
            try:
                if cur_theme == "dark":
                    enable_dark_theme(app)
                else:
                    enable_light_theme(app)
            except Exception:
                pass

        # Отложенное восстановление: порядок/сортировка из saveState, затем ширины и видимость
        QtCore.QTimer.singleShot(0, self._initial_restore)

    # ===== Восстановление состояния таблицы =====
    def _initial_restore(self):
        # 1) Порядок и сортировка
        try:
            self._restoring_header = True
            state = self.settings.value("table_header_state/MainView", type=QtCore.QByteArray)
            if isinstance(state, QtCore.QByteArray) and not state.isEmpty():
                self.view.horizontalHeader().restoreState(state)
        except Exception:
            pass
        finally:
            self._restoring_header = False

        # 2) Видимость и ширины по колонкам
        self._restore_columns_user_prefs()

        # 3) После небольшой задержки начнём сохранять изменения пользователя
        QtCore.QTimer.singleShot(400, lambda: setattr(self, "_startup_ignore_changes", False))

        # Синхронизируем меню "Столбцы"
        self._sync_column_checks()

    def _restore_columns_user_prefs(self):
        try:
            hdr = self.view.horizontalHeader()
            cols = self.view.model().columnCount()
            group = "table_header_state/MainView"
            for c in range(cols):
                vis = self.settings.value(f"{group}/vis_{c}", None)
                if vis is not None:
                    vis_norm = bool(vis) if isinstance(vis, bool) else str(vis).lower() in ("1", "true", "t", "yes", "y")
                    hdr.setSectionHidden(c, not vis_norm)
                w = self.settings.value(f"{group}/width_{c}", None)
                if w is not None:
                    try:
                        w_int = int(w)
                        if w_int > 0:
                            hdr.resizeSection(c, w_int)
                    except Exception:
                        pass
        except Exception:
            pass

    # ===== Сохранение =====
    def _save_header_state(self):
        if self._restoring_header or self._startup_ignore_changes:
            return
        try:
            hdr = self.view.horizontalHeader()
            state = hdr.saveState()
            self.settings.setValue("table_header_state/MainView", state)
            self.settings.sync()
        except Exception:
            pass

    def _on_section_resized_user(self, logicalIndex, oldSize, newSize):
        if self._restoring_header or self._startup_ignore_changes:
            return
        try:
            group = "table_header_state/MainView"
            self.settings.setValue(f"{group}/width_{logicalIndex}", int(newSize))
            self.settings.sync()
        except Exception:
            pass
        try:
            if isinstance(self.desc_col, int) and self.desc_col >= 0 and logicalIndex == self.desc_col:
                self.view.resizeRowsToContents()
        except Exception:
            pass

    # ===== Поиск/фильтр/обновление =====
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

    # ===== Действия с задачами =====
    def selected_task(self):
        idx = self.view.currentIndex()
        if not idx.isValid():
            return None
        src = self.proxy.mapToSource(idx)
        row = src.row()
        return self.model.rows[row] if 0 <= row < len(self.model.rows) else None

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

    # ===== Контекстное меню таблицы =====
    def show_context_menu(self, pos):
        index = self.view.indexAt(pos)
        has_sel = index.isValid()
        if has_sel:
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

        menu.addSeparator()
        if self.columns_menu is not None:
            self._sync_column_checks()
            menu.addMenu(self.columns_menu)

        if has_sel:
            task = self.selected_task()
            completed = bool(task.get("completed") if isinstance(task, dict) else task[5])
            toggle_text = "Отметить выполненной" if not completed else "Снять отметку выполнения"

            def toggle_completed():
                task_id = task["id"] if isinstance(task, dict) else task[0]
                title = task.get("title") if isinstance(task, dict) else task[1]
                desc = task.get("description") if isinstance(task, dict) else task[2]
                due = task.get("due_date") if isinstance(task, dict) else task[3]
                priority = task.get("priority") if isinstance(task, dict) else task[6]
                self.repo.update_task(task_id, title, desc, due, not completed, priority)
                self.refresh()

            menu.addSeparator()
            menu.addAction(toggle_text, toggle_completed)

        menu.addSeparator()
        menu.addAction("Обновить", self.refresh)

        global_pos = self.view.viewport().mapToGlobal(pos)
        menu.exec_(global_pos)

    # ===== Меню "Столбцы" =====
    def _rebuild_columns_menu(self):
        self.columns_menu.clear()
        hdr = self.view.horizontalHeader()
        self._column_actions = {}

        cols = self.view.model().columnCount()
        group = "table_header_state/MainView"

        for col in range(cols):
            name = self.model.headerData(col, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole)
            text = str(name or f"Колонка {col + 1}")

            vis_val = self.settings.value(f"{group}/vis_{col}", None)
            if vis_val is None:
                is_visible = not hdr.isSectionHidden(col)
            else:
                is_visible = bool(vis_val) if isinstance(vis_val, bool) else str(vis_val).lower() in ("1", "true", "t", "yes", "y")

            act = QtWidgets.QAction(text, self, checkable=True)
            act.setChecked(is_visible)

            def on_toggled(checked, c=col):
                if self._restoring_header or self._startup_ignore_changes:
                    return
                try:
                    hdr.setSectionHidden(c, not checked)
                    self.settings.setValue(f"{group}/vis_{c}", bool(checked))
                    self.settings.sync()
                except Exception:
                    pass
                self._sync_column_checks()
                self._save_header_state()

            act.toggled.connect(on_toggled)
            self.columns_menu.addAction(act)
            self._column_actions[col] = act

        self.columns_menu.aboutToShow.connect(self._sync_column_checks)
    def _sync_column_checks(self):
        hdr = self.view.horizontalHeader()
        group = "table_header_state/MainView"
        for col, act in list(self._column_actions.items()):
            vis_val = self.settings.value(f"{group}/vis_{col}", None)
            if vis_val is None:
                vis = not hdr.isSectionHidden(col)
            else:
                vis = bool(vis_val) if isinstance(vis_val, bool) else str(vis_val).lower() in ("1", "true", "t", "yes", "y")
            act.blockSignals(True)
            act.setChecked(vis)
            act.blockSignals(False)

    # ===== Тема =====
    def on_toggle_theme(self, checked):
        app = QtWidgets.QApplication.instance()
        if not app:
            return
        try:
            if checked:
                enable_dark_theme(app)
                self.settings.setValue("theme", "dark")
            else:
                enable_light_theme(app)
                self.settings.setValue("theme", "light")
        except Exception:
            pass

    # ===== Служебное =====
    def closeEvent(self, e):
        try:
            self._save_header_state()
            try:
                self.settings.setValue("win/geometry", self.saveGeometry())
                self.settings.sync()
            except Exception:
                pass
        finally:
            super().closeEvent(e)

    def show_about(self):
        QtWidgets.QMessageBox.about(
            self,
            "О программе",
            "PlanBoard\n\n"
            "Простой планировщик задач.\n"
            "Функционал:\n"

            "- Создание, изменение и удаление задач (CRUD)\n"

            "- Возможность сортировки по любому столбцу (при клике на заголовок)\n"

            "- Встроенная строка поиска для быстрого нахождения задач по названию\n"

            "- Применение фильтров для более точного отбора информации\n"

            "- Изменение статуса задачи через контекстное меню\n"

            "- Настройка отображения столбцов (выбор, скрытие, сохранение порядка и ширины)\n"

            "- Поддержка тем оформления: светлая и тёмная (выбор сохраняется)\n"
            "Версия: 1.2.0\n"
            "Автор: Бученков Игорь"
        )

    def show_help(self):
        text = (
            "Справка\n\n"
            "PlanBoard — простой планировщик задач. Используйте поиск и фильтры "
            "для быстрого нахождения задач. Двойной клик — редактирование.\n\n"
            "Горячие клавиши:\n"
            "  F1 — Открыть справку\n"
            "  F2 — Добавить задачу\n"
            "  F3 — Редактировать выбранную\n"
            "  Delete — Удалить выбранную\n"
            "  F5 — Обновить список\n"
        )
        QtWidgets.QMessageBox.information(self, "Справка", text)


class FramelessWindow(QtWidgets.QWidget):
    RESIZE_MARGIN = 8

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.setObjectName("FramelessWindow")
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        # Настройки
        self.settings = QtCore.QSettings("YourCompany", "PlanBoard")

        # Внешняя рамка
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

        # Шапка
        self.titlebar = TitleBar(self, title="Планировщик задач")

        # Контент
        self.content = MainWindow(repo, parent=self.frame)
        self.content.setWindowFlags(QtCore.Qt.Widget)
        self.content.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        # Компоновка
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)  # отступ под тень
        root.setSpacing(0)
        root.addWidget(self.frame)

        content_layout = QtWidgets.QVBoxLayout(self.frame)
        content_layout.setContentsMargins(1, 1, 1, 1)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.titlebar)
        content_layout.addWidget(self.content, 1)

        # QSizeGrip
        self.size_grip = QtWidgets.QSizeGrip(self.frame)
        self.size_grip.setFixedSize(14, 14)
        corner = QtWidgets.QHBoxLayout()
        corner.setContentsMargins(0, 0, 0, 0)
        corner.addStretch(1)
        corner.addWidget(self.size_grip, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom)
        content_layout.addLayout(corner)

        # Двойной клик по шапке — max/restore
        self.titlebar.mouseDoubleClickEvent = self._titlebar_double_click

        # Последняя "нормальная" геометрия (не максимизированное окно)
        self._last_normal_geom = None

        # Восстановим после того, как виджет будет показан (даёт более стабильный результат с Frameless)
        QtCore.QTimer.singleShot(0, self._restore_window_state)

        # Сохранение при выходе
        app = QtWidgets.QApplication.instance()
        if app is not None:
            try:
                app.aboutToQuit.disconnect(self._save_window_state)
            except Exception:
                pass
            app.aboutToQuit.connect(self._save_window_state)

        self._geom_save_timer = QtCore.QTimer(self)
        self._geom_save_timer.setSingleShot(True)
        self._geom_save_timer.setInterval(400)
        self._geom_save_timer.timeout.connect(self._save_window_geometry)

    def _save_window_geometry(self):
        try:
            self.settings.setValue("win/geometry", self.saveGeometry())
            self.settings.sync()
        except Exception:
            pass

    def _restore_window_geometry(self):
        try:
            ba = self.settings.value("win/geometry", type=QtCore.QByteArray)
            ok = False
            if isinstance(ba, QtCore.QByteArray) and not ba.isEmpty():
                ok = self.restoreGeometry(ba)
        except Exception:
            pass

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # отложенно сохраним геометрию, чтобы не писать на каждый пиксель
        if self.isWindow():
            self._geom_save_timer.start()

    def moveEvent(self, e):
        super().moveEvent(e)
        if self.isWindow():
            self._geom_save_timer.start()


    def _titlebar_double_click(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()

    # Запомним нормальную геометрию при изменении состояния
    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.WindowStateChange:
            if not self.isMaximized() and not self.isMinimized():
                self._last_normal_geom = self.geometry()
        super().changeEvent(event)

    def moveEvent(self, event):
        # Обновлять нормальную геометрию в процессе перемещения в нормальном состоянии
        if not self.isMaximized() and not self.isMinimized():
            self._last_normal_geom = self.geometry()
        super().moveEvent(event)

    def resizeEvent(self, event):
        # Обновлять нормальную геометрию при изменении размера в нормальном состоянии
        if not self.isMaximized() and not self.isMinimized():
            self._last_normal_geom = self.geometry()
        super().resizeEvent(event)

    def _restore_window_state(self):
        # Состояние (максимизировано или нет)
        win_state = self.settings.value("window_state", int(QtCore.Qt.WindowNoState))
        try:
            win_state = int(win_state)
        except Exception:
            win_state = int(QtCore.Qt.WindowNoState)

        # Геометрия (последняя нормальная)
        geom_bytes = self.settings.value("window_geometry", None)
        rect = None
        if isinstance(geom_bytes, QtCore.QByteArray) and not geom_bytes.isEmpty():
            # Попытка через restoreGeometry — иногда с Frameless требуется сначала showNormal
            try:
                self.restoreGeometry(geom_bytes)
                self._last_normal_geom = self.geometry()
            except Exception:
                pass

        # Если restoreGeometry не дал результата, попробуем прямой QRect
        if self._last_normal_geom is None:
            rect = self.settings.value("window_rect", None)
            if isinstance(rect, QtCore.QRect):
                self.setGeometry(rect)
                self._last_normal_geom = rect

        # Если нет сохранённой геометрии — центрируем на экране
        if self._last_normal_geom is None:
            screen = QtWidgets.QApplication.primaryScreen()
            ag = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1280, 800)
            w, h = 900, 550
            x = ag.x() + (ag.width() - w) // 2
            y = ag.y() + (ag.height() - h) // 2
            self.setGeometry(x, y, w, h)
            self._last_normal_geom = self.geometry()

        # Применим состояние окна
        if win_state == int(QtCore.Qt.WindowMaximized):
            self.showMaximized()
        else:
            self.showNormal()

        # Безопасность: если окно оказалось вне экрана (смена мониторов/масштаба) — подвинем внутрь
        self._ensure_inside_available_area()

    def _ensure_inside_available_area(self):
        screen = QtWidgets.QApplication.screenAt(self.frameGeometry().center())
        ag = screen.availableGeometry() if screen else QtWidgets.QApplication.primaryScreen().availableGeometry()
        r = self.geometry()
        new_r = QtCore.QRect(r)
        if r.right() < ag.left() or r.left() > ag.right() or r.bottom() < ag.top() or r.top() > ag.bottom():
            # Полностью вне экрана — центрируем
            w, h = r.width(), r.height()
            x = ag.x() + (ag.width() - w) // 2
            y = ag.y() + (ag.height() - h) // 2
            new_r = QtCore.QRect(x, y, w, h)
        else:
            # Корректируем частично выходящую геометрию
            if new_r.left() < ag.left():
                new_r.moveLeft(ag.left())
            if new_r.top() < ag.top():
                new_r.moveTop(ag.top())
            if new_r.right() > ag.right():
                new_r.moveRight(ag.right())
            if new_r.bottom() > ag.bottom():
                new_r.moveBottom(ag.bottom())
        if new_r != r:
            self.setGeometry(new_r)
            self._last_normal_geom = new_r

    def _save_window_state(self):
        try:
            # Сохраняем QByteArray от saveGeometry — универсально
            self.settings.setValue("window_geometry", self.saveGeometry())
            # Плюс дубль в виде QRect для надёжности (особенно при Frameless)
            normal_rect = self._last_normal_geom if self._last_normal_geom else self.geometry()
            self.settings.setValue("window_rect", normal_rect)
            # Состояние
            self.settings.setValue(
                "window_state",
                int(QtCore.Qt.WindowMaximized if self.isMaximized() else QtCore.Qt.WindowNoState)
            )
        except Exception:
            pass

    def closeEvent(self, e):
        try:
            self._save_window_state()
        finally:
            super().closeEvent(e)

    # Windows: расширенный хит-тест по видимой рамке (удобный ресайз за все края/углы)
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

            if msg.message != WM_NCHITTEST:
                return False, 0
            if self.isMaximized():
                return False, 0

            # Позиция курсора
            pos = QtGui.QCursor.pos()
            x, y = pos.x(), pos.y()

            # Внешний прямоугольник окна
            win_rect = self.frameGeometry()
            wl, wr = win_rect.left(), win_rect.right()
            wt, wb = win_rect.top(), win_rect.bottom()

            # Видимая рамка (frameRoot)
            frame_rect = self.frame.geometry()
            frame_top_left = self.frame.mapToGlobal(QtCore.QPoint(0, 0))
            fl, ft = frame_top_left.x(), frame_top_left.y()
            fr, fb = fl + frame_rect.width() - 1, ft + frame_rect.height() - 1

            m = max(10, getattr(self, "RESIZE_MARGIN", 8))

            # По видимой рамке
            on_left = fl <= x <= fl + m
            on_right = fr - m <= x <= fr
            on_top = ft <= y <= ft + m
            on_bottom = fb - m <= y <= fb

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

            # Резерв: у самого края окна
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
