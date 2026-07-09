"""
Resources Schedule (RS) Dialog — Interactive PyQt6 viewer for the aggregated
Resources Schedule. Displays Materials, Labor, Equipment, and Plant in tabbed
tables with sorting, filtering, and summary statistics.

Launched from the main window's Project menu.
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QLineEdit, QComboBox,
    QWidget, QMessageBox, QProgressDialog, QApplication, QFrame,
    QFileDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QBrush

from rs_generator import RSGenerator, RSResult


# ─── Colour Palette (matches app theme) ──────────────────────────────────────

COLOR_HEADER_BG = QColor("#1b5e20")
COLOR_HEADER_FG = QColor("#ffffff")
COLOR_MATERIAL = QColor("#f3e5f5")       # Light purple
COLOR_LABOR = QColor("#e3f2fd")          # Light blue
COLOR_EQUIPMENT = QColor("#fff9c4")      # Light yellow
COLOR_PLANT = QColor("#e8f5e9")          # Light green
COLOR_SUMMARY_BG = QColor("#fafafa")
COLOR_ALT_ROW = QColor("#f5f7f9")
COLOR_ACCENT = QColor("#2e7d32")
COLOR_SKIPPED = QColor("#ffebee")        # Light red


class RSDialog(QDialog):
    """Resources Schedule viewer dialog."""

    def __init__(self, pboq_db_path, project_dir, parent=None, scope='all', selected_rowids=None):
        super().__init__(parent)
        self.pboq_db_path = pboq_db_path
        self.project_dir = project_dir
        self.scope = scope
        self.selected_rowids = selected_rowids
        self.result = None   # RSResult

        self.setWindowTitle("Resources Schedule")
        self.setMinimumSize(1050, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._init_ui()

        # Generate data after the UI is shown
        QTimer.singleShot(100, self._generate)

    # ── UI Setup ──────────────────────────────────────────────────────────

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        # ── Top Toolbar ───────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        # Title
        title = QLabel("📋 Resources Schedule")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #2e7d32;")
        toolbar.addWidget(title)

        toolbar.addStretch()

        # Search
        search_label = QLabel("Search:")
        search_label.setStyleSheet("font-size: 9pt;")
        toolbar.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by resource name...")
        self.search_input.setFixedWidth(220)
        self.search_input.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.search_input)

        # Refresh
        refresh_btn = QPushButton("⟳ Refresh")
        refresh_btn.setFixedWidth(90)
        refresh_btn.setToolTip("Regenerate the Resources Schedule")
        refresh_btn.clicked.connect(self._generate)
        toolbar.addWidget(refresh_btn)

        # Export Excel
        self.export_btn = QPushButton("📊 Export Excel")
        self.export_btn.setFixedWidth(110)
        self.export_btn.setToolTip("Export Resources Schedule to Excel")
        self.export_btn.clicked.connect(self._export_excel)
        self.export_btn.setEnabled(False)
        toolbar.addWidget(self.export_btn)

        layout.addLayout(toolbar)

        # ── Summary Cards ─────────────────────────────────────────────────
        self.summary_frame = QFrame()
        self.summary_frame.setObjectName("RSSummaryFrame")
        self.summary_frame.setStyleSheet("""
            QFrame#RSSummaryFrame {
                background-color: #f5f7f9;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        summary_layout = QHBoxLayout(self.summary_frame)
        summary_layout.setContentsMargins(10, 6, 10, 6)
        summary_layout.setSpacing(20)

        self.summary_labels = {}
        for key, label_text, color in [
            ('materials', 'Materials', '#7B1FA2'),
            ('labor', 'Labour', '#1565C0'),
            ('equipment', 'Equipment', '#F57F17'),
            ('plant', 'Plant', '#2E7D32'),
            ('grand', 'Grand Total', '#333333'),
        ]:
            card = QVBoxLayout()
            card.setSpacing(1)

            name_lbl = QLabel(label_text)
            name_lbl.setStyleSheet(f"color: {color}; font-size: 9pt; font-weight: bold;")
            card.addWidget(name_lbl)

            val_lbl = QLabel("—")
            val_lbl.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")
            val_lbl.setObjectName(f"RSValue_{key}")
            card.addWidget(val_lbl)
            self.summary_labels[key] = val_lbl

            summary_layout.addLayout(card)

        summary_layout.addStretch()
        layout.addWidget(self.summary_frame)

        # ── Tab Widget ────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        layout.addWidget(self.tabs, 1)

        # Create tabs
        self.mat_table = self._create_resource_table()
        self.lab_table = self._create_resource_table()
        self.eqp_table = self._create_resource_table()
        self.plt_table = self._create_resource_table()
        self.skip_table = self._create_skipped_table()

        self.tabs.addTab(self.mat_table, "🧱 Materials")
        self.tabs.addTab(self.lab_table, "👷 Labour")
        self.tabs.addTab(self.eqp_table, "⚙ Equipment")
        self.tabs.addTab(self.plt_table, "🏗 Plant")
        self.tabs.addTab(self.skip_table, "⚠ Skipped Items")

        # ── Status Bar ────────────────────────────────────────────────────
        self.status_label = QLabel("Ready. Generating...")
        self.status_label.setStyleSheet("color: #777; font-size: 8pt; margin-top: 4px;")
        layout.addWidget(self.status_label)

    def _create_resource_table(self):
        """Creates a QTableWidget configured for resource display."""
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels([
            "#", "Resource Name", "Unit", "Total Qty",
            "Avg. Unit Rate", "Total Cost", "Used In (Rate Codes)"
        ])
        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget { 
                gridline-color: #e0e0e0; 
                font-size: 9pt;
                alternate-background-color: #f9fafb;
            }
            QTableWidget::item:selected {
                background-color: #e8f5e9;
                color: #2e7d32;
            }
        """)
        table.setSortingEnabled(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)

        header = table.horizontalHeader()
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #1b5e20;
                color: white;
                font-weight: bold;
                padding: 4px 6px;
                border: none;
                border-right: 1px solid #2e7d32;
                font-size: 9pt;
            }
        """)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        table.setColumnWidth(0, 40)
        table.setColumnWidth(2, 70)
        table.setColumnWidth(3, 110)
        table.setColumnWidth(4, 110)
        table.setColumnWidth(5, 130)

        return table

    def _create_skipped_table(self):
        """Creates a QTableWidget for skipped (unbroken-down) items."""
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels([
            "#", "Description", "Reason", "Bill Amount"
        ])
        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget { 
                gridline-color: #e0e0e0; 
                font-size: 9pt;
                alternate-background-color: #fff3f3;
            }
        """)
        table.setSortingEnabled(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)

        header = table.horizontalHeader()
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #c62828;
                color: white;
                font-weight: bold;
                padding: 4px 6px;
                border: none;
                border-right: 1px solid #d32f2f;
                font-size: 9pt;
            }
        """)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)

        table.setColumnWidth(0, 40)
        table.setColumnWidth(2, 200)
        table.setColumnWidth(3, 130)

        return table

    # ── Data Generation ───────────────────────────────────────────────────

    def _generate(self):
        """Runs the RS generator and populates the tables."""
        self.status_label.setText("Generating Resources Schedule...")
        QApplication.processEvents()

        try:
            generator = RSGenerator(self.pboq_db_path, self.project_dir)
            self.result = generator.generate(
                scope=self.scope,
                selected_rowids=self.selected_rowids
            )

            self._populate_table(self.mat_table, self.result.materials, COLOR_MATERIAL)
            self._populate_table(self.lab_table, self.result.labor, COLOR_LABOR)
            self._populate_table(self.eqp_table, self.result.equipment, COLOR_EQUIPMENT)
            self._populate_table(self.plt_table, self.result.plant, COLOR_PLANT)
            self._populate_skipped_table()
            self._update_summary()

            # Update tab labels with counts
            self.tabs.setTabText(0, f"🧱 Materials ({len(self.result.materials)})")
            self.tabs.setTabText(1, f"👷 Labour ({len(self.result.labor)})")
            self.tabs.setTabText(2, f"⚙ Equipment ({len(self.result.equipment)})")
            self.tabs.setTabText(3, f"🏗 Plant ({len(self.result.plant)})")
            self.tabs.setTabText(4, f"⚠ Skipped ({len(self.result.skipped_rows)})")

            total = (len(self.result.materials) + len(self.result.labor) +
                     len(self.result.equipment) + len(self.result.plant))
            self.status_label.setText(
                f"Generated: {total} unique resources across "
                f"{len(self.result.materials)}M / {len(self.result.labor)}L / "
                f"{len(self.result.equipment)}E / {len(self.result.plant)}P  |  "
                f"{len(self.result.skipped_rows)} skipped rows"
            )
            self.export_btn.setEnabled(True)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_label.setText(f"Error: {e}")
            QMessageBox.warning(self, "RS Generation Error", str(e))

    # ── Table Population ──────────────────────────────────────────────────

    def _populate_table(self, table, entries, row_color):
        """Fills a resource table with RSResourceEntry items."""
        table.setSortingEnabled(False)
        table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            # #
            num_item = QTableWidgetItem()
            num_item.setData(Qt.ItemDataRole.DisplayRole, row + 1)
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 0, num_item)

            # Resource Name
            name_item = QTableWidgetItem(entry.name)
            name_item.setBackground(row_color)
            table.setItem(row, 1, name_item)

            # Unit
            unit_item = QTableWidgetItem(entry.unit)
            unit_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 2, unit_item)

            # Total Qty
            qty_item = QTableWidgetItem()
            qty_item.setData(Qt.ItemDataRole.DisplayRole, round(entry.total_qty, 4))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, 3, qty_item)

            # Unit Rate (weighted average)
            rate_item = QTableWidgetItem()
            rate_item.setData(Qt.ItemDataRole.DisplayRole, round(entry.unit_rate, 2))
            rate_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, 4, rate_item)

            # Total Cost
            cost_item = QTableWidgetItem()
            cost_item.setData(Qt.ItemDataRole.DisplayRole, round(entry.total_cost, 2))
            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cost_font = QFont()
            cost_font.setBold(True)
            cost_item.setFont(cost_font)
            table.setItem(row, 5, cost_item)

            # Used In (Rate Codes)
            codes = ", ".join(sorted(entry.used_in_codes))
            codes_item = QTableWidgetItem(codes)
            codes_item.setForeground(QColor("#777777"))
            codes_item.setToolTip(codes)
            table.setItem(row, 6, codes_item)

        table.setSortingEnabled(True)

    def _populate_skipped_table(self):
        """Fills the skipped items table."""
        table = self.skip_table
        skipped = self.result.skipped_rows if self.result else []

        table.setSortingEnabled(False)
        table.setRowCount(len(skipped))

        for row, item in enumerate(skipped):
            num_item = QTableWidgetItem()
            num_item.setData(Qt.ItemDataRole.DisplayRole, row + 1)
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 0, num_item)

            desc_item = QTableWidgetItem(item.description)
            table.setItem(row, 1, desc_item)

            reason_item = QTableWidgetItem(item.reason)
            reason_item.setForeground(QColor("#c62828"))
            table.setItem(row, 2, reason_item)

            amt_item = QTableWidgetItem()
            amt_item.setData(Qt.ItemDataRole.DisplayRole, round(item.bill_amount, 2))
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, 3, amt_item)

        table.setSortingEnabled(True)

    def _update_summary(self):
        """Updates the summary cards at the top."""
        if not self.result:
            return
        s = self.result.summary
        currency = ""

        # Detect currency from first available entry
        for entries in [self.result.materials, self.result.labor,
                        self.result.equipment, self.result.plant]:
            if entries:
                currency = entries[0].currency
                break

        def fmt(val):
            return f"{val:,.2f}"

        self.summary_labels['materials'].setText(
            f"{fmt(s['materials_total'])}  ({s['materials_count']} items)")
        self.summary_labels['labor'].setText(
            f"{fmt(s['labor_total'])}  ({s['labor_count']} items)")
        self.summary_labels['equipment'].setText(
            f"{fmt(s['equipment_total'])}  ({s['equipment_count']} items)")
        self.summary_labels['plant'].setText(
            f"{fmt(s['plant_total'])}  ({s['plant_count']} items)")
        self.summary_labels['grand'].setText(
            f"{currency}  {fmt(s['grand_total'])}")

    # ── Search Filter ─────────────────────────────────────────────────────

    def _apply_filter(self, text):
        """Filters the currently active table by resource name."""
        current_tab = self.tabs.currentIndex()
        tables = [self.mat_table, self.lab_table, self.eqp_table, self.plt_table, self.skip_table]
        if current_tab >= len(tables):
            return

        table = tables[current_tab]
        search_text = text.lower().strip()
        name_col = 1  # Resource name is always in column 1

        for row in range(table.rowCount()):
            item = table.item(row, name_col)
            if item:
                match = search_text in item.text().lower() if search_text else True
                table.setRowHidden(row, not match)
            else:
                table.setRowHidden(row, bool(search_text))

    # ── Excel Export ──────────────────────────────────────────────────────

    def _export_excel(self):
        """Exports the RS to an Excel file using rs_export."""
        if not self.result:
            QMessageBox.warning(self, "No Data", "Generate the Resources Schedule first.")
            return

        try:
            from rs_export import RSExcelExporter
        except ImportError:
            QMessageBox.warning(self, "Export Error", "rs_export module not found.")
            return

        # Default filename
        db_name = os.path.splitext(os.path.basename(self.pboq_db_path))[0]
        default_name = f"{db_name}_Resources_Schedule.xlsx"
        default_path = os.path.join(os.path.dirname(self.pboq_db_path), default_name)

        output_path, _ = QFileDialog.getSaveFileName(
            self, "Export Resources Schedule", default_path,
            "Excel Files (*.xlsx);;All Files (*)"
        )
        if not output_path:
            return

        try:
            exporter = RSExcelExporter(self.result)
            success, message = exporter.export(output_path)
            if success:
                QMessageBox.information(self, "Export Complete", message)
            else:
                QMessageBox.warning(self, "Export Failed", message)
        except Exception as e:
            QMessageBox.warning(self, "Export Error", f"Export failed: {e}")
