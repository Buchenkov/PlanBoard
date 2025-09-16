import sys
from PyQt5 import QtWidgets
from app.db import init_db
from app.repo import TaskRepo
from app.views import MainWindow

def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    repo = TaskRepo()
    w = MainWindow(repo)
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()