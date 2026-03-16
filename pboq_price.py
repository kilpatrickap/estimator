from PyQt6.QtWidgets import QWidget, QVBoxLayout

class PBOQPricePane(QWidget):
    """A blank Price Tools pane for PBOQ viewer."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        # Blank for now
        layout.addStretch()
