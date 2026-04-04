import os
import sqlite3
import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QDialogButtonBox, QMessageBox, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class MarginMigrationWorker(QThread):
    progress = pyqtSignal(int, str)
    finished_mig = pyqtSignal(bool, str)

    def __init__(self, project_dir, old_overhead, old_profit, new_overhead, new_profit):
        super().__init__()
        self.project_dir = project_dir
        self.old_overhead = old_overhead
        self.old_profit = old_profit
        self.new_overhead = new_overhead
        self.new_profit = new_profit

    def run(self):
        try:
            self.progress.emit(10, "Calculating Multipliers...")
            
            # Subtotal * (1 + Overhead%) * (1 + Profit%)
            old_multiplier = (1 + self.old_overhead / 100.0) * (1 + self.old_profit / 100.0)
            new_multiplier = (1 + self.new_overhead / 100.0) * (1 + self.new_profit / 100.0)
            
            if old_multiplier <= 0:
                old_multiplier = 1.0
                
            scale_factor = new_multiplier / old_multiplier
            
            self.progress.emit(30, "Migrating PBOQ files (Gross Rates only)...")
            self._migrate_pboq_gross_rates(scale_factor)
            
            self.progress.emit(70, "Migrating SOR/Library databases...")
            self._migrate_sor_gross_rates(scale_factor)
            
            self.progress.emit(100, "Migration Complete.")
            self.finished_mig.emit(True, "All existing Gross Rates have been mathematically scaled to reflect new Overhead & Profit.")
        except Exception as e:
            self.finished_mig.emit(False, str(e))

    def _migrate_sor_gross_rates(self, scale_factor):
        sor_dir = os.path.join(self.project_dir, "SOR")
        lib_dir = os.path.join(self.project_dir, "Imported Library")
        
        target_dirs = []
        if os.path.exists(sor_dir): target_dirs.append(sor_dir)
        if os.path.exists(lib_dir): target_dirs.append(lib_dir)
        
        for d in target_dirs:
            for f in os.listdir(d):
                if not f.endswith('.db'): continue
                db_path = os.path.join(d, f)
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                try:
                    cursor.execute("PRAGMA table_info(sor_items)")
                    db_cols = [info[1] for info in cursor.fetchall()]
                    if "GrossRate" not in db_cols: continue
                        
                    cursor.execute('SELECT rowid, GrossRate FROM sor_items WHERE GrossRate IS NOT NULL AND GrossRate != ""')
                    rows = cursor.fetchall()
                    
                    updates = []
                    for row in rows:
                        rowid = row[0]
                        v = row[1]
                        try:
                            import re
                            clean_str = re.sub(r'[^\d.-]', '', str(v))
                            if not clean_str: continue
                            numeric_val = float(clean_str)
                            scaled_val = numeric_val * scale_factor
                            
                            sym_match = re.search(r'^([^\d]+)', str(v).strip())
                            sym = sym_match.group(1).strip() + " " if sym_match else ""
                            
                            formatted_val = f"{sym}{scaled_val:,.2f}".strip()
                            updates.append((formatted_val, rowid))
                        except ValueError:
                            pass
                    
                    if updates:
                        cursor.executemany('UPDATE sor_items SET GrossRate = ? WHERE rowid = ?', updates)
                        
                    conn.commit()
                except Exception:
                    conn.rollback()
                finally:
                    conn.close()

    def _migrate_pboq_gross_rates(self, scale_factor):
        pboq_dir = os.path.join(self.project_dir, "Priced BOQs")
        if not os.path.exists(pboq_dir): return
        
        # Load mappings
        import json
        states_folder = os.path.join(self.project_dir, "BOQ-Setup States")
        
        for f in os.listdir(pboq_dir):
            if not f.endswith('.db'): continue
            
            db_path = os.path.join(pboq_dir, f)
            db_basename = f
            base_name = db_basename.replace("PBOQ_", "").replace(".db", ".xlsx")
            state_file = os.path.join(states_folder, base_name + ".state.json")
            
            # Map default columns (-1 means unmapped)
            m_rate = -1
            m_amt = -1
            if os.path.exists(states_folder) and os.path.exists(state_file):
                try:
                    with open(state_file, 'r') as sf:
                        st = json.load(sf)
                        m_rate = st.get('cb_rate', 0) - 1
                        m_amt = st.get('cb_amount', 0) - 1 # If they mapped an amount
                except: pass

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute("PRAGMA table_info(pboq_items)")
                db_cols = [info[1] for info in cursor.fetchall()]
                
                if "GrossRate" not in db_cols:
                    conn.close()
                    continue
                    
                target_cols = ['"GrossRate"']
                if m_rate >= 0: target_cols.append(f'"Column {m_rate}"')
                if m_amt >= 0: target_cols.append(f'"Column {m_amt}"')
                
                # We need "RateCode" and Qty to do a native extraction if linked
                q_cols = ", ".join(set(target_cols))
                has_code = "RateCode" in db_cols
                query_str = f'SELECT rowid, {q_cols}'
                if has_code: query_str += ', "RateCode"'
                # Get the generic Qty column if they mapped it
                m_qty = -1
                if os.path.exists(states_folder) and os.path.exists(state_file):
                    try:
                        with open(state_file, 'r') as sf:
                            st = json.load(sf)
                            m_qty = st.get('cb_qty', 0) - 1
                    except: pass
                if m_qty >= 0:
                    query_str += f', "Column {m_qty}"'
                    
                query_str += ' FROM pboq_items WHERE "GrossRate" IS NOT NULL AND "GrossRate" != ""'
                cursor.execute(query_str)
                rows = cursor.fetchall()
                
                updates = []
                cols_to_update = list(set([c.strip('"') for c in target_cols]))
                
                # Cache Rate Buildups to get fresh mathematically calculated Grand Totals
                native_rates = {}
                rates_db_path = os.path.join(self.project_dir, "SOR", "construction_rates.db")
                if os.path.exists(rates_db_path):
                    from database import DatabaseManager
                    rates_db = DatabaseManager(rates_db_path)
                    for r_data in rates_db.get_rates_data():
                        cde = r_data.get('rate_code')
                        if cde:
                            est_obj = rates_db.load_estimate_details(r_data.get('id'))
                            if est_obj:
                                native_rates[cde.strip().upper()] = est_obj.calculate_totals()['grand_total']

                for row in rows:
                    rowid = row[0]
                    v_gross = row[1] # GrossRate is at index 1
                    
                    # Extract variables from dynamic end of row
                    code_val = ""
                    qty_val = 1.0
                    idx_offset = 1 + len(set(target_cols))
                    if has_code:
                        code_val = str(row[idx_offset] or "").strip().upper()
                        idx_offset += 1
                    if m_qty >= 0:
                        try:
                            import re
                            q_clean = re.sub(r'[^\d.-]', '', str(row[idx_offset]))
                            qty_val = float(q_clean) if q_clean else 1.0
                        except: pass
                    
                    try:
                        import re
                        clean_str = re.sub(r'[^\d.-]', '', str(v_gross))
                        if not clean_str: continue
                        numeric_val = float(clean_str)
                        
                        sym_match = re.search(r'^([^\d]+)', str(v_gross).strip())
                        sym = sym_match.group(1).strip() + " " if sym_match else ""
                        
                        # IF link exists, pull the PRECISE native rate!
                        if code_val and code_val in native_rates:
                            scaled_val = native_rates[code_val]
                        else:
                            scaled_val = numeric_val * scale_factor
                            
                        new_gross = f"{sym}{scaled_val:,.2f}".strip()
                        
                        # Apply multiplier to ALL targeted columns in this row independently
                        row_update_vals = []
                        for i, col_name in enumerate(cols_to_update):
                            cv = row[i+1] # +1 because rowid is 0
                            
                            if m_amt >= 0 and col_name == f'Column {m_amt}':
                                # It's an Amount column. Amount = Qty * new Rate
                                c_scaled = scaled_val * qty_val
                                c_sym_match = re.search(r'^([^\d]+)', str(cv).strip())
                                c_sym = c_sym_match.group(1).strip() + " " if c_sym_match else sym
                                row_update_vals.append(f"{c_sym}{c_scaled:,.2f}".strip())
                                continue
                            
                            if m_rate >= 0 and col_name == f'Column {m_rate}':
                                c_sym_match = re.search(r'^([^\d]+)', str(cv).strip())
                                c_sym = c_sym_match.group(1).strip() + " " if c_sym_match else sym
                                row_update_vals.append(f"{c_sym}{scaled_val:,.2f}".strip())
                                continue
                                
                            if col_name == 'GrossRate':
                                row_update_vals.append(new_gross)
                                continue
                                
                            # Fallback generic math scale (shouldn't trigger normally)
                            if not cv:
                                row_update_vals.append(cv)
                                continue
                            
                            c_clean = re.sub(r'[^\d.-]', '', str(cv))
                            if not c_clean:
                                row_update_vals.append(cv)
                                continue
                                
                            c_num = float(c_clean)
                            c_scaled = c_num * scale_factor
                            c_sym_match = re.search(r'^([^\d]+)', str(cv).strip())
                            c_sym = c_sym_match.group(1).strip() + " " if c_sym_match else ""
                            row_update_vals.append(f"{c_sym}{c_scaled:,.2f}".strip())
                            
                        # Format the update tuple: (*vals, rowid)
                        updates.append(tuple(row_update_vals + [rowid]))
                        
                    except ValueError:
                        pass
                
                if updates:
                    set_clause = ", ".join([f'"{c}" = ?' for c in cols_to_update])
                    cursor.executemany(f'UPDATE pboq_items SET {set_clause} WHERE rowid = ?', updates)
                    
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()

