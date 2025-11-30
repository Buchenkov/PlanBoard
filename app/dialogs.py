# Диалог добавления/редактирования задачи.

from PyQt5 import QtWidgets, QtCore, QtGui


class HelpDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, settings: QtCore.QSettings = None):
        super().__init__(parent)
        self.setWindowTitle("Справка — PlanBoard")
        self.resize(600, 400)

        self.settings = settings

        self.browser = QtWidgets.QTextBrowser(self)
        self.browser.setOpenExternalLinks(True)
        self.browser.setReadOnly(True)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok, parent=self)
        btns.accepted.connect(self.accept)

        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(self.browser)
        lay.addWidget(btns)

        if self.settings is not None:
            geom = self.settings.value("help_dialog_geometry")
            if geom:
                try:
                    self.restoreGeometry(geom)
                except Exception:
                    pass

    def set_help_text(self, text: str, is_html: bool = False):
        if is_html:
            self.browser.setHtml(text)
        else:
            self.browser.setPlainText(text)

    def accept(self):
        if self.settings is not None:
            try:
                self.settings.setValue("help_dialog_geometry", self.saveGeometry())
            except Exception:
                pass
        super().accept()

class TaskEditDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, task=None):
        super().__init__(parent)
        # Убираем кнопку "?" в заголовке
        flags = self.windowFlags()
        flags &= ~QtCore.Qt.WindowContextHelpButtonHint
        self.setWindowFlags(flags)

        self.setWindowTitle("Задача")
        self.setModal(True)
        self.task = task

        # Поля формы
        self.title_edit = QtWidgets.QLineEdit()
        self.desc_edit = QtWidgets.QPlainTextEdit()

        self.due_edit = QtWidgets.QDateEdit(calendarPopup=True)
        self.due_edit.setDisplayFormat("yyyy-MM-dd")
        self.due_edit.setDate(QtCore.QDate.currentDate())

        self.priority_spin = QtWidgets.QSpinBox()
        self.priority_spin.setRange(0, 10)

        self.completed_chk = QtWidgets.QCheckBox("Выполнено")

        # Компоновка
        form = QtWidgets.QFormLayout()
        form.addRow("Название:", self.title_edit)
        form.addRow("Описание:", self.desc_edit)
        form.addRow("Срок:", self.due_edit)
        form.addRow("Приоритет:", self.priority_spin)
        form.addRow("", self.completed_chk)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(btns)
        self.resize(420, 320)

        if task:
            self._load_task(task)

    def _load_task(self, task):
        # Поддержка dict и tuple
        if isinstance(task, dict):
            title = task.get("title", "")
            desc = task.get("description", "")
            due_str = task.get("due_date") or ""
            completed = bool(task.get("completed", 0))
            try:
                priority = int(task.get("priority") or 0)
            except Exception:
                priority = 0
        else:
            # (id, title, description, due_date, created_at, completed, priority)
            try:
                _, title, desc, due_str, _, completed, priority = task
            except Exception:
                title, desc, due_str, completed, priority = "", "", "", 0, 0
            try:
                priority = int(priority or 0)
            except Exception:
                priority = 0
            completed = bool(completed)

        self.title_edit.setText(title or "")
        self.desc_edit.setPlainText(desc or "")

        # Установка даты
        if due_str:
            qd = QtCore.QDate.fromString(str(due_str), "yyyy-MM-dd")
            if qd.isValid():
                self.due_edit.setDate(qd)
            else:
                self.due_edit.setDate(QtCore.QDate.currentDate())
        else:
            self.due_edit.setDate(QtCore.QDate.currentDate())

        self.priority_spin.setValue(priority)
        self.completed_chk.setChecked(bool(completed))

    def get_data(self):
        title = self.title_edit.text().strip()
        desc = self.desc_edit.toPlainText().strip()
        due = self.due_edit.date().toString("yyyy-MM-dd")
        priority = int(self.priority_spin.value())
        completed = self.completed_chk.isChecked()
        return title, desc, due, completed, priority

# Алиас для совместимости со старым импортом
TaskDialog = TaskEditDialog
