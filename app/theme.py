from PyQt5 import QtWidgets, QtGui, QtCore

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

    app.setStyleSheet("""
        QTableView { gridline-color: #404040; selection-background-color: #2a82da; selection-color: white; }
        QHeaderView::section { background-color: #3b3b3b; color: #e0e0e0; padding: 4px; border: 0px; border-right: 1px solid #505050; }
        QToolTip { color: #e0e0e0; background-color: #2d2d2d; border: 1px solid #5a5a5a; }
    """)

def enable_light_theme(app):
    QtWidgets.QApplication.setStyle("Fusion")
    app.setPalette(app.style().standardPalette())
    app.setStyleSheet("")