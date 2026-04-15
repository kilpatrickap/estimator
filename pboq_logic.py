import sqlite3
import json
import os
import re

class PBOQLogic:
    """Core business logic for PBOQ management, database sync, and calculations."""
    
    @staticmethod
    def connect_db(file_path):
        try:
            conn = sqlite3.connect(file_path)
            return conn
        except sqlite3.Error:
            return None

    @staticmethod
    def ensure_schema(conn):
        """Ensures the PBOQ database has the required pboq_items table and logical columns."""
        cursor = conn.cursor()
        try:
            # Check if pboq_items exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_items'")
            if not cursor.fetchone():
                return False, "Table 'pboq_items' not found in database."

            # Get physical columns (excluding logical ones we add)
            cursor.execute("PRAGMA table_info(pboq_items)")
            existing_cols = [row[1] for row in cursor.fetchall()]
            
            logical_cols = [
                ("SubbeePackage", "TEXT"), ("SubbeeName", "TEXT"), ("SubbeeRate", "FLOAT"), 
                ("SubbeeMarkup", "TEXT"), ("SubbeeCategory", "TEXT"), ("SubbeeCode", "TEXT"),
                ("ProvSum", "FLOAT"), ("ProvSumCode", "TEXT"), ("ProvSumFormula", "TEXT"), 
                ("ProvSumCategory", "TEXT"), ("ProvSumCurrency", "TEXT"), ("ProvSumExchangeRates", "TEXT"),
                ("PCSum", "FLOAT"), ("PCSumCode", "TEXT"), ("PCSumFormula", "TEXT"), 
                ("PCSumCategory", "TEXT"), ("PCSumCurrency", "TEXT"), ("PCSumExchangeRates", "TEXT"),
                ("PlugRate", "FLOAT"), ("PlugCode", "TEXT"), ("PlugFormula", "TEXT"), 
                ("PlugCategory", "TEXT"), ("PlugCurrency", "TEXT"), ("PlugExchangeRates", "TEXT"), 
                ("PlugFactor", "FLOAT"), ("GrossRate", "FLOAT"), ("RateCode", "TEXT"), ("IsFlagged", "INTEGER")
            ]
            
            for col_name, col_type in logical_cols:
                if col_name not in existing_cols:
                    cursor.execute(f'ALTER TABLE pboq_items ADD COLUMN "{col_name}" {col_type}')
            
            # Ensure pboq_formatting table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pboq_formatting (
                    global_row_idx INTEGER,
                    col_idx INTEGER,
                    format_json TEXT,
                    PRIMARY KEY (global_row_idx, col_idx)
                )
            """)

            # Ensure subcontractor_quotes table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subcontractor_quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    package_name TEXT,
                    row_idx INTEGER,
                    subcontractor_name TEXT,
                    rate FLOAT
                )
            """)

            # Ensure subcontractor_details table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subcontractor_details (
                    name TEXT PRIMARY KEY,
                    phone TEXT,
                    email TEXT
                )
            """)

            conn.commit()
            
            # Re-fetch all columns to determine which are "Physical"
            cursor.execute("PRAGMA table_info(pboq_items)")
            all_cols = [row[1] for row in cursor.fetchall()]
            
            # We want to return only the "Physical" columns (those that aren't in logical_cols)
            logical_names = [c[0] for c in logical_cols]
            physical_cols = [c for c in all_cols if c not in logical_names]
            
            return True, physical_cols
            
        except sqlite3.Error as e:
            return False, str(e)

    @staticmethod
    def load_formatting(conn):
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT global_row_idx, col_idx, format_json FROM pboq_formatting")
            rows = cursor.fetchall()
            return {(row[0], row[1]): json.loads(row[2]) for row in rows}
        except:
            return {}

    @staticmethod
    def clear_cell_formatting(file_path, g_idx, col_idx):
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pboq_formatting WHERE global_row_idx=? AND col_idx=?", (g_idx, col_idx))
            conn.commit()
            conn.close()
        except:
            pass

    @staticmethod
    def persist_batch_cell_formatting(file_path, col_idx, updates):
        """Saves a batch of cell formatting data."""
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            for g_idx, fmt in updates:
                cursor.execute("""
                    INSERT OR REPLACE INTO pboq_formatting (global_row_idx, col_idx, format_json)
                    VALUES (?, ?, ?)
                """, (g_idx, col_idx, json.dumps(fmt)))
            conn.commit()
            conn.close()
            return True
        except:
            return False

    @staticmethod
    def persist_batch_named_updates(file_path, col_name, updates):
        """Updates a specific named logical column for multiple rows."""
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            for rowid, val in updates:
                cursor.execute(f'UPDATE pboq_items SET "{col_name}" = ? WHERE rowid = ?', (val, rowid))
            conn.commit()
            conn.close()
            return True
        except:
            return False

    @staticmethod
    def persist_batch_updates(file_path, db_columns, col_idx, updates):
        """Updates a physical column by index for multiple rows."""
        try:
            # col_idx in the UI corresponds to db_columns[col_idx + 1] in many cases,
            # but we assume the caller provides the correct physical column index if needed.
            # Based on pboq_viewer mapping:
            col_name = db_columns[col_idx + 1]
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            for rowid, val in updates:
                cursor.execute(f'UPDATE pboq_items SET "{col_name}" = ? WHERE rowid = ?', (val, rowid))
            conn.commit()
            conn.close()
            return True
        except:
            return False

    @staticmethod
    def sync_rate_to_master_lib(pdb_path, items):
        """Syncs Plug, Sub, and Gross rates into the master project database."""
        if not pdb_path or not os.path.exists(pdb_path): return
        try:
            conn = sqlite3.connect(pdb_path)
            cursor = conn.cursor()
            # Ensure table exists in master
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pboq_items (
                    Description TEXT,
                    Unit TEXT,
                    RateCode TEXT,
                    GrossRate FLOAT,
                    PlugCode TEXT,
                    PlugRate FLOAT,
                    SubbeeCode TEXT,
                    SubbeeRate FLOAT,
                    SubbeeName TEXT,
                    PRIMARY KEY (Description, Unit)
                )
            """)
            for item in items:
                desc = item.get('desc')
                unit = item.get('unit')
                code = item.get('code')
                rate = item.get('rate')
                type_ = item.get('type')
                sub_name = item.get('sub_name', '')
                
                try:
                    r_float = float(str(rate).replace(',', ''))
                except:
                    r_float = 0.0

                if type_ == 'Plug Rate':
                    cursor.execute("""
                        INSERT INTO pboq_items (Description, Unit, PlugCode, PlugRate) 
                        VALUES(?, ?, ?, ?) 
                        ON CONFLICT(Description, Unit) DO UPDATE SET PlugCode=excluded.PlugCode, PlugRate=excluded.PlugRate
                    """, (desc, unit, code, r_float))
                elif type_ == 'Sub. Rate':
                    cursor.execute("""
                        INSERT INTO pboq_items (Description, Unit, SubbeeCode, SubbeeRate, SubbeeName) 
                        VALUES(?, ?, ?, ?, ?) 
                        ON CONFLICT(Description, Unit) DO UPDATE SET SubbeeCode=excluded.SubbeeCode, SubbeeRate=excluded.SubbeeRate, SubbeeName=excluded.SubbeeName
                    """, (desc, unit, code, r_float, sub_name))
                elif type_ == 'Gross Rate':
                    cursor.execute("""
                        INSERT INTO pboq_items (Description, Unit, RateCode, GrossRate) 
                        VALUES(?, ?, ?, ?) 
                        ON CONFLICT(Description, Unit) DO UPDATE SET RateCode=excluded.RateCode, GrossRate=excluded.GrossRate
                    """, (desc, unit, code, r_float))
            conn.commit()
            conn.close()
        except:
            pass

    @staticmethod
    def parse_single_line(text):
        """Parses a single line of formula text."""
        trimmed = text.strip()
        if not trimmed:
            return None
            
        is_formula = trimmed.startswith('=')
        segment = text.split(';')[0]
        
        if not is_formula:
            try:
                val = segment.strip().replace(',', '')
                return float(val)
            except ValueError:
                return None
        
        term = segment.replace('=', '', 1)
        term = re.sub(r'"[^"]*"', '', term)
        term = term.replace('x', '*').replace('X', '*').replace('%', '/100')
        term = re.sub(r'/\s*[a-zA-Z²³]+[a-zA-Z²³\d]*', '', term)
        term = re.sub(r'[a-zA-Z²³]+[a-zA-Z²³\d]*', '', term)
        
        try:
            cleaned_term = re.sub(r'[^0-9+\-*/(). ]', '', term)
            return float(eval(cleaned_term, {"__builtins__": None}, {}))
        except:
            return None

    @staticmethod
    def bulk_update_currencies(file_path, new_currency):
        """Standardized bulk update for PBOQ DBs."""
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE pboq_items SET "PlugCurrency" = ?, "ProvSumCurrency" = ?, "PCSumCurrency" = ?', 
                           (new_currency, new_currency, new_currency))
            conn.commit()
            conn.close()
        except:
            pass
