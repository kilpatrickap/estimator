import os
import sqlite3
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QHBoxLayout, QMessageBox, QHeaderView, QLineEdit, QTextEdit, QComboBox, QWidget)
from PyQt6.QtCore import Qt, pyqtSignal
from pboq_logic import PBOQLogic


class PackageSummaryDialog(QDialog):
    dataChanged = pyqtSignal()

    def __init__(self, db_path, project_dir, pkg_col, markup_col, categories_dict, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.project_dir = project_dir
        self.pkg_col = pkg_col
        self.markup_col = markup_col
        self.categories_dict = categories_dict # Mapping of Category Name -> Code Prefix
        self.setWindowTitle("Work Packages Management")
        self.setMinimumWidth(850) # Increased for 4th column
        self.setMinimumHeight(450)
        self.category_names = sorted(list(self.categories_dict.keys()))
        self._init_ui()
        self._load_data()




    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Subcontractor Package", "Project Category", "Default Markup (%)", "Internal Markup Notes (Composition)"])
        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 300)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        self.table.setAlternatingRowColors(True)
        # Professional Excel-like row height (24px)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.verticalHeader().setMinimumSectionSize(24)
        # Interactive mode allows manual override while keeping the Excel feel
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        self.sync_all_btn = QPushButton("Sync All PBOQs")
        self.sync_all_btn.setToolTip("Apply these markups to ALL PBOQ files in the project folder")
        self.sync_all_btn.clicked.connect(self._sync_to_all_pboqs)
        
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self._save_changes)
        
        btn_layout.addWidget(self.sync_all_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)
        
        self.table.itemChanged.connect(self._handle_item_changed)

    def _handle_item_changed(self, item):
        if item.column() == 2: # Markup column
            self.table.blockSignals(True)
            txt = item.text().replace(',', '').replace('%', '')
            try:
                f_val = float(txt) if txt else 0.0
                item.setText("{:,.2f}%".format(f_val))
            except:
                pass # Keep what user typed if invalid
            self.table.blockSignals(False)

    def _load_data(self):
        self.table.blockSignals(True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Ensure schema is up to date with new fields
            PBOQLogic.ensure_schema(conn)
            
            # Load metadata (Categories, etc.)
            pkg_settings = PBOQLogic.get_package_settings(self.db_path)

            # Group by package name and find the most common markup (or max)
            cursor.execute(f"""
                SELECT "{self.pkg_col}", MAX("{self.markup_col}"), MAX("SubbeeNotes")
                FROM pboq_items 
                WHERE "{self.pkg_col}" IS NOT NULL AND "{self.pkg_col}" != ''
                GROUP BY "{self.pkg_col}"
                ORDER BY "{self.pkg_col}"
            """)
            rows = cursor.fetchall()
            self.table.setRowCount(len(rows))
            for i, (pkg, markup, notes) in enumerate(rows):
                # Col 0: Package Name (Read-only)
                name_item = QTableWidgetItem(pkg)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                self.table.setItem(i, 0, name_item)
                
                # Col 1: Category Dropdown (Wrapped for Top Alignment)
                container = QWidget()
                c_layout = QVBoxLayout(container)
                c_layout.setContentsMargins(0, 0, 0, 0)
                c_layout.setSpacing(0)
                
                cat_combo = QComboBox()
                cat_combo.addItems(["-- Select Category --"] + self.category_names)
                current_cat = pkg_settings.get(pkg, {}).get('category', '')
                if current_cat in self.category_names:
                    cat_combo.setCurrentText(current_cat)
                
                cat_combo.setStyleSheet("QComboBox { border: none; background: transparent; padding: 0px; }")
                c_layout.addWidget(cat_combo, 0, Qt.AlignmentFlag.AlignTop)
                self.table.setCellWidget(i, 1, container)

                # Col 2: Markup (%)
                # Priority: 1. Metadata Setting, 2. Existing PBOQ Value, 3. Project Default (20%)
                m_val = pkg_settings.get(pkg, {}).get('markup')
                if m_val is None:
                    try:
                        m_val = float(markup) if markup else 20.0
                    except:
                        m_val = 20.0
                
                markup_item = QTableWidgetItem("{:,.2f}%".format(m_val))
                markup_item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
                self.table.setItem(i, 2, markup_item)
                
                # Col 3: Notes (QTextEdit)
                notes_edit = QTextEdit(notes if notes else "")
                notes_edit.setPlaceholderText("Markup composition ...")
                notes_edit.setAcceptRichText(False)
                notes_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                notes_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                notes_edit.setStyleSheet("QTextEdit { border: none; padding-top: 0px; padding-left: 2px; background: transparent; }")
                self.table.setCellWidget(i, 3, notes_edit)
                
                notes_edit.textChanged.connect(lambda row=i, widget=notes_edit: self._adjust_row_height(row, widget))
                self._adjust_row_height(i, notes_edit)
                
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load package labels: {e}")
        finally:
            conn.close()
            self.table.blockSignals(False)

    def showEvent(self, event):
        """Recalculate heights once the window is actually visible and widths are finalized."""
        super().showEvent(event)
        for i in range(self.table.rowCount()):
            w = self.table.cellWidget(i, 3) # Notes column
            if w:
                self._adjust_row_height(i, w)

    def _adjust_row_height(self, row, widget):
        """Dynamically set the row height to fit the text content exactly."""
        doc = widget.document()
        col_width = self.table.columnWidth(3) # Notes column
        if col_width > 0:
            doc.setTextWidth(col_width - 8)
        target_h = int(doc.size().height()) + 4
        self.table.setRowHeight(row, max(24, target_h))

    def resizeEvent(self, event):
        """Ensure heights update if the user stretches the window (changing the wrap)."""
        super().resizeEvent(event)
        for i in range(self.table.rowCount()):
            w = self.table.cellWidget(i, 3)
            if w:
                self._adjust_row_height(i, w)

    def _save_changes(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        settings_to_save = {}
        try:
            for i in range(self.table.rowCount()):
                pkg = self.table.item(i, 0).text()
                
                # Fetch Category from dropdown (found inside the alignment wrapper)
                cat_wrapper = self.table.cellWidget(i, 1)
                selected_cat = ""
                if cat_wrapper:
                    cat_combo = cat_wrapper.layout().itemAt(0).widget()
                    if isinstance(cat_combo, QComboBox) and cat_combo.currentIndex() > 0:
                        selected_cat = cat_combo.currentText()

                # Fetch Markup
                raw_m = self.table.item(i, 2).text().replace(',', '').replace('%', '')
                try: markup_val = float(raw_m)
                except ValueError: markup_val = 10.0
                
                # Fetch Notes
                notes_widget = self.table.cellWidget(i, 3)
                notes_val = notes_widget.toPlainText() if notes_widget else ""
                
                # Apply this markup/category to all items in this package in the CURRENT PBOQ
                cursor.execute(f"""
                    UPDATE pboq_items 
                    SET "{self.markup_col}" = ?, "SubbeeCategory" = ?, "SubbeeNotes" = ? 
                    WHERE "{self.pkg_col}" = ?
                """, (str(markup_val), selected_cat, notes_val, pkg))
                
                # Prepare metadata for separate table
                settings_to_save[pkg] = {
                    'category': selected_cat,
                    'markup': markup_val,
                    'notes': notes_val
                }
            
            conn.commit()
            conn.close()

            # Persist Package Meta-Data
            PBOQLogic.save_package_settings(self.db_path, settings_to_save)
            
            self.dataChanged.emit()
            QMessageBox.information(self, "Success", "Changes saved successfully.")
        except sqlite3.Error as e:
            if conn: conn.close()
            QMessageBox.critical(self, "Save Error", f"Failed to save changes: {e}")



    def _sync_to_all_pboqs(self):
        """Applies current table markups to every PBOQ database in the project's Priced BOQs folder."""
        # Robust folder detection: handle cases where project_dir points to subfolders
        pboq_folder = ""
        current = self.project_dir
        for _ in range(4): # Check up to 4 levels up
            candidate = os.path.join(current, "Priced BOQs")
            if os.path.exists(candidate):
                pboq_folder = candidate
                break
            parent = os.path.dirname(current)
            if parent == current: break # reached root
            current = parent
            
        if not pboq_folder:
            QMessageBox.warning(self, "Sync Error", f"Could not find 'Priced BOQs' folder starting from:\n{self.project_dir}")
            return
        
        # Gather settings from table
        package_settings = {}
        for i in range(self.table.rowCount()):
            pkg = self.table.item(i, 0).text().strip()
            if not pkg: continue
            
            # Fetch Category from dropdown (inside wrapper)
            cat_wrapper = self.table.cellWidget(i, 1)
            selected_cat = ""
            if cat_wrapper:
                cat_combo = cat_wrapper.layout().itemAt(0).widget()
                if isinstance(cat_combo, QComboBox) and cat_combo.currentIndex() > 0:
                    selected_cat = cat_combo.currentText()

            # Fetch Markup
            raw_m = self.table.item(i, 2).text().replace(',', '').replace('%', '')
            try: m_val = float(raw_m)
            except: m_val = 20.0
            
            # Fetch Notes
            notes_widget = self.table.cellWidget(i, 3)
            n_val = notes_widget.toPlainText() if notes_widget else ""
            
            package_settings[pkg] = {'markup': m_val, 'category': selected_cat, 'notes': n_val}

        if not package_settings: return

        db_files = [f for f in os.listdir(pboq_folder) if f.lower().endswith('.db')]
        updated_count = 0
        total_rows_updated = 0
        
        for db_name in db_files:
            target_path = os.path.join(pboq_folder, db_name)
            try:
                conn = sqlite3.connect(target_path)
                success, db_cols = PBOQLogic.ensure_schema(conn)
                if not success:
                    conn.close()
                    continue
                
                cursor = conn.cursor()
                target_markup_col = db_cols[14] if len(db_cols) > 14 else "Column 13" # Standardized Markup col
                
                rows_in_file = 0
                for pkg, data in package_settings.items():
                    # Update data rows
                    cols_to_search = [f'"{c}"' for c in db_cols if c != 'Sheet']
                    where_clause = " OR ".join([f"{c} LIKE ? COLLATE NOCASE" for c in cols_to_search])
                    
                    sql = f"""
                        UPDATE pboq_items 
                        SET "{target_markup_col}" = ?, SubbeeMarkup = ?, "SubbeeCategory" = ?, "SubbeeNotes" = ?
                        WHERE {where_clause}
                    """
                    params = [str(data['markup']), str(data['markup']), data['category'], data['notes']] + [pkg] * len(cols_to_search)
                    
                    cursor.execute(sql, tuple(params))
                    rows_in_file += cursor.rowcount

                    # Update Package Settings Table
                    cursor.execute("""
                        INSERT OR REPLACE INTO subcontractor_package_settings (package_name, category_name, markup_default, notes)
                        VALUES (?, ?, ?, ?)
                    """, (pkg, data['category'], data['markup'], data['notes']))
                    
                conn.commit()
                conn.close()
                if rows_in_file > 0:
                    updated_count += 1
                    total_rows_updated += rows_in_file
            except Exception as e:
                print(f"Failed to sync {db_name}: {e}")
                
        self.dataChanged.emit() # Refresh current view too

        
        # Ensure UI repaints before we show the blocking popup
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        
        msg = (f"Successfully synced markups in {updated_count} PBOQ file(s).\n"
               f"Total rows updated: {total_rows_updated}\n\n"
               f"Layouts are standardized based on the target file schema.")
        QMessageBox.information(self, "Project Sync Complete", msg)


