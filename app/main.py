
import sys
import os
from PyQt5 import QtGui, QtCore, QtWidgets
from app.db import init_db
from app.repo import TaskRepo
from app.views import FramelessWindow
from app.theme import enable_dark_theme, enable_light_theme


def ensure_qt_plugins():
    """Опционально: настройка путей к плагинам Qt (обычно не требуется для PyInstaller)."""
    try:
        plugins = QtCore.QLibraryInfo.location(QtCore.QLibraryInfo.PluginsPath)
        binpath = QtCore.QLibraryInfo.location(QtCore.QLibraryInfo.BinariesPath)

        if not plugins:
            import site
            sp = next(p for p in site.getsitepackages() if p.endswith("site-packages"))
            qtbase = os.path.join(sp, "PyQt5", "Qt5")
            plugins = os.path.join(qtbase, "plugins")
            binpath = os.path.join(qtbase, "bin")

        if plugins and os.path.isdir(plugins):
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugins
            QtCore.QCoreApplication.addLibraryPath(plugins)
        if binpath and os.path.isdir(binpath):
            os.environ["PATH"] = binpath + os.pathsep + os.environ.get("PATH", "")
    except Exception as e:
        print("Qt plugin path setup warning:", e)


def main():
    # Инициализация БД (создаст таблицы при первом запуске)
    init_db()

    app = QtWidgets.QApplication(sys.argv)

    # Применяем тему из настроек (по умолчанию — тёмная)
    settings = QtCore.QSettings("YourCompany", "PlanBoard")
    theme = settings.value("theme", "dark")
    if theme == "dark":
        enable_dark_theme(app)
    else:
        enable_light_theme(app)

    repo = TaskRepo()
    w = FramelessWindow(repo)
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
