import sys
from PyQt5 import QtGui, QtCore, QtWidgets
from app.db import init_db
from app.repo import TaskRepo
from app.views import MainWindow
from app.theme import enable_dark_theme, enable_light_theme


def enable_dark_theme(app):
    QtWidgets.QApplication.setStyle("Fusion")
    palette = QtGui.QPalette()
    base = QtGui.QColor(45, 45, 45)
    alt_base = QtGui.QColor(53, 53, 53)
    window = QtGui.QColor(53, 53, 53)
    text = QtGui.QColor(220, 220, 220)
    disabled_text = QtGui.QColor(128, 128, 128)
    button = QtGui.QColor(53, 53, 53)
    highlight = QtGui.QColor(42, 130, 218)

    palette.setColor(QtGui.QPalette.Window, window)
    palette.setColor(QtGui.QPalette.WindowText, text)
    palette.setColor(QtGui.QPalette.Base, base)
    palette.setColor(QtGui.QPalette.AlternateBase, alt_base)
    palette.setColor(QtGui.QPalette.ToolTipBase, text)
    palette.setColor(QtGui.QPalette.ToolTipText, text)
    palette.setColor(QtGui.QPalette.Text, text)
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Text, disabled_text)
    palette.setColor(QtGui.QPalette.Button, button)
    palette.setColor(QtGui.QPalette.ButtonText, text)
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText, disabled_text)
    palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    palette.setColor(QtGui.QPalette.Link, highlight)
    palette.setColor(QtGui.QPalette.Highlight, highlight)
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255))
    app.setPalette(palette)

    # Небольшие штрихи для таблиц (контраст сетки/selection)
    app.setStyleSheet("""
        QTableView { gridline-color: #404040; selection-background-color: #2a82da; selection-color: white; }
        QHeaderView::section { background-color: #3b3b3b; color: #e0e0e0; padding: 4px; border: 0px; border-right: 1px solid #505050; }
        QToolTip { color: #e0e0e0; background-color: #2d2d2d; border: 1px solid #5a5a5a; }
    """)

def enable_light_theme(app):
    # Сбрасываем на стандартную светлую палитру
    QtWidgets.QApplication.setStyle("Fusion")
    app.setPalette(app.style().standardPalette())
    app.setStyleSheet("")


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
    settings = QtCore.QSettings("YourCompany", "PlanBoard")
    theme = settings.value("theme", "dark")  # по умолчанию тёмная
    if theme == "dark":
        enable_dark_theme(app)
    else:
        enable_light_theme(app)
    repo = TaskRepo()
    w = MainWindow(repo)
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()