import os
import shutil
import sqlite3
import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QDialogButtonBox, QMessageBox, QProgressBar, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDoubleValidator

from database import DatabaseManager


class MigrationWorker(QThread):
    progress = pyqtSignal(int, str)
    finished_mig = pyqtSignal(bool, str)

    def __init__(self, project_dir, old_currency, new_currency, rate, operator='/'):
        super().__init__()
        self.project_dir = project_dir
        self.old_currency = old_currency
        self.new_currency = new_currency
        self.rate = rate
        self.operator = operator

    def run(self):
        try:
            self.progress.emit(5, "Creating backups...")
            self._create_backups()
            
            self.progress.emit(20, "Migrating Project Database...")
            self._migrate_project_database()
            
            self.progress.emit(50, "Migrating PBOQ files...")
            self._migrate_pboqs()
            
            self.progress.emit(100, "Migration Complete.")
            self.finished_mig.emit(True, "All monetary values have been successfully converted.")
        except Exception as e:
            self.finished_mig.emit(False, str(e))

    def _create_backups(self):
        backup_dir = os.path.join(self.project_dir, "Backups", "Pre-Currency-Migration")
        os.makedirs(backup_dir, exist_ok=True)
        
        # Backup Project Database
        proj_db_dir = os.path.join(self.project_dir, "Project Database")
        if os.path.exists(proj_db_dir):
            for f in os.listdir(proj_db_dir):
                if f.endswith('.db'):
                    shutil.copy2(os.path.join(proj_db_dir, f), os.path.join(backup_dir, f"{f}.bak"))

        # Backup PBOQs
        pboq_dir = os.path.join(self.project_dir, "Priced BOQs")
        if os.path.exists(pboq_dir):
            for f in os.listdir(pboq_dir):
                if f.endswith('.db'):
                    shutil.copy2(os.path.join(pboq_dir, f), os.path.join(backup_dir, f"{f}.bak"))

    def _migrate_project_database(self):
        proj_db_dir = os.path.join(self.project_dir, "Project Database")
        if not os.path.exists(proj_db_dir): return
        
        db_path = None
        for f in os.listdir(proj_db_dir):
            if f.endswith('.db'):
                db_path = os.path.join(proj_db_dir, f)
                break
                
        if not db_path:
            return
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            op = self.operator
            if op not in ['*', '/']: op = '/'
            
            # 1. Update Settings
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'currency'", (self.new_currency,))
            
            # 2. Scale Library Tables
            cursor.execute(f"UPDATE materials SET price = price {op} ? WHERE price IS NOT NULL", (self.rate,))
            cursor.execute("UPDATE materials SET currency = ? WHERE currency = ?", (self.new_currency, self.old_currency))
            
            cursor.execute(f"UPDATE labor SET rate = rate {op} ? WHERE rate IS NOT NULL", (self.rate,))
            cursor.execute("UPDATE labor SET currency = ? WHERE currency = ?", (self.new_currency, self.old_currency))
            
            cursor.execute(f"UPDATE equipment SET rate = rate {op} ? WHERE rate IS NOT NULL", (self.rate,))
            cursor.execute("UPDATE equipment SET currency = ? WHERE currency = ?", (self.new_currency, self.old_currency))
            
            cursor.execute(f"UPDATE plant SET rate = rate {op} ? WHERE rate IS NOT NULL", (self.rate,))
            cursor.execute("UPDATE plant SET currency = ? WHERE currency = ?", (self.new_currency, self.old_currency))
            
            cursor.execute(f"UPDATE indirect_costs SET amount = amount {op} ? WHERE amount IS NOT NULL", (self.rate,))
            cursor.execute("UPDATE indirect_costs SET currency = ? WHERE currency = ?", (self.new_currency, self.old_currency))
            
            # 3. Scale Main Estimates
            cursor.execute(f"UPDATE estimates SET grand_total = grand_total {op} ?, net_total = net_total {op} ?", (self.rate, self.rate))
            cursor.execute("UPDATE estimates SET currency = ? WHERE currency = ?", (self.new_currency, self.old_currency))
            
            # 4. Scale Estimate Internals
            cursor.execute(f"UPDATE estimate_materials SET price = price {op} ? WHERE price IS NOT NULL", (self.rate,))
            cursor.execute("UPDATE estimate_materials SET currency = ? WHERE currency = ?", (self.new_currency, self.old_currency))
            
            cursor.execute(f"UPDATE estimate_labor SET rate = rate {op} ? WHERE rate IS NOT NULL", (self.rate,))
            cursor.execute("UPDATE estimate_labor SET currency = ? WHERE currency = ?", (self.new_currency, self.old_currency))
            
            cursor.execute(f"UPDATE estimate_equipment SET rate = rate {op} ? WHERE rate IS NOT NULL", (self.rate,))
            cursor.execute("UPDATE estimate_equipment SET currency = ? WHERE currency = ?", (self.new_currency, self.old_currency))
            
            cursor.execute(f"UPDATE estimate_plant SET rate = rate {op} ? WHERE rate IS NOT NULL", (self.rate,))
            cursor.execute("UPDATE estimate_plant SET currency = ? WHERE currency = ?", (self.new_currency, self.old_currency))
            
            cursor.execute(f"UPDATE estimate_indirect_costs SET amount = amount {op} ? WHERE amount IS NOT NULL", (self.rate,))
            cursor.execute("UPDATE estimate_indirect_costs SET currency = ? WHERE currency = ?", (self.new_currency, self.old_currency))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _migrate_pboqs(self):
        pboq_dir = os.path.join(self.project_dir, "Priced BOQs")
        states_dir = os.path.join(self.project_dir, "PBOQ States")
        
        if not os.path.exists(pboq_dir): return
        
        for f in os.listdir(pboq_dir):
            if not f.endswith('.db'): continue
            
            db_path = os.path.join(pboq_dir, f)
            state_path = os.path.join(states_dir, f"{f}.json")
            
            mappings = {}
            if os.path.exists(state_path):
                try:
                    with open(state_path, 'r') as sf:
                        st = json.load(sf)
                        mappings = st.get('mappings', {})
                except:
                    pass
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                # Get column schema
                cursor.execute("PRAGMA table_info(pboq_items)")
                db_cols = [info[1] for info in cursor.fetchall()]
                
                # Build list of columns to scale
                cols_to_scale = []
                
                # Logical named columns
                for logic_col in ["GrossRate", "PlugRate", "ProvSum", "PCSum", "Daywork", "SubbeeRate"]:
                    if logic_col in db_cols: cols_to_scale.append(logic_col)
                    
                # Physical mapped columns
                roles_to_scale = ['bill_rate', 'bill_amount', 'rate', 'plug_rate', 'prov_sum', 'pc_sum', 'daywork', 'sub_rate']
                for role in roles_to_scale:
                    col_idx = mappings.get(role, -1)
                    if col_idx >= 0:
                        db_idx = col_idx + 1 # offset for 'Sheet' column
                        if db_idx < len(db_cols):
                            col_name = db_cols[db_idx]
                            if col_name not in cols_to_scale:
                                cols_to_scale.append(col_name)
                                
                if not cols_to_scale:
                    conn.close()
                    continue
                    
                # Iterate rows and scale
                cursor.execute(f"SELECT rowid, {', '.join(f'\"{c}\"' for c in cols_to_scale)} FROM pboq_items")
                rows = cursor.fetchall()
                
                for row in rows:
                    rowid = row[0]
                    vals = list(row[1:])
                    updates = []
                    
                    for i, v in enumerate(vals):
                        if v is None or str(v).strip() == "": continue
                        
                        try:
                            # Parse out comma-formatted string, scale, format back
                            numeric_val = float(str(v).replace(',', ''))
                            if self.operator == '*':
                                scaled_val = numeric_val * self.rate
                            else:
                                scaled_val = numeric_val / self.rate
                            formatted_val = f"{scaled_val:,.2f}"
                            updates.append((f'"{cols_to_scale[i]}" = ?', formatted_val))
                        except ValueError:
                            # Not a number, skip
                            pass
                            
                    if updates:
                        set_clause = ", ".join([u[0] for u in updates])
                        params = [u[1] for u in updates] + [rowid]
                        cursor.execute(f"UPDATE pboq_items SET {set_clause} WHERE rowid = ?", params)
                        
                # Update currency logical fields
                currency_cols = ["PlugCurrency", "ProvSumCurrency", "PCSumCurrency", "DayworkCurrency"]
                curr_updates = [f'"{c}" = ?' for c in currency_cols if c in db_cols]
                if curr_updates:
                    cursor.execute(f'UPDATE pboq_items SET {", ".join(curr_updates)}', [self.new_currency] * len(curr_updates))
                    
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()

