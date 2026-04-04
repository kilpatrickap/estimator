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
            
            self.progress.emit(100, "Migration Complete.")
            self.finished_mig.emit(True, "All existing Gross Rates have been mathematically scaled to reflect new Overhead & Profit.")
        except Exception as e:
            self.finished_mig.emit(False, str(e))

    def _migrate_pboq_gross_rates(self, scale_factor):
        pboq_dir = os.path.join(self.project_dir, "Priced BOQs")
        if not os.path.exists(pboq_dir): return
        
        for f in os.listdir(pboq_dir):
            if not f.endswith('.db'): continue
            
            db_path = os.path.join(pboq_dir, f)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                # Check if GrossRate exists
                cursor.execute("PRAGMA table_info(pboq_items)")
                db_cols = [info[1] for info in cursor.fetchall()]
                
                if "GrossRate" not in db_cols:
                    conn.close()
                    continue
                    
                cursor.execute('SELECT rowid, "GrossRate" FROM pboq_items WHERE "GrossRate" IS NOT NULL AND "GrossRate" != ""')
                rows = cursor.fetchall()
                
                updates = []
                for row in rows:
                    rowid = row[0]
                    v = row[1]
                    try:
                        numeric_val = float(str(v).replace(',', ''))
                        scaled_val = numeric_val * scale_factor
                        formatted_val = f"{scaled_val:,.2f}"
                        updates.append((formatted_val, rowid))
                    except ValueError:
                        pass
                
                if updates:
                    cursor.executemany('UPDATE pboq_items SET "GrossRate" = ? WHERE rowid = ?', updates)
                    
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