class MarginMigrationDialog(QDialog):
    def __init__(self, project_dir, old_overhead, old_profit, new_overhead, new_profit, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Margin Adjustment Wizard")
        
        self.project_dir = project_dir
        self.old_o = old_overhead
        self.old_p = old_profit
        self.new_o = new_overhead
        self.new_p = new_profit
        
        self.setMinimumSize(450, 300)
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel(f"<b>Overhead / Profit Change Detected!</b>")
        title.setStyleSheet("font-size: 14px;")
        layout.addWidget(title)
        
        # Format strings safely
        desc = QLabel(
            f"You have modified the project margins:<br>"
            f"• Overhead: <b>{self.old_o}%</b> &rarr; <b>{self.new_o}%</b><br>"
            f"• Profit: <b>{self.old_p}%</b> &rarr; <b>{self.new_p}%</b><br><br>"
            f"All dynamic base rate build-ups will automatically adopt these new percentages. However, <b>Priced BOQ</b> spreadsheets currently contain static 'Gross Rates'.<br><br>"
            f"Do you want to mathematically recalculate all PBOQ Gross Rates to reflect this new margin structure?"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        self.status_lbl = QLabel()
        self.status_lbl.setStyleSheet("font-size: 10px; color: #666;")
        self.status_lbl.hide()
        layout.addWidget(self.status_lbl)
        
        self.btn_box = QDialogButtonBox()
        self.btn_scale = self.btn_box.addButton("Recalculate Gross Rates", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_just_labels = self.btn_box.addButton("No, Leave as Static", QDialogButtonBox.ButtonRole.RejectRole)
        self.btn_cancel = self.btn_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        
        self.btn_scale.clicked.connect(self._start_migration)
        self.btn_just_labels.clicked.connect(self.reject) 
        self.btn_cancel.clicked.connect(self._on_cancel)
        
        layout.addWidget(self.btn_box)
        
        self.setFixedWidth(550)
        self.setFixedHeight(self.sizeHint().height())

    def _on_cancel(self):
        self.done(-1) 

    def _start_migration(self):
        self.btn_box.setEnabled(False)
        self.progress_bar.show()
        self.status_lbl.show()
        
        self.worker = MarginMigrationWorker(self.project_dir, self.old_o, self.old_p, self.new_o, self.new_p)
        self.worker.progress.connect(self._update_progress)
        self.worker.finished_mig.connect(self._migration_finished)
        self.worker.start()

    def _update_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.status_lbl.setText(msg)

    def _migration_finished(self, success, msg):
        self.btn_box.setEnabled(True)
        if success:
            QMessageBox.information(self, "Recalculation Complete", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Migration Failed", msg)
            self.reject()
