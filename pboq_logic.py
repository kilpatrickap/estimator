import os
import sqlite3
import json
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

class PBOQLogic:
    """Handles database interactions and business logic for the PBOQ viewer."""
    
    @staticmethod
    def connect_db(file_path):
        if not file_path or not os.path.exists(file_path):
            return None
        return sqlite3.connect(file_path)

    @staticmethod
    def ensure_schema(conn):
        cursor = conn.cursor()
        # Check for pboq_items table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_items';")
        if not cursor.fetchone():
            return False, "This database does not contain valid PBOQ data."
        
        # Get column info
        cursor.execute("PRAGMA table_info(pboq_items)")
        db_columns = [info[1] for info in cursor.fetchall()]
        
        # Ensure Standard Columns 0-13 exist for consistent mapping
        for i in range(14):
            col_name = f"Column {i}"
            if col_name not in db_columns:
                cursor.execute(f"ALTER TABLE pboq_items ADD COLUMN \"{col_name}\" TEXT")
                db_columns.append(col_name)

        # Ensure Named logical columns exist for internal logic fallback
        named_cols = ["GrossRate", "RateCode", "PlugRate", "PlugCode", "PlugFormula", 
                      "PlugCategory", "PlugCurrency", "PlugExchangeRates",
                      "SubbeePackage", "SubbeeName", "SubbeeRate", "SubbeeMarkup"]
        
        for nc in named_cols:
            if nc not in db_columns:
                cursor.execute(f"ALTER TABLE pboq_items ADD COLUMN {nc} TEXT")
                db_columns.append(nc)
        
        # Ensure Formatting table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pboq_formatting (
                row_idx INTEGER,
                col_idx INTEGER,
                fmt_json TEXT,
                PRIMARY KEY (row_idx, col_idx)
            )
        """)
        
        # Ensure Subcontractor Quotes table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subcontractor_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_name TEXT,
                row_idx INTEGER,
                subcontractor_name TEXT,
                rate REAL,
                FOREIGN KEY(row_idx) REFERENCES pboq_items(rowid)
            )
        """)
        
        conn.commit()
        return True, db_columns

    @staticmethod
    def load_formatting(conn):
        formatting_data = {}
        cursor = conn.cursor()
        cursor.execute("SELECT row_idx, col_idx, fmt_json FROM pboq_formatting")
        for row_idx, col_idx, fmt_json in cursor.fetchall():
            formatting_data[(row_idx, col_idx)] = json.loads(fmt_json)
        return formatting_data



    @staticmethod
    def persist_batch_updates(file_path, db_cols, col_idx_in_display, updates):
        """Helper to batch update PBOQ items in the database by rowid."""
        if not file_path or not os.path.exists(file_path): return False
        
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # col_idx_in_display is 0-based index of the column in the displayed table (e.g., 0-7)
            # db_cols includes 'Sheet' at index 0, then 'Column 0', 'Column 1', etc.
            db_col_index = col_idx_in_display + 1 
            db_col_to_update = db_cols[db_col_index] if db_col_index < len(db_cols) else None
            
            if db_col_to_update:
                for rowid, val in updates:
                    cursor.execute(f'UPDATE pboq_items SET "{db_col_to_update}" = ? WHERE rowid = ?', (val, rowid))
                conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Update Error: {e}")
            return False

    @staticmethod
    def persist_cell_formatting(file_path, global_row_idx, col_idx, bg_color=None, fg_color=None, bold=None):
        """Persists cell-level formatting (colors, bold) to the pboq_formatting table."""
        if not file_path or not os.path.exists(file_path): return
        
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT fmt_json FROM pboq_formatting WHERE row_idx=? AND col_idx=?", (global_row_idx, col_idx))
            row = cursor.fetchone()
            fmt = json.loads(row[0]) if row else {}
            
            if bg_color: fmt['bg_color'] = bg_color if isinstance(bg_color, str) else bg_color.name()
            if fg_color: fmt['font_color'] = fg_color if isinstance(fg_color, str) else fg_color.name()
            if bold is not None: fmt['bold'] = bold
            
            cursor.execute("INSERT OR REPLACE INTO pboq_formatting (row_idx, col_idx, fmt_json) VALUES (?, ?, ?)", 
                         (global_row_idx, col_idx, json.dumps(fmt)))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error persisting cell formatting: {e}")

    @staticmethod
    def persist_batch_cell_formatting(file_path, col_idx, updates):
        """Batch persist formatting for multiple rows in one column. 
        Updates is a list of (global_row_idx, {fmt_dict})"""
        if not file_path or not os.path.exists(file_path): return
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            for g_idx, fmt in updates:
                cursor.execute("SELECT fmt_json FROM pboq_formatting WHERE row_idx=? AND col_idx=?", (g_idx, col_idx))
                row = cursor.fetchone()
                existing_fmt = json.loads(row[0]) if row else {}
                existing_fmt.update(fmt)
                
                cursor.execute("INSERT OR REPLACE INTO pboq_formatting (row_idx, col_idx, fmt_json) VALUES (?, ?, ?)", 
                             (g_idx, col_idx, json.dumps(existing_fmt)))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error batch persisting formatting: {e}")

    @staticmethod
    def clear_cell_formatting(file_path, global_row_idx, col_idx):
        if not file_path or not os.path.exists(file_path): return
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pboq_formatting WHERE row_idx=? AND col_idx=?", (global_row_idx, col_idx))
            conn.commit()
            conn.close()
        except Exception:
            pass


