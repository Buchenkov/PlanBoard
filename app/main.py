import sys
from PyQt5 import QtWidgets, QtCore
from app.db import init_db
from app.repo import TaskRepo
from app.views import MainWindow


def ensure_qt_plugins():
    try:
        # Узнаём, где PyQt5 держит плагины и бинарники Qt
        plugins = QtCore.QLibraryInfo.location(QtCore.QLibraryInfo.PluginsPath)
        binpath = QtCore.QLibraryInfo.location(QtCore.QLibraryInfo.BinariesPath)

        # Подстрахуемся на случай пустых значений и колёс с Qt5
        if not plugins:
            import site, os
            sp = next(p for p in site.getsitepackages() if p.endswith("site-packages"))
            qtbase = os.path.join(sp, "PyQt5", "Qt5")
            plugins = os.path.join(qtbase, "plugins")
            binpath = os.path.join(qtbase, "bin")

        # Пропишем пути для текущего процесса
        if plugins and os.path.isdir(plugins):
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugins
            QtCore.QCoreApplication.addLibraryPath(plugins)
        if binpath and os.path.isdir(binpath):
            os.environ["PATH"] = binpath + os.pathsep + os.environ.get("PATH", "")

    except Exception as e:
        print("Qt plugin path setup warning:", e)

def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    repo = TaskRepo()
    w = MainWindow(repo)
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()