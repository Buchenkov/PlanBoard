import sys
from PyQt5 import QtWidgets, QtCore
from app.db import init_db
from app.repo import TaskRepo
from app.views import FramelessWindow
from app.theme import enable_dark_theme, enable_light_theme

def main():
    app = QtWidgets.QApplication(sys.argv)

    # Читаем тему из настроек и применяем до создания окна
    settings = QtCore.QSettings("YourCompany", "PlanBoard")
    theme = str(settings.value("theme", "dark"))
    if theme == "dark":
        enable_dark_theme(app)
    else:
        enable_light_theme(app)

    init_db()
    repo = TaskRepo()
    win = FramelessWindow(repo)  # важно: именно FramelessWindow
    win.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
