
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


def _resource_bases():
    """
    Корни для поиска ресурсов:
    - sys._MEIPASS (PyInstaller)
    - папка с этим файлом (app/)
    - родительская папка (корень проекта)
    - папка с исполняемым файлом
    """
    bases = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bases.append(Path(meipass))
    this_file = Path(__file__).resolve()
    bases.append(this_file.parent)         # .../app
    bases.append(this_file.parent.parent)  # проектный корень
    try:
        exe_dir = Path(sys.executable).resolve().parent
        bases.append(exe_dir)
    except Exception:
        pass
    # уникализируем порядок
    seen = []
    for b in bases:
        if b and b not in seen:
            seen.append(b)
    return seen


def find_icon():
    """
    Ищем иконку по типичным путям.
    """
    candidates_rel = [
        Path("resources/icons/app.ico"),
        Path("resources/app.ico"),
        Path("resources/icons/app.png"),
        Path("resources/icons/app.svg"),
        Path("app/resources/icons/app.ico"),
        Path("app/resources/app.ico"),
    ]
    for base in _resource_bases():
        for rel in candidates_rel:
            p = base / rel
            if p.is_file():
                return str(p)
    return None


def main():
    # Важно для корректной иконки в таскбаре/группировки на Windows
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

    # Иконка приложения (для панели задач/заголовка окна)
    app_icon = None
    icon_path = find_icon()
    if icon_path:
        icon = QtGui.QIcon(icon_path)
        if not icon.isNull():
            app.setWindowIcon(icon)
            app_icon = icon  # держим ссылку

    init_db()
    repo = TaskRepo()
    win = FramelessWindow(repo)

    # Если окно само не выставляет иконку — выставим
    if app_icon:
        try:
            win.setWindowIcon(app_icon)
            win._app_icon = app_icon
        except Exception:
            pass

    # ВАЖНО: трей отключён — не создаём QSystemTrayIcon вообще
    # (раньше тут был код создания win.tray и .setVisible(True))

    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
