import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QMdiArea, QMdiSubWindow, QVBoxLayout, QWidget, QMenuBar, QPushButton

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        cw = QWidget()
        self.setCentralWidget(cw)
        layout = QVBoxLayout(cw)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Custom File/Edit/View Menu Bar
        # This one is standalone, not QMainWindow.menuBar()
        custom_mb = QMenuBar()
        custom_mb.addMenu("File")
        custom_mb.addMenu("Edit")
        custom_mb.addMenu("Window")
        custom_mb.addMenu("View")
        layout.addWidget(custom_mb)
        
        # 2. Custom Toolbar (Top Navigation Bar)
        layout.addWidget(QPushButton("Custom Toolbar"))
        
        # 3. Ribbon toggle button
        layout.addWidget(QPushButton("Ribbon"))
        
        # 4. Actual QMainWindow menu bar for MDI controls
        # We put it into the layout here, underneath the ribbon
        real_mb = self.menuBar()
        layout.addWidget(real_mb)
        # Wait, if real_mb has no menus, will it be hidden?
        # Let's see if MDI area puts buttons there and makes it visible.
        
        # 5. MDI Area
        self.mdi = QMdiArea()
        layout.addWidget(self.mdi)
        
        sub = QMdiSubWindow()
        sub.setWidget(QPushButton("subwindow"))
        self.mdi.addSubWindow(sub)
        
        sub.showMaximized()

app = QApplication(sys.argv)
w = MainWindow()
w.show()

from PyQt6.QtCore import QTimer
QTimer.singleShot(2000, app.quit)
sys.exit(app.exec())
