import os
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, QTableWidgetItem,
    QLabel, QComboBox, QPushButton, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QMessageBox, QInputDialog, QMenu, QFormLayout, QTabWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

class BOQSetupWindow(QWidget):
    """Parses Excel BOQs, allows mapping, and formats them into an Estimate struct."""
    def __init__(self, boq_file_path, active_est_window, parent=None):
        super().__init__(parent)
        self.boq_file_path = boq_file_path
        self.active_est_window = active_est_window
        
        # Dictionary to store dataframe and row types per sheet name
        self.sheet_data = {} 
        self.active_sheet = None
        
        # Color codes for visual feedback
        self.COLOR_HEADING = QColor("#e8f5e9") # Light green
        self.COLOR_ITEM = QColor("#ffffff")    # White
        self.COLOR_IGNORE = QColor("#ffebee")  # Light red

        self.setWindowTitle(f"BOQ Setup - {os.path.basename(boq_file_path)}")
        self._init_ui()
        self._load_excel()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # LEFT PANE: Raw Excel View with Tabs
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("Raw BOQ Data (from Excel):"))
        
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        left_layout.addWidget(self.tabs)
        
        # RIGHT PANE: Mapping and Preview
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        mapping_form = QFormLayout()
        
        self.cb_ref = QComboBox()
        self.cb_desc = QComboBox()
        self.cb_qty = QComboBox()
        self.cb_unit = QComboBox()
        self.cb_rate = QComboBox()
        
        mapping_form.addRow("Ref / Item No Column:", self.cb_ref)
        mapping_form.addRow("Description Column:", self.cb_desc)
        mapping_form.addRow("Quantity Column:", self.cb_qty)
        mapping_form.addRow("Unit Column:", self.cb_unit)
        mapping_form.addRow("Rate Column (Optional):", self.cb_rate)
        
        apply_map_btn = QPushButton("Apply Mapping to All Sheets")
        apply_map_btn.clicked.connect(self._apply_mapping)
        
        right_layout.addLayout(mapping_form)
        right_layout.addWidget(apply_map_btn)
        
        right_layout.addWidget(QLabel("Formatted Preview:"))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Sheet", "Ref", "Description", "Quantity", "Unit", "Type"])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tree.header().setStretchLastSection(True)
        right_layout.addWidget(self.tree)
        
        import_btn = QPushButton("Import to Estimate Tasks")
        import_btn.setMinimumHeight(50)
        import_btn.setStyleSheet("background-color: #1976D2; color: white; font-weight: bold;")
        import_btn.clicked.connect(self._import_to_estimate)
        right_layout.addWidget(import_btn)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)
        
        main_layout.addWidget(splitter)

    def _load_excel(self):
        try:
            xl = pd.ExcelFile(self.boq_file_path)
            sheet_names = xl.sheet_names
            
            # Basic parsing of cell styles for bold detection (auto headings)
            is_xlsx = self.boq_file_path.lower().endswith('.xlsx')
            
            wb = None
            if is_xlsx:
                import openpyxl
                try:
                    wb = openpyxl.load_workbook(self.boq_file_path, data_only=True)
                except: pass
            else:
                import xlrd
                try:
                    wb = xlrd.open_workbook(self.boq_file_path, formatting_info=True)
                except: pass
                
            for sheet_name in sheet_names:
                df = xl.parse(sheet_name, header=None)
                df.fillna("", inplace=True)
                row_types = ['ignore'] * len(df)
                
                table = QTableWidget()
                table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
                table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
                table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                table.customContextMenuRequested.connect(self._show_context_menu)
                # Word wrap to handle long descriptions
                table.setWordWrap(True)
                
                table.setRowCount(len(df))
                table.setColumnCount(len(df.columns))
                
                columns = [f"Column {i}" for i in range(len(df.columns))]
                table.setHorizontalHeaderLabels(columns)
                
                ws = None
                if wb and is_xlsx and sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                elif wb and not is_xlsx:
                    try:
                        ws = wb.sheet_by_name(sheet_name)
                    except: pass
                    
                bold_font = QFont()
                bold_font.setBold(True)
                
                for r in range(len(df)):
                    row_is_bold = False
                    for c in range(len(df.columns)):
                        val = str(df.iloc[r, c])
                        item = QTableWidgetItem(val)
                        
                        # Preserve simple formatting (Bold check)
                        is_bold = False
                        if ws and is_xlsx:
                            try:
                                cell = ws.cell(row=r+1, column=c+1)
                                if cell.font and cell.font.bold: is_bold = True
                            except: pass
                        elif ws and not is_xlsx:
                            try:
                                xf_idx = ws.cell_xf_index(r, c)
                                xf = wb.xf_list[xf_idx]
                                font = wb.font_list[xf.font_index]
                                if font.weight >= 700: is_bold = True   # 700 is typically bold in xlrd
                            except: pass
                            
                        if is_bold:
                            item.setFont(bold_font)
                            # If the cell has text and is bold, we might guess this row is a heading
                            if val.strip():
                                row_is_bold = True
                                
                        item.setBackground(self.COLOR_IGNORE)
                        table.setItem(r, c, item)
                        
                    # Auto guess: if major cell in row was bold, default it to heading initially
                    if row_is_bold:
                        row_types[r] = 'heading'
                        for c in range(len(df.columns)):
                            if table.item(r, c): 
                                table.item(r, c).setBackground(self.COLOR_HEADING)
                # Set a good reasonable column width for description (assume col 1 or 2)
                if len(df.columns) > 2:
                    table.setColumnWidth(1, 350)
                    table.setColumnWidth(2, 350)
                
                # Resize rows to fit wrapped content based on new column widths
                table.resizeRowsToContents()
                # Automatically resize row height as user resizes columns/modifies layout
                table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
                
                self.sheet_data[sheet_name] = {
                    'df': df,
                    'row_types': row_types,
                    'table': table,
                    'columns': columns
                }
                self.tabs.addTab(table, sheet_name)

            if sheet_names:
                self.active_sheet = sheet_names[0]
                self._populate_comboboxes(self.sheet_data[self.active_sheet]['columns'])

        except Exception as e:
            QMessageBox.critical(self, "Excel Error", f"Failed to load BOQ Excel file.\nError: {e}")

    def _on_tab_changed(self, index):
        sheet_name = self.tabs.tabText(index)
        self.active_sheet = sheet_name
        
    def _populate_comboboxes(self, columns):
        for cb in [self.cb_ref, self.cb_desc, self.cb_qty, self.cb_unit, self.cb_rate]:
            cb.clear()
            cb.addItem("-- Select Column --")
            cb.addItems(columns)
        
        if len(columns) > 1: self.cb_ref.setCurrentIndex(1)
        if len(columns) > 2: self.cb_desc.setCurrentIndex(2)
        if len(columns) > 3: self.cb_qty.setCurrentIndex(3)
        if len(columns) > 4: self.cb_unit.setCurrentIndex(4)

    def _show_context_menu(self, pos):
        if not self.active_sheet: return
        data = self.sheet_data[self.active_sheet]
        table = data['table']
        
        menu = QMenu()
        set_heading_action = menu.addAction("Set row(s) as Heading")
        set_item_action = menu.addAction("Set row(s) as Item")
        set_ignore_action = menu.addAction("Set row(s) to Ignore")
        
        action = menu.exec(table.mapToGlobal(pos))
        if not action: return
        
        rows = list(set([idx.row() for idx in table.selectedIndexes()]))
        
        for r in rows:
            if action == set_heading_action:
                data['row_types'][r] = 'heading'
                self._update_row_color(table, r, self.COLOR_HEADING)
            elif action == set_item_action:
                data['row_types'][r] = 'item'
                self._update_row_color(table, r, self.COLOR_ITEM)
            elif action == set_ignore_action:
                data['row_types'][r] = 'ignore'
                self._update_row_color(table, r, self.COLOR_IGNORE)
        
        self._build_tree_preview()

    def _update_row_color(self, table, row, color):
        for c in range(table.columnCount()):
            item = table.item(row, c)
            if item:
                item.setBackground(color)

    def _apply_mapping(self):
        """Auto detects Headings vs Items based on columns across ALL sheets based on selected columns."""
        desc_col = self.cb_desc.currentIndex() - 1
        qty_col = self.cb_qty.currentIndex() - 1
        
        if desc_col < 0:
            QMessageBox.warning(self, "Mapping Error", "You must at least select a Description column.")
            return

        for sheet_name, data in self.sheet_data.items():
            df = data['df']
            table = data['table']
            
            for r in range(len(df)):
                desc_val = str(df.iloc[r, desc_col]).strip() if desc_col < len(df.columns) else ""
                qty_val = str(df.iloc[r, qty_col]).strip() if qty_col >= 0 and qty_col < len(df.columns) else ""
                
                # We skip overriding if the user manually set it, but for simplicity we'll override if ignore
                # Actually, let's keep existing headings derived from bold font if they exist.
                if not desc_val:
                    data['row_types'][r] = 'ignore'
                    self._update_row_color(table, r, self.COLOR_IGNORE)
                    continue
                    
                # If it has a description but no quantity, and it wasn't already mapped, assume Heading
                if desc_val and not qty_val:
                    data['row_types'][r] = 'heading'
                    self._update_row_color(table, r, self.COLOR_HEADING)
                elif desc_val and qty_val:
                    data['row_types'][r] = 'item'
                    self._update_row_color(table, r, self.COLOR_ITEM)

        self._build_tree_preview()

    def _build_tree_preview(self):
        self.tree.clear()
        
        ref_col = self.cb_ref.currentIndex() - 1
        desc_col = self.cb_desc.currentIndex() - 1
        qty_col = self.cb_qty.currentIndex() - 1
        unit_col = self.cb_unit.currentIndex() - 1
        
        bold_font = QFont()
        bold_font.setBold(True)
        
        for sheet_name, data in self.sheet_data.items():
            df = data['df']
            row_types = data['row_types']
            
            # Create a root node for the sheet
            sheet_node = QTreeWidgetItem(self.tree, [sheet_name, "", "Sheet Root", "", "", "Heading"])
            for i in range(6): sheet_node.setFont(i, bold_font)
            sheet_node.setBackground(2, QColor("#bbdefb")) # light blue

            current_heading_item = sheet_node
            
            for r in range(len(df)):
                rtype = row_types[r]
                if rtype == 'ignore': continue
                
                ref_val = str(df.iloc[r, ref_col]) if 0 <= ref_col < len(df.columns) else ""
                desc_val = str(df.iloc[r, desc_col]) if 0 <= desc_col < len(df.columns) else ""
                qty_val = str(df.iloc[r, qty_col]) if 0 <= qty_col < len(df.columns) else ""
                unit_val = str(df.iloc[r, unit_col]) if 0 <= unit_col < len(df.columns) else ""
                
                if rtype == 'heading':
                    current_heading_item = QTreeWidgetItem(sheet_node, [sheet_name, ref_val, desc_val, "", "", "Heading"])
                    for i in range(6): current_heading_item.setFont(i, bold_font)
                    current_heading_item.setBackground(2, self.COLOR_HEADING)
                
                elif rtype == 'item':
                    parent = current_heading_item if current_heading_item else sheet_node
                    item_node = QTreeWidgetItem(parent, [sheet_name, ref_val, desc_val, qty_val, unit_val, "Item"])
                    
        self.tree.expandAll()

    def _import_to_estimate(self):
        """Creates Tasks in the active estimate based on the mapped items across all sheets."""
        if not self.active_est_window:
            QMessageBox.warning(self, "Error", "No active estimate window found to import into.")
            return
            
        ref_col = self.cb_ref.currentIndex() - 1
        desc_col = self.cb_desc.currentIndex() - 1
        qty_col = self.cb_qty.currentIndex() - 1
        unit_col = self.cb_unit.currentIndex() - 1

        if desc_col < 0:
            QMessageBox.warning(self, "Error", "Description column must be mapped.")
            return

        self.active_est_window.save_state()
        from models import Task
        
        imported_count = 0
        
        for sheet_name, data in self.sheet_data.items():
            df = data['df']
            row_types = data['row_types']
            current_category = ""
            
            for r in range(len(df)):
                rtype = row_types[r]
                
                desc_val = str(df.iloc[r, desc_col]).strip() if 0 <= desc_col < len(df.columns) else ""
                if not desc_val: continue
                
                if rtype == 'heading':
                    current_category = desc_val
                elif rtype == 'item':
                    ref_val = str(df.iloc[r, ref_col]).strip() if 0 <= ref_col < len(df.columns) else ""
                    qty_str = str(df.iloc[r, qty_col]).strip() if 0 <= qty_col < len(df.columns) else "0"
                    unit_val = str(df.iloc[r, unit_col]).strip() if 0 <= unit_col < len(df.columns) else ""
                    
                    try:
                        qty = float(qty_str.replace(',', '').replace(' ', ''))
                    except ValueError:
                        qty = 1.0 # fallback
                        
                    full_desc = f"[{ref_val}] {desc_val}" if ref_val else desc_val
                    # Structure: [Sheet Name] -> [Heading Category] -> Description
                    prefix = f"[{sheet_name}]"
                    if current_category:
                        prefix += f" {current_category} -"
                        
                    full_desc = f"{prefix} {full_desc}"
                        
                    new_task = Task(description=full_desc, quantity=qty, unit=unit_val)
                    self.active_est_window.estimate.add_task(new_task)
                    imported_count += 1
                
        self.active_est_window.db_manager.save_estimate(self.active_est_window.estimate)
        self.active_est_window.refresh_view()
        QMessageBox.information(self, "Success", f"Successfully imported {imported_count} items from all sheets into the estimate.")
        self.close()
