# database.py

import sqlite3
import os
from datetime import datetime
from models import Task, Estimate


DB_FILE = "construction_costs.db"


class DatabaseManager:
    """Manages all interactions with the SQLite database."""

    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        if not os.path.exists(self.db_file):
            self._init_db()
        else:
            self._migrate_db()

    def _migrate_db(self):
        """Adds missing columns to the database if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Check if grand_total column exists in estimates table
            cursor.execute("PRAGMA table_info(estimates)")
            columns = [info['name'] for info in cursor.fetchall()]

            if 'grand_total' not in columns:
                cursor.execute("ALTER TABLE estimates ADD COLUMN grand_total REAL DEFAULT 0.0")
                conn.commit()

            # Create settings table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            conn.commit()

            # Check if currency column exists in materials table
            cursor.execute("PRAGMA table_info(materials)")
            columns = [info['name'] for info in cursor.fetchall()]
            if 'currency' not in columns:
                cursor.execute("ALTER TABLE materials ADD COLUMN currency TEXT DEFAULT 'GHS (₵)'")
                conn.commit()

            # Check if currency column exists in labor table
            cursor.execute("PRAGMA table_info(labor)")
            columns = [info['name'] for info in cursor.fetchall()]
            if 'currency' not in columns:
                cursor.execute("ALTER TABLE labor ADD COLUMN currency TEXT DEFAULT 'GHS (₵)'")
                conn.commit()

            # Check if currency column exists in equipment table
            cursor.execute("PRAGMA table_info(equipment)")
            columns = [info['name'] for info in cursor.fetchall()]
            if 'currency' not in columns:
                cursor.execute("ALTER TABLE equipment ADD COLUMN currency TEXT DEFAULT 'GHS (₵)'")
                conn.commit()

            # Add Date, Location, Remarks to materials, labor, and equipment
            for table in ['materials', 'labor', 'equipment']:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [info['name'] for info in cursor.fetchall()]
                if 'date_added' not in columns:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN date_added TEXT")
                if 'location' not in columns:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN location TEXT")
                if 'remarks' not in columns:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN remarks TEXT")
                if 'contact' not in columns:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN contact TEXT")
                conn.commit()
        except sqlite3.Error:
            pass
        finally:
            conn.close()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")  # Enforce foreign key constraints
        return conn

    def _init_db(self):
        """Initializes the database schema and populates with sample data."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # --- Core Cost Tables ---
        cursor.execute('CREATE TABLE materials (id INTEGER PRIMARY KEY, name TEXT UNIQUE, unit TEXT, currency TEXT DEFAULT "GHS (₵)", price REAL, date_added TEXT, location TEXT, contact TEXT, remarks TEXT)')
        cursor.execute('CREATE TABLE labor (id INTEGER PRIMARY KEY, trade TEXT UNIQUE, currency TEXT DEFAULT "GHS (₵)", rate_per_hour REAL, date_added TEXT, location TEXT, contact TEXT, remarks TEXT)')
        cursor.execute('CREATE TABLE equipment (id INTEGER PRIMARY KEY, name TEXT UNIQUE, currency TEXT DEFAULT "GHS (₵)", rate_per_hour REAL, date_added TEXT, location TEXT, contact TEXT, remarks TEXT)')
        
        # --- Settings Table ---
        cursor.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)')

        # --- Estimate Storage Tables (Updated Schema) ---
        cursor.execute('''
            CREATE TABLE estimates (
                id INTEGER PRIMARY KEY,
                project_name TEXT,
                client_name TEXT,
                overhead_percent REAL,
                profit_margin_percent REAL,
                currency TEXT,
                date_created TEXT,
                grand_total REAL DEFAULT 0.0
            )
        ''')
        cursor.execute('''
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                estimate_id INTEGER NOT NULL,
                description TEXT,
                FOREIGN KEY(estimate_id) REFERENCES estimates(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE estimate_materials (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                material_id INTEGER NOT NULL,
                quantity REAL,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY(material_id) REFERENCES materials(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE estimate_labor (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                labor_id INTEGER NOT NULL,
                hours REAL,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY(labor_id) REFERENCES labor(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE estimate_equipment (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                equipment_id INTEGER NOT NULL,
                hours REAL,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY(equipment_id) REFERENCES equipment(id) ON DELETE CASCADE
            )
        ''')

        # Sample Data
        sample_materials = [
            ('Concrete 3000 PSI', 'cubic_yard', 'GHS (₵)', 150.00, datetime.now().strftime('%Y-%m-%d'), 'Accra', 'Standard mix'),
            ('2x4 Lumber 8ft', 'each', 'GHS (₵)', 4.50, datetime.now().strftime('%Y-%m-%d'), 'Kumasi', 'Treated pine'),
            ('1/2" Drywall Sheet 4x8', 'sheet', 'GHS (₵)', 12.00, datetime.now().strftime('%Y-%m-%d'), 'Accra', 'Moisture resistant'),
            ('Latex Paint', 'gallon', 'GHS (₵)', 35.00, datetime.now().strftime('%Y-%m-%d'), 'Tema', 'Interior silk')
        ]
        sample_labor = [
            ('General Laborer', 'GHS (₵)', 25.00, datetime.now().strftime('%Y-%m-%d'), 'Nationwide', '-'),
            ('Carpenter', 'GHS (₵)', 45.00, datetime.now().strftime('%Y-%m-%d'), 'Accra', 'Experienced'),
            ('Electrician', 'GHS (₵)', 65.00, datetime.now().strftime('%Y-%m-%d'), 'Kumasi', 'Certified'),
            ('Painter', 'GHS (₵)', 35.00, datetime.now().strftime('%Y-%m-%d'), 'Tema', '-')
        ]
        sample_equipment = [
            ('Skid Steer', 'GHS (₵)', 75.00, datetime.now().strftime('%Y-%m-%d'), 'Rental Depot', 'Daily rate'),
            ('Excavator', 'GHS (₵)', 120.00, datetime.now().strftime('%Y-%m-%d'), 'Project Site', 'Hourly with fuel'),
            ('Concrete Mixer', 'GHS (₵)', 40.00, datetime.now().strftime('%Y-%m-%d'), 'Warehouse', '-'),
            ('Scissor Lift', 'GHS (₵)', 60.00, datetime.now().strftime('%Y-%m-%d'), 'Rental Depot', '19ft reach')
        ]
        cursor.executemany('INSERT INTO materials (name, unit, currency, price, date_added, location, remarks) VALUES (?,?,?,?,?,?,?)', sample_materials)
        cursor.executemany('INSERT INTO labor (trade, currency, rate_per_hour, date_added, location, remarks) VALUES (?,?,?,?,?,?)', sample_labor)
        cursor.executemany('INSERT INTO equipment (name, currency, rate_per_hour, date_added, location, remarks) VALUES (?,?,?,?,?,?)', sample_equipment)
        
        # Insert default settings
        cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ('currency', 'GHS (₵)'))
        cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ('overhead', '15.0'))
        cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ('profit', '10.0'))

        conn.commit()
        conn.close()

    # --- Methods for Cost Library ---
    def get_items(self, table_name):
        conn = self._get_connection()
        # Use explicit column lists to ensure consistent order regardless of migration history
        col_map = {
            'materials': 'id, name, unit, currency, price, date_added, location, contact, remarks',
            'labor': 'id, trade, currency, rate_per_hour, date_added, location, contact, remarks',
            'equipment': 'id, name, currency, rate_per_hour, date_added, location, contact, remarks'
        }
        cols = col_map.get(table_name, '*')
        sort_col = "name" if table_name in ["materials", "equipment"] else "trade"
        items = conn.cursor().execute(f"SELECT {cols} FROM {table_name} ORDER BY {sort_col}").fetchall()
        conn.close()
        return items

    def add_item(self, table_name, data):
        conn = self._get_connection()
        try:
            sql_map = {
                'materials': 'INSERT INTO materials (name, unit, currency, price, date_added, location, contact, remarks) VALUES (?,?,?,?,?,?,?,?)',
                'labor': 'INSERT INTO labor (trade, currency, rate_per_hour, date_added, location, contact, remarks) VALUES (?,?,?,?,?,?,?)',
                'equipment': 'INSERT INTO equipment (name, currency, rate_per_hour, date_added, location, contact, remarks) VALUES (?,?,?,?,?,?,?)'
            }
            sql = sql_map.get(table_name)
            if not sql: return False
            conn.cursor().execute(sql, data)
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def update_item(self, table_name, item_id, data):
        conn = self._get_connection()
        sql_map = {
            'materials': 'UPDATE materials SET name=?, unit=?, currency=?, price=?, date_added=?, location=?, contact=?, remarks=? WHERE id=?',
            'labor': 'UPDATE labor SET trade=?, currency=?, rate_per_hour=?, date_added=?, location=?, contact=?, remarks=? WHERE id=?',
            'equipment': 'UPDATE equipment SET name=?, currency=?, rate_per_hour=?, date_added=?, location=?, contact=?, remarks=? WHERE id=?'
        }
        sql = sql_map.get(table_name)
        if not sql: return
        conn.cursor().execute(sql, (*data, item_id))
        conn.commit()
        conn.close()

    def update_item_currency(self, table_name, item_id, currency):
        """Updates only the currency for a specific item in any table."""
        conn = self._get_connection()
        conn.cursor().execute(f"UPDATE {table_name} SET currency = ? WHERE id = ?", (currency, item_id))
        conn.commit()
        conn.close()

    def update_item_date(self, table_name, item_id, date_str):
        """Updates only the date for a specific item in any table."""
        conn = self._get_connection()
        conn.cursor().execute(f"UPDATE {table_name} SET date_added = ? WHERE id = ?", (date_str, item_id))
        conn.commit()
        conn.close()

    def delete_item(self, table_name, item_id):
        conn = self._get_connection()
        conn.cursor().execute(f"DELETE FROM {table_name} WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()

    def get_item_id_by_name(self, table_name, name, cursor):
        """Helper to find an ID for a given name without opening a new connection."""
        column_map = {"materials": "name", "labor": "trade", "equipment": "name"}
        column_name = column_map.get(table_name)
        if not column_name: return None
        cursor.execute(f"SELECT id FROM {table_name} WHERE {column_name} = ?", (name,))
        result = cursor.fetchone()
        return result['id'] if result else None

    # --- Methods for Saving and Loading Estimates ---
    def save_estimate(self, estimate_obj):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Calculate grand total for storage
        totals = estimate_obj.calculate_totals()
        grand_total = totals['grand_total']
        
        try:
            if estimate_obj.id:
                # 1. Update existing estimate record
                sql = """UPDATE estimates 
                         SET project_name = ?, client_name = ?, overhead_percent = ?, 
                             profit_margin_percent = ?, currency = ?, date_created = ?, grand_total = ? 
                         WHERE id = ?"""
                cursor.execute(sql, (
                    estimate_obj.project_name, estimate_obj.client_name,
                    estimate_obj.overhead_percent, estimate_obj.profit_margin_percent,
                    estimate_obj.currency, estimate_obj.date, grand_total, estimate_obj.id
                ))
                estimate_id = estimate_obj.id
                
                # Clear existing tasks to avoid duplicates - cascading deletes items too
                cursor.execute("DELETE FROM tasks WHERE estimate_id = ?", (estimate_id,))
            else:
                # 1. Save new main estimate record
                sql = "INSERT INTO estimates (project_name, client_name, overhead_percent, profit_margin_percent, currency, date_created, grand_total) VALUES (?, ?, ?, ?, ?, ?, ?)"
                cursor.execute(sql, (
                    estimate_obj.project_name, estimate_obj.client_name,
                    estimate_obj.overhead_percent, estimate_obj.profit_margin_percent,
                    estimate_obj.currency,
                    estimate_obj.date,
                    grand_total
                ))
                estimate_id = cursor.lastrowid
                estimate_obj.id = estimate_id

            # 2. Save each task and its items
            for task_obj in estimate_obj.tasks:
                cursor.execute("INSERT INTO tasks (estimate_id, description) VALUES (?, ?)",
                               (estimate_id, task_obj.description))
                task_id = cursor.lastrowid

                # Save materials
                for material in task_obj.materials:
                    material_id = self.get_item_id_by_name("materials", material['name'], cursor)
                    if material_id:
                        cursor.execute(
                            "INSERT INTO estimate_materials (task_id, material_id, quantity) VALUES (?, ?, ?)",
                            (task_id, material_id, material['qty']))

                # Save labor
                for labor in task_obj.labor:
                    labor_id = self.get_item_id_by_name("labor", labor['trade'], cursor)
                    if labor_id:
                        cursor.execute("INSERT INTO estimate_labor (task_id, labor_id, hours) VALUES (?, ?, ?)",
                                       (task_id, labor_id, labor['hours']))

                # Save equipment
                for equip in task_obj.equipment:
                    equip_id = self.get_item_id_by_name("equipment", equip['name'], cursor)
                    if equip_id:
                        cursor.execute("INSERT INTO estimate_equipment (task_id, equipment_id, hours) VALUES (?, ?, ?)",
                                       (task_id, equip_id, equip['hours']))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_saved_estimates_summary(self):
        conn = self._get_connection()
        estimates = conn.cursor().execute(
            "SELECT id, project_name, client_name, date_created FROM estimates ORDER BY date_created DESC").fetchall()
        conn.close()
        return estimates

    def load_estimate_details(self, estimate_id):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM estimates WHERE id = ?", (estimate_id,))
        est_data = cursor.fetchone()
        if not est_data: return None

        loaded_estimate = Estimate(est_data['project_name'], est_data['client_name'], est_data['overhead_percent'],
                                   est_data['profit_margin_percent'], currency=est_data['currency'] or "GHS (₵)", 
                                   date=est_data['date_created'])
        loaded_estimate.id = est_data['id']

        cursor.execute("SELECT * FROM tasks WHERE estimate_id = ?", (estimate_id,))
        tasks_data = cursor.fetchall()

        for task_data in tasks_data:
            task_obj = Task(task_data['description'])

            # Load materials
            mat_sql = """
                SELECT m.name, m.unit, m.price, em.quantity
                FROM estimate_materials em JOIN materials m ON em.material_id = m.id
                WHERE em.task_id = ?
            """
            cursor.execute(mat_sql, (task_data['id'],))
            for mat in cursor.fetchall():
                task_obj.add_material(mat['name'], mat['quantity'], mat['unit'], mat['price'])

            # Load labor
            lab_sql = """
                SELECT l.trade, l.rate_per_hour, el.hours
                FROM estimate_labor el JOIN labor l ON el.labor_id = l.id
                WHERE el.task_id = ?
            """
            cursor.execute(lab_sql, (task_data['id'],))
            for lab in cursor.fetchall():
                task_obj.add_labor(lab['trade'], lab['hours'], lab['rate_per_hour'])

            # Load equipment
            equip_sql = """
                SELECT e.name, e.rate_per_hour, ee.hours
                FROM estimate_equipment ee JOIN equipment e ON ee.equipment_id = e.id
                WHERE ee.task_id = ?
            """
            cursor.execute(equip_sql, (task_data['id'],))
            for equip in cursor.fetchall():
                task_obj.add_equipment(equip['name'], equip['hours'], equip['rate_per_hour'])

            loaded_estimate.add_task(task_obj)

        conn.close()
        return loaded_estimate

    def delete_estimate(self, estimate_id):
        """Deletes an estimate and all its associated data from the database."""
        conn = self._get_connection()
        try:
            conn.cursor().execute("DELETE FROM estimates WHERE id = ?", (estimate_id,))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error on delete: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def duplicate_estimate(self, estimate_id):
        """Duplicates an estimate by loading it, modifying it, and saving it as a new entry."""
        original_estimate = self.load_estimate_details(estimate_id)
        if not original_estimate:
            return False

        # Modify for saving as a new entry
        original_estimate.id = None  # Crucial to create a new record
        original_estimate.project_name = f"Copy of {original_estimate.project_name}"

        return self.save_estimate(original_estimate)

    # --- START OF CHANGE: New Method to Edit Estimate ---
    def update_estimate_metadata(self, estimate_id, project_name, client_name, date):
        """Updates the project name, client name, and date of an existing estimate."""
        conn = self._get_connection()
        try:
            sql = "UPDATE estimates SET project_name = ?, client_name = ?, date_created = ? WHERE id = ?"
            conn.cursor().execute(sql, (project_name, client_name, date, estimate_id))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error on update: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    # --- END OF CHANGE ---

    def get_recent_estimates(self, limit=5):
        """Retrieves the N most recent estimates."""
        conn = self._get_connection()
        try:
            sql = "SELECT id, project_name, client_name, date_created FROM estimates ORDER BY date_created DESC LIMIT ?"
            estimates = conn.cursor().execute(sql, (limit,)).fetchall()
            return estimates
        finally:
            conn.close()

    def get_total_estimates_count(self):
        """Returns the total number of estimates."""
        conn = self._get_connection()
        try:
            return conn.cursor().execute("SELECT COUNT(*) FROM estimates").fetchone()[0]
        finally:
            conn.close()

    def get_total_estimates_value(self):
        """Returns the sum of grand_total for all estimates."""
        conn = self._get_connection()
        try:
            val = conn.cursor().execute("SELECT SUM(grand_total) FROM estimates").fetchone()[0]
            return val if val else 0.0
        finally:
            conn.close()

    def get_setting(self, key, default=None):
        """Retrieves a setting value by key."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            return result['value'] if result else default
        finally:
            conn.close()

    def set_setting(self, key, value):
        """Sets a setting value."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()
            return True
        finally:
            conn.close()
