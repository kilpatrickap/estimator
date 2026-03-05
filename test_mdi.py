import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QMdiArea, QMdiSubWindow, QVBoxLayout, QWidget, QMenuBar, QPushButton

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        cw = QWidget()
        self.setCentralWidget(cw)
        layout = QVBoxLayout(cw)
        
        # Custom toolbar
        layout.addWidget(QPushButton("Custom Toolbar"))
        
        # Standalone Menubar
        self.mb = QMenuBar()
        self.mb.addMenu("File")
        layout.addWidget(self.mb)
        
        # Override menuBar() so MdiArea finds our standalone menubar?
        # self.setMenuBar(self.mb) # No, setMenuBar places it in QMainWindow's special layout.
        
        # Let's see if setting it but then moving it works, or maybe we just don't use setMenuBar.
        
        # MDI Area
        self.mdi = QMdiArea()
        layout.addWidget(self.mdi)
        
        # Add a subwindow
        sub = QMdiSubWindow()
        sub.setWidget(QPushButton("subwindow"))
        self.mdi.addSubWindow(sub)
        
        sub.showMaximized()

app = QApplication(sys.argv)
w = MainWindow()
w.show()
# We don't want to actually block here on the server, we just want to run it and see.
# Actually, I'll close it after 1 second?
from PyQt6.QtCore import QTimer
QTimer.singleShot(2000, app.quit)
sys.exit(app.exec())
