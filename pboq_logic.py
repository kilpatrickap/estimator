import os
import sqlite3
import json
import re
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

class PBOQLogic:
    """Handles database interactions and business logic for the PBOQ viewer."""

    @staticmethod
    def evaluate_formula(formula_text):
        """Evaluates a multi-line PBOQ formula string to a single float value."""
        if not formula_text: return 0.0
        lines = formula_text.split('\n')
        total_sum = 0
        for line in lines:
            val = PBOQLogic.parse_single_line(line)
            if val is not None:
                total_sum += val
        return total_sum

    @staticmethod
    def parse_single_line(text):
        trimmed = text.strip()
        if not trimmed: return None
        is_formula = trimmed.startswith('=')
        segment = text.split(';')[0]
        if not is_formula:
            try: return float(segment.strip().replace(',',''))
            except ValueError: return None
        term = segment.replace('=', '', 1)
        term = re.sub(r'"[^"]*"', '', term)
        term = term.replace('x', '*').replace('X', '*').replace('%', '/100')
        term = re.sub(r'/\s*[a-zA-Z\u00b2\u00b3]+[a-zA-Z\u00b2\u00b3\d]*', '', term)
        term = re.sub(r'[a-zA-Z\u00b2\u00b3]+[a-zA-Z\u00b2\u00b3\d]*', '', term)
        try:
            cleaned_term = re.sub(r'[^0-9+\-*/(). ]', '', term)
            return float(eval(cleaned_term, {"__builtins__": None}, {}))
        except: return None
    
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
        
        # Standard Columns and Named Columns in a fixed preferred order
        standard_cols = [f"Column {i}" for i in range(20)]
        named_cols = ["GrossRate", "RateCode", "PlugRate", "PlugCode", "PlugFormula", "PlugFactor", 
                      "PlugCategory", "PlugCurrency", "PlugExchangeRates",
                      "ProvSum", "ProvSumCode", "ProvSumFormula", "ProvSumCategory", "ProvSumCurrency", "ProvSumExchangeRates",
                      "PCSum", "PCSumCode", "PCSumFormula", "PCSumCategory", "PCSumCurrency", "PCSumExchangeRates",
                      "Daywork", "DayworkCode", "DayworkFormula", "DayworkCategory", "DayworkCurrency", "DayworkExchangeRates",
                      "SubbeePackage", "SubbeeName", "SubbeeRate", "SubbeeMarkup", "SubbeeNotes",
                      "SubbeeCategory", "SubbeeCode", "IsFlagged"]
        
        for col_name in standard_cols + named_cols:
            if col_name not in db_columns:
                cursor.execute(f"ALTER TABLE pboq_items ADD COLUMN \"{col_name}\" TEXT")
                db_columns.append(col_name)

        
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
        
        # Ensure Subcontractor Package Metadata Table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subcontractor_package_settings (
                package_name TEXT PRIMARY KEY,
                category_name TEXT,
                markup_default REAL,
                notes TEXT
            )
        """)
        
        # Ensure Subcontractor Details table exists for contact info
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subcontractor_details (
                name TEXT PRIMARY KEY,
                phone TEXT,
                email TEXT
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
    def persist_batch_named_updates(file_path, col_name, updates):
        """Updates a named column (like SubbeeName) directly by rowid."""
        if not file_path or not os.path.exists(file_path): return False
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            for rowid, val in updates:
                cursor.execute(f'UPDATE pboq_items SET "{col_name}" = ? WHERE rowid = ?', (val, rowid))
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error: return False

    @staticmethod
    def toggle_flag(file_path, rowid, current_state):
        """Toggles the IsFlagged status for a specific row."""
        new_state = 1 if not current_state else 0
        return PBOQLogic.persist_batch_named_updates(file_path, "IsFlagged", [(rowid, new_state)]), new_state

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


    @staticmethod
    def get_package_settings(db_path):
        """Loads all package-specific settings (categories/markups) from the DB."""
        if not db_path or not os.path.exists(db_path): return {}
        settings = {}
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT package_name, category_name, markup_default, notes FROM subcontractor_package_settings")
            for pkg, cat, mk, notes in cursor.fetchall():
                settings[pkg] = {'category': cat, 'markup': mk, 'notes': notes}
            conn.close()
        except: pass
        return settings

    @staticmethod
    def save_package_settings(db_path, settings_dict):
        """Bulk saves package meta-data like category mappings."""
        if not db_path or not os.path.exists(db_path): return
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            for pkg, data in settings_dict.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO subcontractor_package_settings (package_name, category_name, markup_default, notes)
                    VALUES (?, ?, ?, ?)
                """, (pkg, data.get('category', ''), data.get('markup', 0.0), data.get('notes', '')))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving package settings: {e}")

    @staticmethod
    def bulk_update_currencies(file_path, new_currency):
        """Updates all logical currency columns in the PBOQ database."""
        if not file_path or not os.path.exists(file_path): return
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            cols = ["PlugCurrency", "ProvSumCurrency", "PCSumCurrency", "DayworkCurrency"]
            
            cursor.execute(f"PRAGMA table_info(pboq_items)")
            db_cols = [info[1] for info in cursor.fetchall()]
            
            update_frags = []
            for col in cols:
                if col in db_cols:
                    update_frags.append(f'"{col}" = ?')
            
            if update_frags:
                cursor.execute(f'UPDATE pboq_items SET {", ".join(update_frags)}', [new_currency] * len(update_frags))
                conn.commit()
            conn.close()
        except Exception as e:
            print(f"PBOQ Currency Update Error: {e}")
