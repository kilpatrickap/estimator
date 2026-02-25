from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFrame, 
                             QTextEdit, QSplitter, QFormLayout)
from PyQt6.QtCore import Qt, pyqtSignal

class RateBuildupSummaryWidget(QWidget):
    """Encapsulates the Notes and Totals section of the Rate Build-up Dialog."""
    
    notesChanged = pyqtSignal()
    
    def __init__(self, estimate_object, parent=None):
        super().__init__(parent)
        self.estimate = estimate_object
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 0)
        
        notes_lbl = QLabel("Notes :")
        notes_lbl.setStyleSheet("font-weight: bold; color: #444;")
        layout.addWidget(notes_lbl)

        self.summary_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.summary_splitter.setHandleWidth(10)
        
        # Notes Section
        self.notes_widget = QWidget()
        notes_container = QVBoxLayout(self.notes_widget)
        notes_container.setContentsMargins(0, 0, 0, 0)
        
        self.notes_input = QTextEdit(self.estimate.notes or "")
        self.notes_input.setPlaceholderText("Enter Rate's notes here...")
        self.notes_input.setAcceptRichText(False)
        self.notes_input.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.notes_input.setStyleSheet("""
            QTextEdit { 
                border: 1px solid #c8e6c9; 
                border-radius: 6px; 
                background-color: #fffde7; 
                color: #6a1b9a; 
                padding: 10px;
            }
        """)
        self.notes_input.textChanged.connect(self._on_notes_changed)
        notes_container.addWidget(self.notes_input)
        self.notes_widget.setMinimumWidth(200) 
        
        # Totals Section
        totals_panel = QFrame()
        totals_panel.setStyleSheet("background-color: #f1f8e9; border-radius: 6px; border: 1px solid #c8e6c9;")
        totals_layout = QFormLayout(totals_panel)
        totals_layout.setContentsMargins(15, 10, 15, 10)
        totals_layout.setSpacing(8)
        
        self.summary_splitter.addWidget(self.notes_widget)
        self.summary_splitter.addWidget(totals_panel)
        self.summary_splitter.setStretchFactor(0, 1)
        self.summary_splitter.setStretchFactor(1, 1)
        
        layout.addWidget(self.summary_splitter)
        
        # Total Labels
        self.subtotal_label = QLabel("0.00")
        self.overhead_label = QLabel("0.00")
        self.profit_label = QLabel("0.00")
        self.total_label = QLabel("0.00")
        
        for lbl in [self.subtotal_label, self.overhead_label, self.profit_label, self.total_label]:
            lbl.setStyleSheet("font-family: 'Consolas', monospace; font-weight: bold; border: none;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.total_label.setStyleSheet("font-family: 'Consolas', monospace; font-weight: bold; color: #2e7d32; border: none;")
        
        self.subtotal_header_label = QLabel("Build-up Sub-Total (Sum of Net Rates):")
        totals_layout.addRow(self.subtotal_header_label, self.subtotal_label)
        
        self.overhead_header_label = QLabel(f"Overhead ({self.estimate.overhead_percent}%):")
        totals_layout.addRow(self.overhead_header_label, self.overhead_label)
        
        self.profit_header_label = QLabel(f"Profit ({self.estimate.profit_margin_percent}%):")
        totals_layout.addRow(self.profit_header_label, self.profit_label)
        
        gross_rate_header = QLabel("Gross Rate:")
        gross_rate_header.setStyleSheet("font-weight: bold;")
        totals_layout.addRow(gross_rate_header, self.total_label)
        
    def _on_notes_changed(self):
        self.estimate.notes = self.notes_input.toPlainText()
        self.notesChanged.emit()

    def update_totals(self, totals_dict, base_sym="$"):
        """Called by the main dialog when calculations change."""
        self.subtotal_label.setText(f"{base_sym}{totals_dict['subtotal']:,.2f}")
        self.overhead_label.setText(f"{base_sym}{totals_dict['overhead']:,.2f}")
        self.profit_label.setText(f"{base_sym}{totals_dict['profit']:,.2f}")
        self.total_label.setText(f"{base_sym}{totals_dict['grand_total']:,.2f}")
        
    def refresh_ui(self):
        """Called by parent when the estimate object might have been entirely replaced (e.g. undo/redo)"""
        # Block signals to prevent infinite loop of un-doing typing
        self.notes_input.blockSignals(True)
        self.notes_input.setText(self.estimate.notes or "")
        self.notes_input.blockSignals(False)
        
        self.overhead_header_label.setText(f"Overhead ({self.estimate.overhead_percent}%):")
        self.profit_header_label.setText(f"Profit ({self.estimate.profit_margin_percent}%):")
