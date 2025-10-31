import sys
import ctypes
from pathlib import Path
from PyQt5 import QtWidgets, QtCore, QtGui
from app.db import init_db
from app.repo import TaskRepo
from app.views import FramelessWindow
from app.theme import enable_dark_theme, enable_light_theme

# Включаем HiDPI ДО создания QApplication
QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)


def set_win_appusermodel_id(appid: str) -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
    except Exception:
        pass


def find_icon():
    # Пробуем несколько типичных путей относительно корня проекта (где папка app/)
    base = Path(__file__).resolve().parent.parent
    candidates = [
        base / "resources" / "app.ico",
        base / "resources" / "icons" / "app.ico",
        base / "resources" / "icons" / "app.png",
        base / "resources" / "icons" / "app.svg",
        base / "app" / "resources" / "app.ico",
        base / "app" / "resources" / "icons" / "app.ico",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def main():
    set_win_appusermodel_id("YourCompany.PlanBoard")

    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    # Тема
    settings = QtCore.QSettings("YourCompany", "PlanBoard")
    theme = settings.value("theme", "dark")
    try:
        if theme == "dark":
            enable_dark_theme(app)
        else:
            enable_light_theme(app)
    except Exception:
        pass

    # Попытка установить иконку приложения (если файл найден)
    icon_path = find_icon()
    if icon_path:
        icon = QtGui.QIcon(icon_path)
        if not icon.isNull():
            app.setWindowIcon(icon)

    init_db()
    repo = TaskRepo()
    win = FramelessWindow(repo)

    # Если FramelessWindow сам не устанавливает иконку — ставим её здесь
    if icon_path:
        try:
            win.setWindowIcon(QtGui.QIcon(icon_path))
        except Exception:
            pass

    # Трей-иконка: сохраняем как атрибут окна, чтобы GC её не собрал
    if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
        try:
            win.tray = QtWidgets.QSystemTrayIcon(win)
            tray_icon = win.windowIcon()
            if tray_icon.isNull():
                tray_icon = app.windowIcon()
            win.tray.setIcon(tray_icon)
            win.tray.setVisible(True)
        except Exception:
            pass

    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
