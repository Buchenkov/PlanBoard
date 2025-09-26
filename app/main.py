import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from app.db import init_db
from app.repo import TaskRepo
from app.views import FramelessWindow


def main():
    init_db()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    repo = TaskRepo()
    w = FramelessWindow(repo)
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()