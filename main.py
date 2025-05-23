from PyQt5 import QtWidgets
import sys
from ui import Ui_MainWindow

class Main(QtWidgets.QMainWindow):
    def __init__(self):
        super(Main, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

def App():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    win = Main()
    win.showMaximized()
    sys.exit(app.exec_())

App()