class CurrencyMigrationDialog(QDialog):
    def __init__(self, project_dir, old_currency, new_currency, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Currency Conversion Wizard")
        self.setMinimumWidth(400)
        
        self.project_dir = project_dir
        self.old_currency = old_currency
        self.new_currency = new_currency
        
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel(f"<b>Base Currency Change Detected</b><br><br>Changing from <b>{self.old_currency}</b> to <b>{self.new_currency}</b>")
        title.setWordWrap(True)
        layout.addWidget(title)
        
        desc = QLabel("Do you want to mathematically scale all existing rates and amounts in this project to reflect the new currency?")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        lbl_rate = QLabel("Select operation and Exchange Rate:")
        layout.addWidget(lbl_rate)
        
        input_layout = QHBoxLayout()
        self.operator_combo = QComboBox()
        self.operator_combo.addItems(["Divide (/)", "Multiply (*)"])
        input_layout.addWidget(self.operator_combo)
        
        self.rate_input = QLineEdit()
        self.rate_input.setPlaceholderText("e.g. 11.0")
        self.rate_input.setValidator(QDoubleValidator(0.0001, 10000.0, 4))
        input_layout.addWidget(self.rate_input)
        input_layout.setStretch(1, 1)
        layout.addLayout(input_layout)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        self.status_lbl = QLabel()
        self.status_lbl.hide()
        layout.addWidget(self.status_lbl)
        
        self.btn_box = QDialogButtonBox()
        self.btn_scale = self.btn_box.addButton("Scale Values", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_just_labels = self.btn_box.addButton("Just Change Labels", QDialogButtonBox.ButtonRole.RejectRole)
        self.btn_cancel = self.btn_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        
        self.btn_scale.clicked.connect(self._start_migration)
        self.btn_just_labels.clicked.connect(self.reject) # Returns Rejected, meaning "Don't scale"
        self.btn_cancel.clicked.connect(self._on_cancel)
        
        layout.addWidget(self.btn_box)

    def _on_cancel(self):
        self.done(-1) # Special code for Cancel

    def _start_migration(self):
        rate_text = self.rate_input.text()
        if not rate_text:
            QMessageBox.warning(self, "Validation", "Please enter an exchange rate.")
            return
            
        rate = float(rate_text)
        if rate <= 0:
            QMessageBox.warning(self, "Validation", "Exchange rate must be greater than zero.")
            return

        op_text = self.operator_combo.currentText()
        operator = '*' if '*' in op_text else '/'
        action_word = "multiply" if operator == '*' else "divide"

        reply = QMessageBox.question(self, "Confirm Migration", 
                                    f"Are you sure you want to {action_word} all monetary values in the project by {rate}?\n\nBackups will be created.",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                                    
        if reply == QMessageBox.StandardButton.Yes:
            self.btn_box.setEnabled(False)
            self.rate_input.setEnabled(False)
            self.operator_combo.setEnabled(False)
            self.progress_bar.show()
            self.status_lbl.show()
            
            self.worker = MigrationWorker(self.project_dir, self.old_currency, self.new_currency, rate, operator)
            self.worker.progress.connect(self._update_progress)
            self.worker.finished_mig.connect(self._migration_finished)
            self.worker.start()

    def _update_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.status_lbl.setText(msg)

    def _migration_finished(self, success, msg):
        self.btn_box.setEnabled(True)
        if success:
            QMessageBox.information(self, "Migration Complete", msg)
            self.accept() # Returns Accepted, meaning scaled
        else:
            QMessageBox.critical(self, "Migration Failed", msg)
            self.reject()
