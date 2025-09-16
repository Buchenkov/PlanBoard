# Диалог добавления/редактирования задачи.

from PyQt5 import QtWidgets, QtCore, QtGui
import datetime

class TaskDialog(QtWidgets.QDialog):
    def init(self, parent=None, task=None):
        super().init(parent)
        self.setWindowTitle("Задача")
        self.task = task

        self.title_edit = QtWidgets.QLineEdit()
        self.desc_edit = QtWidgets.QPlainTextEdit()
        self.due_edit = QtWidgets.QDateEdit(calendarPopup=True)
        self.due_edit.setDisplayFormat("yyyy-MM-dd")
        self.due_edit.setDate(QtCore.QDate.currentDate())
        self.priority_spin = QtWidgets.QSpinBox()
        self.priority_spin.setRange(0, 10)
        self.completed_chk = QtWidgets.QCheckBox("Выполнено")

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

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(btns)
        self.setLayout(layout)
        self.resize(400, 300)

        if task:
            self._load_task(task)

    def _load_task(self, task):
        task_id, title, desc, due, created, completed, priority = task
        self.title_edit.setText(title or "")
        self.desc_edit.setPlainText(desc or "")
        try:
            y, m, d = [int(x) for x in (due or "").split("-")]
            self.due_edit.setDate(QtCore.QDate(y, m, d))
        except Exception:
            self.due_edit.setDate(QtCore.QDate.currentDate())
        self.priority_spin.setValue(int(priority or 0))
        self.completed_chk.setChecked(bool(completed))

    def get_data(self):
        title = self.title_edit.text().strip()
        desc = self.desc_edit.toPlainText().strip()
        due = self.due_edit.date().toString("yyyy-MM-dd")
        priority = int(self.priority_spin.value())
        completed = self.completed_chk.isChecked()
        return title, desc, due, completed, priority