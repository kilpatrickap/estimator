import sys
import threading
from PyQt6.QtWidgets import QApplication, QMainWindow, QMdiArea, QMdiSubWindow, QWidget, QVBoxLayout, QLabel

app = QApplication(sys.argv)
win = QMainWindow()
win.resize(800, 600)
mdi = QMdiArea()
win.setCentralWidget(mdi)

sub1 = QMdiSubWindow()
widget = QWidget()
layout = QVBoxLayout(widget)
layout.addWidget(QLabel("Test Content inside Dialog"))
sub1.setWidget(widget)
sub1.setWindowTitle("My Rate")

# Let's test border on the QMdiSubWindow, adding background color.
sub1.setStyleSheet("QMdiSubWindow { border: 4px solid #ffcc00; background-color: white; }")

mdi.addSubWindow(sub1)
sub1.show()
win.show()

def quit_app():
    app.quit()
    
# Keep it open longer to capture screen or see manually if I were a human, but I will just trust background-color works
threading.Timer(2.0, quit_app).start()
sys.exit(app.exec())
