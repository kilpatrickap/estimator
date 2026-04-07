import os
import sqlite3
import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QDialogButtonBox, QMessageBox, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class MarginMigrationWorker(QThread):
    progress = pyqtSignal(int, str)
    finished_mig = pyqtSignal(bool, str)

    def __init__(self, project_dir, old_overhead, old_profit, new_overhead, new_profit, old_factor=1.0, new_factor=1.0):
        super().__init__()
        self.project_dir = project_dir
        self.old_overhead = old_overhead
        self.old_profit = old_profit
        self.new_overhead = new_overhead
        self.new_profit = new_profit
        self.old_factor = old_factor
        self.new_factor = new_factor

    def run(self):
        try:
            self.progress.emit(10, "Calculating Multipliers...")
            
            # Multiplier: Factor * (1 + Overhead% + Profit%) (Parallel Markup)
            old_multiplier = self.old_factor * (1 + (self.old_overhead / 100.0) + (self.old_profit / 100.0))
            new_multiplier = self.new_factor * (1 + (self.new_overhead / 100.0) + (self.new_profit / 100.0))
            
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
        
        native_rates = {}
        # Scan ALL db files in Imported Library, SOR, and Project Database for rate buildups
        from database import DatabaseManager
        proj_db_dir = os.path.join(self.project_dir, "Project Database")
        # Build scan list: Imported Library -> SOR -> Project Database (last = highest priority)
        scan_dirs = []
        if os.path.exists(lib_dir) and lib_dir not in [sor_dir]:
            scan_dirs.append(lib_dir)
        if os.path.exists(sor_dir):
            scan_dirs.append(sor_dir)
        if os.path.exists(proj_db_dir):
            scan_dirs.append(proj_db_dir)
        for scan_dir in scan_dirs:
            for f in os.listdir(scan_dir):
                if not f.endswith('.db'): continue
                db_path = os.path.join(scan_dir, f)
                try:
                    rdb = DatabaseManager(db_path)
                    for r_data in rdb.get_rates_data():
                        cde = r_data.get('rate_code')
                        if cde:
                            est_obj = rdb.load_estimate_details(r_data.get('id'))
                            if est_obj:
                                gt = est_obj.calculate_totals()['grand_total']
                                native_rates[cde.strip().upper()] = gt
                except Exception as ex:
                    pass
        
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
                        
                    has_code = "RateCode" in db_cols
                    query_str = 'SELECT rowid, GrossRate'
                    if has_code: query_str += ', RateCode'
                    query_str += ' FROM sor_items WHERE GrossRate IS NOT NULL AND GrossRate != ""'
                    
                    cursor.execute(query_str)
                    rows = cursor.fetchall()
                    
                    updates = []
                    for row in rows:
                        rowid = row[0]
                        v = row[1]
                        code_val = str(row[2] or "").strip().upper() if len(row) > 2 else ""
                        
                        try:
                            import re
                            clean_str = re.sub(r'[^\d.-]', '', str(v))
                            if not clean_str: continue
                            numeric_val = float(clean_str)
                            
                            if code_val and code_val in native_rates:
                                scaled_val = native_rates[code_val]
                            else:
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
        
        # Cache Rate Buildups to get fresh mathematically calculated Grand Totals
        native_rates = {}
        # Scan ALL db files in Project Database, SOR, and Imported Library for rate buildups
        from database import DatabaseManager
        proj_db_dir = os.path.join(self.project_dir, "Project Database")
        sor_dir = os.path.join(self.project_dir, "SOR")
        lib_dir = os.path.join(self.project_dir, "Imported Library")
        scan_dirs = []
        if os.path.exists(lib_dir): scan_dirs.append(lib_dir)
        if os.path.exists(sor_dir): scan_dirs.append(sor_dir)
        if os.path.exists(proj_db_dir): scan_dirs.append(proj_db_dir)  # Last = highest priority
        
        for scan_dir in scan_dirs:
            for f in os.listdir(scan_dir):
                if not f.endswith('.db'): continue
                db_path = os.path.join(scan_dir, f)
                try:
                    rdb = DatabaseManager(db_path)
                    for r_data in rdb.get_rates_data():
                        cde = r_data.get('rate_code')
                        if cde:
                            est_obj = rdb.load_estimate_details(r_data.get('id'))
                            if est_obj:
                                gt = est_obj.calculate_totals()['grand_total']
                                native_rates[cde.strip().upper()] = gt
                except Exception as ex:
                    pass
        pboq_files = [f for f in os.listdir(pboq_dir) if f.endswith('.db')]
        for f in pboq_files:
            db_path = os.path.join(pboq_dir, f)
            db_basename = f
            base_name = db_basename.replace("PBOQ_", "").replace(".db", ".xlsx")
            state_file = os.path.join(states_folder, base_name + ".state.json")
            
            # Map default columns (-1 means unmapped)
            # Map default columns (-1 means unmapped)
            m_rate = 6
            m_amt = 5
            m_code = 7
            m_qty = -1
            m_ref = -1
            m_bill_rate = -1
            
            pboq_state_dir = os.path.join(self.project_dir, "PBOQ States")
            pboq_state_file = os.path.join(pboq_state_dir, db_basename + ".json")
            
            if os.path.exists(states_folder) and os.path.exists(state_file):
                try:
                    with open(state_file, 'r') as sf:
                        st = json.load(sf)
                        # Fallbacks for physical mapped rate / amt columns if no PBOQ state exists
                        if not os.path.exists(pboq_state_file):
                            m_rate = st.get('cb_rate', 0) - 1
                            m_amt = st.get('cb_amount', 0) - 1
                        m_qty = st.get('cb_qty', 0) - 1
                        m_ref = st.get('cb_ref', 0) - 1
                except: pass
                
            if os.path.exists(pboq_state_file):
                try:
                    with open(pboq_state_file, 'r') as psf:
                        pst = json.load(psf)
                        if 'mappings' in pst:
                            m_code = pst['mappings'].get('rate_code', 7)
                            m_rate = pst['mappings'].get('rate', 6)
                            m_amt = pst['mappings'].get('bill_amount', 5)
                            m_qty_pst = pst['mappings'].get('qty', -1)
                            if m_qty_pst >= 0: m_qty = m_qty_pst
                            m_ref_pst = pst['mappings'].get('ref', -1)
                            if m_ref_pst >= 0: m_ref = m_ref_pst
                            m_bill_rate_pst = pst['mappings'].get('bill_rate', -1)
                            if m_bill_rate_pst >= 0: m_bill_rate = m_bill_rate_pst
                except: pass
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute('SELECT rowid FROM pboq_items ORDER BY rowid')
                all_rows = cursor.fetchall()
                rowid_to_gidx = {r[0]: idx for idx, r in enumerate(all_rows)}
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_formatting'")
                has_fmt_table = bool(cursor.fetchone())
                formatting_map = {}
                if has_fmt_table:
                    cursor.execute('SELECT row_idx, col_idx, fmt_json FROM pboq_formatting')
                    for r_idx, c_idx, fmt_str in cursor.fetchall():
                        try: formatting_map[(r_idx, c_idx)] = json.loads(fmt_str)
                        except: pass

                cursor.execute("PRAGMA table_info(pboq_items)")
                db_cols = [info[1] for info in cursor.fetchall()]
                if "GrossRate" not in db_cols:
                    conn.close()
                    continue
                    
                # Deterministic List instead of Set
                target_cols = ['"GrossRate"']
                if "RateCode" in db_cols: target_cols.append('"RateCode"')
                if m_rate >= 0 and f'"Column {m_rate}"' not in target_cols: target_cols.append(f'"Column {m_rate}"')
                if m_amt >= 0 and f'"Column {m_amt}"' not in target_cols: target_cols.append(f'"Column {m_amt}"')
                if m_code >= 0 and f'"Column {m_code}"' not in target_cols: target_cols.append(f'"Column {m_code}"')
                if m_bill_rate >= 0 and f'"Column {m_bill_rate}"' not in target_cols: target_cols.append(f'"Column {m_bill_rate}"')
                
                q_cols = ", ".join(target_cols)
                has_code = "RateCode" in db_cols
                query_str = f'SELECT rowid, {q_cols}'
                
                if m_qty >= 0:
                    query_str += f', "Column {m_qty}"'
                if m_ref >= 0:
                    query_str += f', "Column {m_ref}"'
                
                # Fetch ALL applicable rows: rows with existing GrossRate, existing linked RateCode, OR just any mapped Reference (so we can auto-price!)
                where_clauses = ['("GrossRate" IS NOT NULL AND "GrossRate" != "")']
                if has_code:
                    where_clauses.append('("RateCode" IS NOT NULL AND "RateCode" != "")')
                if m_code >= 0:
                    where_clauses.append(f'("Column {m_code}" IS NOT NULL AND "Column {m_code}" != "")')
                if m_ref >= 0:
                    where_clauses.append(f'("Column {m_ref}" IS NOT NULL AND "Column {m_ref}" != "")')
                    
                query_str += ' FROM pboq_items WHERE ' + ' OR '.join(where_clauses)
                cursor.execute(query_str)
                rows = cursor.fetchall()
                
                updates = []
                cols_to_update = [c.strip('"') for c in target_cols]
                
                for row in rows:
                    rowid = row[0]
                    v_gross = row[1] # GrossRate is at index 1
                    g_idx = rowid_to_gidx.get(rowid, -1)
                    
                    is_rate_linked = False
                    is_amt_linked = False
                    
                    if g_idx >= 0 and m_bill_rate >= 0:
                        if formatting_map.get((g_idx, m_bill_rate), {}).get('bg_color', '').lower() == '#e8f5e9':
                            is_rate_linked = True
                            
                    if g_idx >= 0 and m_amt >= 0:
                        if formatting_map.get((g_idx, m_amt), {}).get('bg_color', '').lower() == '#e8f5e9':
                            is_amt_linked = True
                    
                    code_val = ""
                    # Grab logical code if exists
                    if 'RateCode' in cols_to_update:
                        c_idx = cols_to_update.index('RateCode') + 1
                        code_val = str(row[c_idx] or "").strip().upper()
                        
                    # Also check physical rate code column
                    if m_code >= 0:
                        phys_name = f'Column {m_code}'
                        if phys_name in cols_to_update:
                            p_idx = cols_to_update.index(phys_name) + 1
                            p_code = str(row[p_idx] or "").strip().upper()
                            if p_code and not code_val:
                                code_val = p_code
                                
                    # Advanced offset for the trailing columns (qty, ref)
                    idx_offset = 1 + len(target_cols)
                    
                    qty_val = 1.0
                    if m_qty >= 0:
                        try:
                            import re
                            q_clean = re.sub(r'[^\d.-]', '', str(row[idx_offset]))
                            qty_val = float(q_clean) if q_clean else 1.0
                        except: pass
                        idx_offset += 1
                        
                    # Check the physical Ref column for auto-pricing
                    if m_ref >= 0:
                        ref_physical = str(row[idx_offset] or "").strip().upper()
                        if ref_physical and not code_val:
                            # If they have a native rate that precisely matches the BOQ item ref, auto-link it!
                            if ref_physical in native_rates:
                                code_val = ref_physical
                        idx_offset += 1
                    
                    try:
                        import re
                        
                        # Determine the new gross rate value
                        if code_val and code_val in native_rates:
                            # Native rate exists - use it directly (most accurate)
                            scaled_val = native_rates[code_val]
                        elif v_gross and str(v_gross).strip():
                            # Existing GrossRate - scale mathematically
                            clean_str = re.sub(r'[^\d.-]', '', str(v_gross))
                            if not clean_str: continue
                            numeric_val = float(clean_str)
                            scaled_val = numeric_val * scale_factor
                        else:
                            # No GrossRate and no native rate - skip
                            continue
                        
                        # Determine currency symbol from existing GrossRate or mapped column
                        sym = ""
                        if v_gross and str(v_gross).strip():
                            sym_match = re.search(r'^([^\d]+)', str(v_gross).strip())
                            sym = sym_match.group(1).strip() + " " if sym_match else ""
                        elif m_rate >= 0:
                            # Try mapped rate column for symbol
                            cv_rate = row[2] if len(target_cols) > 1 else None
                            if cv_rate:
                                sym_match = re.search(r'^([^\d]+)', str(cv_rate).strip())
                                sym = sym_match.group(1).strip() + " " if sym_match else ""
                            
                        new_gross = f"{sym}{scaled_val:,.2f}".strip()
                        
                        # Apply multiplier to ALL targeted columns in this row independently
                        row_update_vals = []
                        for i, col_name in enumerate(cols_to_update):
                            cv = row[i+1] # +1 because rowid is 0
                            
                            if m_amt >= 0 and col_name == f'Column {m_amt}':
                                if is_amt_linked:
                                    c_scaled = scaled_val * qty_val
                                    c_sym_match = re.search(r'^([^\d]+)', str(cv).strip())
                                    c_sym = c_sym_match.group(1).strip() + " " if c_sym_match else sym
                                    row_update_vals.append(f"{c_sym}{c_scaled:,.2f}".strip())
                                else:
                                    row_update_vals.append(cv)
                                continue
                            
                            if m_bill_rate >= 0 and col_name == f'Column {m_bill_rate}':
                                if is_rate_linked:
                                    c_sym_match = re.search(r'^([^\d]+)', str(cv).strip())
                                    c_sym = c_sym_match.group(1).strip() + " " if c_sym_match else sym
                                    row_update_vals.append(f"{c_sym}{scaled_val:,.2f}".strip())
                                else:
                                    row_update_vals.append(cv)
                                continue
                            
                            if m_rate >= 0 and col_name == f'Column {m_rate}':
                                c_sym_match = re.search(r'^([^\d]+)', str(cv).strip())
                                c_sym = c_sym_match.group(1).strip() + " " if c_sym_match else sym
                                row_update_vals.append(f"{c_sym}{scaled_val:,.2f}".strip())
                                continue
                                
                            if col_name == 'GrossRate':
                                row_update_vals.append(new_gross)
                                continue
                                
                            if col_name == 'RateCode':
                                row_update_vals.append(code_val)
                                continue
                                
                            if m_code >= 0 and col_name == f'Column {m_code}':
                                row_update_vals.append(code_val)
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
    def __init__(self, project_dir, old_overhead, old_profit, new_overhead, new_profit, old_factor=1.0, new_factor=1.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Margin Adjustment Wizard")
        
        self.project_dir = project_dir
        self.old_o = old_overhead
        self.old_p = old_profit
        self.new_o = new_overhead
        self.new_p = new_profit
        self.old_f = old_factor
        self.new_f = new_factor
        
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
        
        self.worker = MarginMigrationWorker(self.project_dir, self.old_o, self.old_p, self.new_o, self.new_p, self.old_f, self.new_f)
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
