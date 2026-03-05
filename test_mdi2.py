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
        
        # Standalone Menubar added to layout beneath toolbar
        self.mb = QMenuBar()
        self.mb.addMenu("File")
        layout.addWidget(self.mb)
        
        # We also need to set it as the main window menu bar, BUT wait!
        # If we use setMenuBar(mb), QMainWindow pulls it out of the layout and puts it at the top!
        # Let's try NOT using setMenuBar(mb) and see if MdiArea puts buttons in `mb`.
        
        self.mdi = QMdiArea()
        layout.addWidget(self.mdi)
        
        sub = QMdiSubWindow()
        sub.setWidget(QPushButton("subwindow"))
        self.mdi.addSubWindow(sub)
        
        # Let's see if buttons show up in `mb` when maximized
        sub.showMaximized()
        
        # Or does QMdiArea just not show buttons if there is no setMenuBar? 
        # By default, a maximized subwindow puts buttons in QMenuBar. If none exists on QMainWindow, it leaves them on the subwindow frame? Wait, no, it hides the subwindow frame, so buttons might disappear entirely!

app = QApplication(sys.argv)
w = MainWindow()
w.show()

# Quick test if buttons exist
from PyQt6.QtCore import QTimer

def test():
    # check if mb contains any QToolButton (which min/max controls use)
    from PyQt6.QtWidgets import QToolButton
    buttons = w.mb.findChildren(QToolButton)
    print("Action buttons in standalone menubar:", len(buttons))
    
    # Check QMainWindow menubar
    mw_mb = w.menuBar()
    print("Action buttons in mainwindow menubar:", len(mw_mb.findChildren(QToolButton)))
    
    app.quit()

QTimer.singleShot(500, test)
sys.exit(app.exec())
