import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QMdiArea, QMdiSubWindow, QVBoxLayout, QWidget, QMenuBar, QPushButton, QToolButton
from PyQt6.QtCore import QTimer

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        cw = QWidget()
        self.setCentralWidget(cw)
        layout = QVBoxLayout(cw)
        
        # Custom toolbar
        layout.addWidget(QPushButton("Custom Toolbar"))
        
        # Take the main window's menubar and put it in layout!
        mb = self.menuBar()
        mb.addMenu("File")
        layout.addWidget(mb)
        
        self.mdi = QMdiArea()
        layout.addWidget(self.mdi)
        
        sub = QMdiSubWindow()
        sub.setWidget(QPushButton("subwindow"))
        self.mdi.addSubWindow(sub)
        
        sub.showMaximized()

app = QApplication(sys.argv)
w = MainWindow()
w.show()
QTimer.singleShot(2000, app.quit)
sys.exit(app.exec())
