# database.py

import sqlite3
import os
from datetime import datetime
from models import Task, Estimate


CATEGORY_PREFIXES = {
    "Preliminaries": "PRLM",
    "Earthworks": "ETWK",
    "Concrete": "CONC",
    "Formwork": "FMWK",
    "Reinforcement": "RFMT",
    "Structural Steelwork": "STLS",
    "Blockwork": "WALL",
    "Flooring": "FLRG",
    "Doors & Windows": "DRWD",
    "Plastering": "PLST",
    "Painting": "PNTG",
    "Roadwork & Fencing": "RDWK",
    "Miscellaneous": "MISC",
    "External Works": "EXWK",
    "Mechanical Works": "MECH",
    "Electrical Works": "ELEC",
    "Plumbing Works": "PLBG",
    "Heating/Ventilation & AirConditioning": "HVAC"
}


DB_FILE = "construction_costs.db"


class DatabaseManager:
    """Manages all interactions with the SQLite database."""

    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        if not os.path.exists(self.db_file):
            self._init_db()
        else:
            self._migrate_db()

    def _get_connection(self):
        """Establishes and returns a database connection."""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")  # Enforce foreign key constraints
        return conn

    def _ensure_column(self, cursor, table, column, definition):
        """Helper to safely add a column if it doesn't exist."""
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [info['name'] for info in cursor.fetchall()]
        if column not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
            return True
        return False

    def _migrate_db(self):
        """Updates the database schema to the latest version."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # 1. Update 'estimates' table
            self._ensure_column(cursor, "estimates", "grand_total", "grand_total REAL DEFAULT 0.0")
            self._ensure_column(cursor, "estimates", "net_total", "net_total REAL DEFAULT 0.0")
            
            # Legacy Rename: rate_id to rate_code
            cursor.execute("PRAGMA table_info(estimates)")
            cols = [info['name'] for info in cursor.fetchall()]
            if 'rate_id' in cols and 'rate_code' not in cols:
                try:
                    cursor.execute("ALTER TABLE estimates RENAME COLUMN rate_id TO rate_code")
                except:
                    self._ensure_column(cursor, "estimates", "rate_code", "rate_code TEXT")
                    cursor.execute("UPDATE estimates SET rate_code = rate_id")
            else:
                self._ensure_column(cursor, "estimates", "rate_code", "rate_code TEXT")
                
            self._ensure_column(cursor, "estimates", "unit", "unit TEXT")
            self._ensure_column(cursor, "estimates", "notes", "notes TEXT")
            self._ensure_column(cursor, "estimates", "adjustment_factor", "adjustment_factor REAL DEFAULT 1.0")
            self._ensure_column(cursor, "estimates", "category", "category TEXT")

            # Data migration: Copy remarks to notes if remarks exists and notes is empty
            cursor.execute("PRAGMA table_info(estimates)")
            est_cols = [info['name'] for info in cursor.fetchall()]
            if 'remarks' in est_cols:
                cursor.execute("UPDATE estimates SET notes = remarks WHERE notes IS NULL OR notes = ''")

            # 2. Create 'settings' table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')

            # 3. Update core resource tables (materials, labor, equipment, plant, indirect_costs)
            resource_tables = ['materials', 'labor', 'equipment', 'plant', 'indirect_costs']
            common_cols = [
                ('currency', "TEXT DEFAULT 'GHS (₵)'"),
                ('date_added', "TEXT"),
                ('location', "TEXT"),
                ('remarks', "TEXT"),
                ('contact', "TEXT"),
                ('unit', "TEXT DEFAULT 'hr'"),
                ('formula', "TEXT")
            ]
            
            for table in resource_tables:
                # Ensure table exists first for 'plant' or 'indirect_costs' which might be new
                if table == 'plant':
                    cursor.execute('CREATE TABLE IF NOT EXISTS plant (id INTEGER PRIMARY KEY, name TEXT UNIQUE, unit TEXT DEFAULT "hr", currency TEXT DEFAULT "GHS (₵)", rate REAL, formula TEXT, date_added TEXT, location TEXT, contact TEXT, remarks TEXT)')
                elif table == 'indirect_costs':
                    cursor.execute('CREATE TABLE IF NOT EXISTS indirect_costs (id INTEGER PRIMARY KEY, description TEXT UNIQUE, unit TEXT, currency TEXT DEFAULT "GHS (₵)", amount REAL, formula TEXT, date_added TEXT)')
                
                for col_name, col_def in common_cols:
                    # Skip common columns if they don't apply to indirect_costs specifically if we want to keep it lean, 
                    # but easiest is to just let _ensure_column handle it if we want them there.
                    # User only asked for: Description, Unit, Currency, Amount, Date.
                    if table == 'indirect_costs' and col_name in ['location', 'remarks', 'contact']:
                        continue
                    self._ensure_column(cursor, table, col_name, f"{col_name} {col_def}")
                
                # Rename rate_per_hour to rate if it exists
                if table in ['labor', 'equipment', 'plant']:
                    cursor.execute(f"PRAGMA table_info({table})")
                    cols = [info['name'] for info in cursor.fetchall()]
                    if 'rate_per_hour' in cols and 'rate' not in cols:
                        try:
                            cursor.execute(f"ALTER TABLE {table} RENAME COLUMN rate_per_hour TO rate")
                        except sqlite3.OperationalError:
                            # Fallback if RENAME COLUMN is not supported
                            cursor.execute(f"ALTER TABLE {table} ADD COLUMN rate REAL")
                            cursor.execute(f"UPDATE {table} SET rate = rate_per_hour")

            # 4. Update estimate item tables
            item_tables = ['estimate_materials', 'estimate_labor', 'estimate_equipment', 'estimate_plant', 'estimate_indirect_costs']
            for table in item_tables:
                if table == 'estimate_plant':
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS estimate_plant (
                            id INTEGER PRIMARY KEY,
                            task_id INTEGER NOT NULL,
                            plant_id INTEGER,
                            hours REAL,
                            formula TEXT,
                            name_trade TEXT,
                            unit TEXT,
                            rate REAL,
                            currency TEXT,
                            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                        )
                    ''')
                elif table == 'estimate_indirect_costs':
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS estimate_indirect_costs (
                            id INTEGER PRIMARY KEY,
                            task_id INTEGER NOT NULL,
                            indirect_id INTEGER,
                            amount REAL,
                            formula TEXT,
                            description TEXT,
                            unit TEXT,
                            currency TEXT,
                            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                        )
                    ''')

                self._ensure_column(cursor, table, "formula", "formula TEXT")
                self._ensure_column(cursor, table, "unit", "unit TEXT")
                if table == "estimate_materials":
                    self._ensure_column(cursor, table, "name", "name TEXT")
                    self._ensure_column(cursor, table, "price", "price REAL")
                    self._ensure_column(cursor, table, "currency", "currency TEXT")
                elif table == "estimate_indirect_costs":
                    self._ensure_column(cursor, table, "description", "description TEXT")
                    self._ensure_column(cursor, table, "amount", "amount REAL")
                    self._ensure_column(cursor, table, "currency", "currency TEXT")
                else:
                    self._ensure_column(cursor, table, "name_trade", "name_trade TEXT")
                    self._ensure_column(cursor, table, "rate", "rate REAL")
                    self._ensure_column(cursor, table, "currency", "currency TEXT")
            
            # 5. Fix constraints on estimate items (remove NOT NULL and Library FKs)
            for table, id_col in [("estimate_materials", "material_id"), ("estimate_labor", "labor_id"), ("estimate_equipment", "equipment_id"), ("estimate_plant", "plant_id"), ("estimate_indirect_costs", "indirect_id")]:
                self._repair_estimate_items_schema(cursor, table, id_col)

            # 5. Create 'estimate_exchange_rates' table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS estimate_exchange_rates (
                    id INTEGER PRIMARY KEY,
                    estimate_id INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    rate REAL DEFAULT 1.0,
                    date TEXT,
                    operator TEXT DEFAULT '*',
                    FOREIGN KEY(estimate_id) REFERENCES estimates(id) ON DELETE CASCADE
                )
            ''')
            self._ensure_column(cursor, "estimate_exchange_rates", "operator", "operator TEXT DEFAULT '*'")
            
            # Ensure new estimate cols
            self._ensure_column(cursor, "estimates", "rate_type", "rate_type TEXT DEFAULT 'Simple'")

            conn.commit()
        except sqlite3.Error as e:
            print(f"Migration Error: {e}")
        finally:
            conn.close()

    def _repair_estimate_items_schema(self, cursor, table_name, id_col):
        """Removes NOT NULL and FOREIGN KEY constraints on the resource link column in SQLite."""
        cursor.execute(f"PRAGMA table_info({table_name})")
        info = cursor.fetchall()
        if not info: return 

        schema = {i['name']: i for i in info}
        target_col = schema.get(id_col)
        
        cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        fks = cursor.fetchall()
        has_library_fk = any(fk['table'] in ["materials", "labor", "equipment", "plant"] for fk in fks)

        if (target_col and target_col['notnull'] == 1) or has_library_fk:
            print(f"Repairing schema for {table_name} to allow NULL links and remove library FKs...")
            
            if table_name == "estimate_materials":
                creation_sql = f'''
                    CREATE TABLE {table_name}_new (
                        id INTEGER PRIMARY KEY,
                        task_id INTEGER NOT NULL,
                        {id_col} INTEGER,
                        quantity REAL,
                        formula TEXT,
                        name TEXT,
                        unit TEXT,
                        price REAL,
                        currency TEXT,
                        FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                    )
                '''
            elif table_name == "estimate_indirect_costs":
                creation_sql = f'''
                    CREATE TABLE {table_name}_new (
                        id INTEGER PRIMARY KEY,
                        task_id INTEGER NOT NULL,
                        {id_col} INTEGER,
                        amount REAL,
                        formula TEXT,
                        description TEXT,
                        unit TEXT,
                        currency TEXT,
                        FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                    )
                '''
            else:
                creation_sql = f'''
                    CREATE TABLE {table_name}_new (
                        id INTEGER PRIMARY KEY,
                        task_id INTEGER NOT NULL,
                        {id_col} INTEGER,
                        hours REAL,
                        formula TEXT,
                        name_trade TEXT,
                        unit TEXT,
                        rate REAL,
                        currency TEXT,
                        FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                    )
                '''
            
            cursor.execute(creation_sql)
            
            # Get common columns for data transfer
            cols = [i['name'] for i in info]
            cursor.execute(f"PRAGMA table_info({table_name}_new)")
            new_cols = [n['name'] for n in cursor.fetchall()]
            common = [c for c in cols if c in new_cols]
            col_str = ", ".join(common)
            
            cursor.execute(f"INSERT INTO {table_name}_new ({col_str}) SELECT {col_str} FROM {table_name}")
            cursor.execute(f"DROP TABLE {table_name}")
            cursor.execute(f"ALTER TABLE {table_name}_new RENAME TO {table_name}")

    def _init_db(self):
        """
        Initializes the database schema and populates with sample data.
        Call this only if the DB file does not exist.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # --- Core Cost Tables ---
        cursor.execute('CREATE TABLE materials (id INTEGER PRIMARY KEY, name TEXT UNIQUE, unit TEXT, currency TEXT DEFAULT "GHS (₵)", price REAL, formula TEXT, date_added TEXT, location TEXT, contact TEXT, remarks TEXT)')
        cursor.execute('CREATE TABLE labor (id INTEGER PRIMARY KEY, trade TEXT UNIQUE, unit TEXT, currency TEXT DEFAULT "GHS (₵)", rate REAL, formula TEXT, date_added TEXT, location TEXT, contact TEXT, remarks TEXT)')
        cursor.execute('CREATE TABLE equipment (id INTEGER PRIMARY KEY, name TEXT UNIQUE, unit TEXT, currency TEXT DEFAULT "GHS (₵)", rate REAL, formula TEXT, date_added TEXT, location TEXT, contact TEXT, remarks TEXT)')
        cursor.execute('CREATE TABLE plant (id INTEGER PRIMARY KEY, name TEXT UNIQUE, unit TEXT, currency TEXT DEFAULT "GHS (₵)", rate REAL, formula TEXT, date_added TEXT, location TEXT, contact TEXT, remarks TEXT)')
        cursor.execute('CREATE TABLE indirect_costs (id INTEGER PRIMARY KEY, description TEXT UNIQUE, unit TEXT, currency TEXT DEFAULT "GHS (₵)", amount REAL, formula TEXT, date_added TEXT)')
        
        # --- Settings Table ---
        cursor.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)')

        # --- Estimate Storage Tables ---
        cursor.execute('''
            CREATE TABLE estimates (
                id INTEGER PRIMARY KEY,
                project_name TEXT,
                client_name TEXT,
                overhead_percent REAL,
                profit_margin_percent REAL,
                currency TEXT,
                date_created TEXT,
                grand_total REAL DEFAULT 0.0,
                net_total REAL DEFAULT 0.0,
                rate_code TEXT,
                unit TEXT,
                notes TEXT,
                adjustment_factor REAL DEFAULT 1.0,
                category TEXT,
                rate_type TEXT DEFAULT 'Simple'
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
                material_id INTEGER,
                quantity REAL,
                formula TEXT,
                name TEXT,
                unit TEXT,
                price REAL,
                currency TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE estimate_labor (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                labor_id INTEGER,
                hours REAL,
                formula TEXT,
                name_trade TEXT,
                unit TEXT,
                rate REAL,
                currency TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE estimate_equipment (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                equipment_id INTEGER,
                hours REAL,
                formula TEXT,
                name_trade TEXT,
                unit TEXT,
                rate REAL,
                currency TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE estimate_plant (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                plant_id INTEGER,
                hours REAL,
                formula TEXT,
                name_trade TEXT,
                unit TEXT,
                rate REAL,
                currency TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE estimate_indirect_costs (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                indirect_id INTEGER,
                amount REAL,
                formula TEXT,
                description TEXT,
                unit TEXT,
                currency TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE estimate_exchange_rates (
                id INTEGER PRIMARY KEY,
                estimate_id INTEGER NOT NULL,
                currency TEXT NOT NULL,
                rate REAL DEFAULT 1.0,
                date TEXT,
                operator TEXT DEFAULT '*',
                FOREIGN KEY(estimate_id) REFERENCES estimates(id) ON DELETE CASCADE
            )
        ''')

        # Insert Sample Data and Defaults
        self._insert_sample_data(cursor)
        
        conn.commit()
        conn.close()

    def _insert_sample_data(self, cursor):
        """Inserts default settings and sample cost items."""
        now = datetime.now().strftime('%Y-%m-%d')
        
        sample_materials = [
            ('Concrete 3000 PSI', 'cubic_yard', 'GHS (₵)', 150.00, now, 'Accra', 'Standard mix'),
            ('2x4 Lumber 8ft', 'each', 'GHS (₵)', 4.50, now, 'Kumasi', 'Treated pine'),
            ('1/2" Drywall Sheet 4x8', 'sheet', 'GHS (₵)', 12.00, now, 'Accra', 'Moisture resistant'),
            ('Latex Paint', 'gallon', 'GHS (₵)', 35.00, now, 'Tema', 'Interior silk')
        ]
        sample_labor = [
            ('General Laborer', 'hr', 'GHS (₵)', 25.00, now, 'Nationwide', '-'),
            ('Carpenter', 'hr', 'GHS (₵)', 45.00, now, 'Accra', 'Experienced'),
            ('Electrician', 'hr', 'GHS (₵)', 65.00, now, 'Kumasi', 'Certified'),
            ('Painter', 'hr', 'GHS (₵)', 35.00, now, 'Tema', '-')
        ]
        sample_equipment = [
            ('Skid Steer', 'hr', 'GHS (₵)', 75.00, now, 'Rental Depot', 'Daily rate'),
            ('Excavator', 'hr', 'GHS (₵)', 120.00, now, 'Project Site', 'Hourly with fuel'),
            ('Concrete Mixer', 'hr', 'GHS (₵)', 40.00, now, 'Warehouse', '-'),
            ('Scissor Lift', 'hr', 'GHS (₵)', 60.00, now, 'Rental Depot', '19ft reach')
        ]
        sample_plant = [
            ('Tower Crane', 'hr', 'GHS (₵)', 250.00, now, 'Site', 'Large capacity'),
            ('Forklift', 'hr', 'GHS (₵)', 80.00, now, 'Warehouse', '5-ton capacity'),
            ('Generator 50kVA', 'hr', 'GHS (₵)', 60.00, now, 'Site', 'Diesel powered')
        ]
        sample_indirect = [
            ('Site Supervision', 'month', 'GHS (₵)', 5000.00, now),
            ('Insurance', 'lot', 'GHS (₵)', 2000.00, now),
            ('Temporary Water', 'month', 'GHS (₵)', 300.00, now)
        ]

        cursor.executemany('INSERT INTO materials (name, unit, currency, price, date_added, location, remarks) VALUES (?,?,?,?,?,?,?)', sample_materials)
        cursor.executemany('INSERT INTO labor (trade, unit, currency, rate, date_added, location, remarks) VALUES (?,?,?,?,?,?,?)', sample_labor)
        cursor.executemany('INSERT INTO equipment (name, unit, currency, rate, date_added, location, remarks) VALUES (?,?,?,?,?,?,?)', sample_equipment)
        cursor.executemany('INSERT INTO plant (name, unit, currency, rate, date_added, location, remarks) VALUES (?,?,?,?,?,?,?)', sample_plant)
        cursor.executemany('INSERT INTO indirect_costs (description, unit, currency, amount, date_added) VALUES (?,?,?,?,?)', sample_indirect)
        
        cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ('currency', 'GHS (₵)'))
        cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ('overhead', '15.0'))
        cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ('profit', '10.0'))

    # --- Methods for Cost Library ---

    def get_items(self, table_name):
        """Retrieves all items from a specified table."""
        conn = self._get_connection()
        try:
            col_map = {
                'materials': 'id, name, unit, currency, price, formula, date_added, location, contact, remarks',
                'labor': 'id, trade, unit, currency, rate, formula, date_added, location, contact, remarks',
                'equipment': 'id, name, unit, currency, rate, formula, date_added, location, contact, remarks',
                'plant': 'id, name, unit, currency, rate, formula, date_added, location, contact, remarks',
                'indirect_costs': 'id, description, unit, currency, amount, formula, date_added'
            }
            cols = col_map.get(table_name, '*')
            sort_col = "description" if table_name == "indirect_costs" else ("name" if table_name in ["materials", "equipment", "plant"] else "trade")
            return conn.cursor().execute(f"SELECT {cols} FROM {table_name} ORDER BY {sort_col}").fetchall()
        finally:
            conn.close()

    def add_item(self, table_name, data):
        """Adds a new item to the cost library and returns its ID."""
        conn = self._get_connection()
        try:
            sql_map = {
                'materials': 'INSERT INTO materials (name, unit, currency, price, formula, date_added, location, contact, remarks) VALUES (?,?,?,?,?,?,?,?,?)',
                'labor': 'INSERT INTO labor (trade, unit, currency, rate, formula, date_added, location, contact, remarks) VALUES (?,?,?,?,?,?,?,?,?)',
                'equipment': 'INSERT INTO equipment (name, unit, currency, rate, formula, date_added, location, contact, remarks) VALUES (?,?,?,?,?,?,?,?,?)',
                'plant': 'INSERT INTO plant (name, unit, currency, rate, formula, date_added, location, contact, remarks) VALUES (?,?,?,?,?,?,?,?,?)',
                'indirect_costs': 'INSERT INTO indirect_costs (description, unit, currency, amount, formula, date_added) VALUES (?,?,?,?,?,?)'
            }
            sql = sql_map.get(table_name)
            if not sql: return None
            cursor = conn.cursor()
            cursor.execute(sql, data)
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def update_item(self, table_name, item_id, data):
        """Updates an existing item in the cost library."""
        conn = self._get_connection()
        try:
            sql_map = {
                'materials': 'UPDATE materials SET name=?, unit=?, currency=?, price=?, formula=?, date_added=?, location=?, contact=?, remarks=? WHERE id=?',
                'labor': 'UPDATE labor SET trade=?, unit=?, currency=?, rate=?, formula=?, date_added=?, location=?, contact=?, remarks=? WHERE id=?',
                'equipment': 'UPDATE equipment SET name=?, unit=?, currency=?, rate=?, formula=?, date_added=?, location=?, contact=?, remarks=? WHERE id=?',
                'plant': 'UPDATE plant SET name=?, unit=?, currency=?, rate=?, formula=?, date_added=?, location=?, contact=?, remarks=? WHERE id=?',
                'indirect_costs': 'UPDATE indirect_costs SET description=?, unit=?, currency=?, amount=?, formula=?, date_added=? WHERE id=?'
            }
            sql = sql_map.get(table_name)
            if not sql: return
            conn.cursor().execute(sql, (*data, item_id))
            conn.commit()
        finally:
            conn.close()

    def update_item_currency(self, table_name, item_id, currency):
        """Updates only the currency for a specific item."""
        self._execute_simple_update(table_name, "currency", currency, item_id)

    def update_item_date(self, table_name, item_id, date_str):
        """Updates only the date for a specific item."""
        self._execute_simple_update(table_name, "date_added", date_str, item_id)

    def update_item_field(self, table_name, column, value, item_id):
        """Updates a single field for a record in any cost library table."""
        self._execute_simple_update(table_name, column, value, item_id)

    def _execute_simple_update(self, table_name, column, value, item_id):
        conn = self._get_connection()
        try:
            conn.cursor().execute(f"UPDATE {table_name} SET {column} = ? WHERE id = ?", (value, item_id))
            conn.commit()
        finally:
            conn.close()

    def delete_item(self, table_name, item_id):
        """Deletes an item from the cost library."""
        conn = self._get_connection()
        try:
            conn.cursor().execute(f"DELETE FROM {table_name} WHERE id = ?", (item_id,))
            conn.commit()
        finally:
            conn.close()

    def get_item_id_by_name(self, table_name, name, cursor):
        """Helper to find an ID for a given name without opening a new connection."""
        column_map = {"materials": "name", "labor": "trade", "equipment": "name", "plant": "name", "indirect_costs": "description"}
        column_name = column_map.get(table_name)
        if not column_name: return None
        cursor.execute(f"SELECT id FROM {table_name} WHERE {column_name} = ?", (name,))
        result = cursor.fetchone()
        return result['id'] if result else None

    # --- Methods for Saving and Loading Estimates ---

    def save_estimate(self, estimate_obj):
        """Saves an estimate object to the database (Create or Update)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        totals = estimate_obj.calculate_totals()
        grand_total = totals['grand_total']
        net_total = totals['subtotal']
        
        try:
            if estimate_obj.id:
                # Update existing
                cursor.execute("""
                    UPDATE estimates 
                    SET project_name = ?, client_name = ?, overhead_percent = ?, 
                        profit_margin_percent = ?, currency = ?, date_created = ?, grand_total = ?, net_total = ?, rate_code = ?, unit = ?, notes = ?, adjustment_factor = ?, category = ?, rate_type = ?
                    WHERE id = ?
                """, (
                    estimate_obj.project_name, estimate_obj.client_name,
                    estimate_obj.overhead_percent, estimate_obj.profit_margin_percent,
                    estimate_obj.currency, estimate_obj.date, grand_total, net_total, 
                    estimate_obj.rate_code, estimate_obj.unit, estimate_obj.notes, 
                    estimate_obj.adjustment_factor, getattr(estimate_obj, 'category', ""), getattr(estimate_obj, 'rate_type', "Simple"), estimate_obj.id
                ))
                estimate_id = estimate_obj.id
                # Wipe tasks to rebuild tree (simplest way to handle hierarchy changes)
                cursor.execute("DELETE FROM tasks WHERE estimate_id = ?", (estimate_id,))
            else:
                # Create new
                cursor.execute("""
                    INSERT INTO estimates (project_name, client_name, overhead_percent, profit_margin_percent, currency, date_created, grand_total, net_total, rate_code, unit, notes, adjustment_factor, category, rate_type) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                estimate_obj.project_name, estimate_obj.client_name,
                estimate_obj.overhead_percent, estimate_obj.profit_margin_percent,
                estimate_obj.currency, estimate_obj.date, grand_total, net_total, 
                estimate_obj.rate_code, estimate_obj.unit, estimate_obj.notes, estimate_obj.adjustment_factor, getattr(estimate_obj, 'category', ""), getattr(estimate_obj, 'rate_type', "Simple")
                ))
                estimate_id = cursor.lastrowid
                estimate_obj.id = estimate_id

            # Save Tasks and Sub-items
            for task_obj in estimate_obj.tasks:
                cursor.execute("INSERT INTO tasks (estimate_id, description) VALUES (?, ?)", (estimate_id, task_obj.description))
                task_id = cursor.lastrowid
                
                self._save_task_items(cursor, task_id, "estimate_materials", task_obj.materials)
                self._save_task_items(cursor, task_id, "estimate_labor", task_obj.labor)
                self._save_task_items(cursor, task_id, "estimate_equipment", task_obj.equipment)
                self._save_task_items(cursor, task_id, "estimate_plant", task_obj.plant)
                self._save_task_items(cursor, task_id, "estimate_indirect_costs", task_obj.indirect_costs)
            
            # Save Exchange Rates
            cursor.execute("DELETE FROM estimate_exchange_rates WHERE estimate_id = ?", (estimate_id,))
            for curr, data in estimate_obj.exchange_rates.items():
                op = data.get('operator', '*')
                cursor.execute("INSERT INTO estimate_exchange_rates (estimate_id, currency, rate, date, operator) VALUES (?, ?, ?, ?, ?)",
                               (estimate_id, curr, data['rate'], data['date'], op))
            
            # Save Sub-Rates (linking composite rates to their sub-rates)
            cursor.execute("CREATE TABLE IF NOT EXISTS estimate_sub_rates (id INTEGER PRIMARY KEY, estimate_id INTEGER, sub_rate_id INTEGER, quantity REAL DEFAULT 1.0, formula TEXT, converted_unit TEXT, FOREIGN KEY(estimate_id) REFERENCES estimates(id) ON DELETE CASCADE)")
            self._ensure_column(cursor, "estimate_sub_rates", "converted_unit", "converted_unit TEXT")
            cursor.execute("DELETE FROM estimate_sub_rates WHERE estimate_id = ?", (estimate_id,))
            for sub_rate in estimate_obj.sub_rates:
                if sub_rate.id:
                    qty = getattr(sub_rate, 'quantity', 1.0)
                    formula = getattr(sub_rate, 'formula', None)
                    c_unit = getattr(sub_rate, 'converted_unit', None)
                    cursor.execute("INSERT INTO estimate_sub_rates (estimate_id, sub_rate_id, quantity, formula, converted_unit) VALUES (?, ?, ?, ?, ?)", (estimate_id, sub_rate.id, qty, formula, c_unit))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def _save_task_items(self, cursor, task_id, dest_table, items):
        """Helper to save list of items (materials/labor/equipment/plant) for a task."""
        
        library_table = dest_table.replace("estimate_", "") # e.g., "materials", "labor"
        
        for item in items:
            if library_table == "materials":
                source_id = self.get_item_id_by_name(library_table, item['name'], cursor)
                sql = f"""INSERT INTO {dest_table} 
                         (task_id, material_id, quantity, formula, name, unit, price, currency) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
                cursor.execute(sql, (task_id, source_id, item['qty'], item.get('formula'),
                                     item['name'], item['unit'], item['unit_cost'], item.get('currency')))
            else: # labor, equipment, plant, indirect_costs
                name_key = 'trade' if library_table == 'labor' else ('description' if library_table == 'indirect_costs' else 'name')
                ref_id_col = f"indirect_id" if library_table == 'indirect_costs' else f"{library_table}_id"
                qty_col = "amount" if library_table == 'indirect_costs' else "hours"
                rate_key = 'amount' if library_table == 'indirect_costs' else 'rate'

                source_id = self.get_item_id_by_name(library_table, item[name_key], cursor)
                sql = f"""INSERT INTO {dest_table} 
                         (task_id, {ref_id_col}, {qty_col}, formula, { 'description' if library_table == 'indirect_costs' else 'name_trade'}, unit, { 'amount' if library_table == 'indirect_costs' else 'rate'}, currency) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
                cursor.execute(sql, (task_id, source_id, item[qty_col], item.get('formula'),
                                     item[name_key], item.get('unit'), item[rate_key], item.get('currency')))

    def get_saved_estimates_summary(self):
        """Returns a summary list of all saved estimates."""
        conn = self._get_connection()
        try:
            return conn.cursor().execute("SELECT id, project_name, client_name, date_created FROM estimates ORDER BY date_created DESC").fetchall()
        finally:
            conn.close()

    def load_estimate_details(self, estimate_id):
        """Fully loads an estimate and its children from the database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM estimates WHERE id = ?", (estimate_id,))
            est_data = cursor.fetchone()
            if not est_data: return None

            loaded_estimate = Estimate(
                est_data['project_name'], est_data['client_name'], 
                est_data['overhead_percent'], est_data['profit_margin_percent'], 
                currency=est_data['currency'] or "GHS (₵)", date=est_data['date_created'],
                unit=est_data['unit'] or "", notes=est_data['notes'] or ""
            )
            loaded_estimate.id = est_data['id']
            # Defensive check for rate_code column
            try:
                loaded_estimate.rate_code = est_data['rate_code']
                loaded_estimate.adjustment_factor = est_data['adjustment_factor'] if est_data['adjustment_factor'] is not None else 1.0
                loaded_estimate.category = est_data['category'] if 'category' in est_data.keys() and est_data['category'] is not None else ""
                loaded_estimate.rate_type = est_data['rate_type'] if 'rate_type' in est_data.keys() and est_data['rate_type'] is not None else "Simple"
            except (IndexError, KeyError):
                loaded_estimate.rate_code = None
                loaded_estimate.adjustment_factor = 1.0
                loaded_estimate.category = ""
                loaded_estimate.rate_type = "Simple"

            cursor.execute("SELECT * FROM tasks WHERE estimate_id = ?", (estimate_id,))
            tasks_data = cursor.fetchall()

            for task_data in tasks_data:
                task_obj = Task(task_data['description'])
                
                # Load Materials
                mats = self._load_task_items(cursor, task_data['id'], "estimate_materials")
                for m in mats:
                    # Convert Row to dict for safe access
                    m_dict = dict(m)
                    # Fallback to library if new columns are missing/empty (for backward compatibility)
                    name = m_dict.get('name') or ""
                    unit = m_dict.get('unit') or ""
                    price = m_dict.get('price') if m_dict.get('price') is not None else 0.0
                    curr = m_dict.get('currency') or loaded_estimate.currency
                    
                    # If redundant data is missing, try join (legacy load)
                    if not name and m_dict.get('material_id'):
                         legacy = self._load_legacy_item(cursor, m_dict['material_id'], "materials")
                         if legacy:
                             name, unit, price, curr = legacy['name'], legacy['unit'], legacy['price'], legacy['currency']
                    
                    task_obj.add_material(name, m['quantity'], unit, price, currency=curr, formula=m['formula'])

                # Load Labor
                labs = self._load_task_items(cursor, task_data['id'], "estimate_labor")
                for l in labs:
                    l_dict = dict(l)
                    name = l_dict.get('name_trade') or ""
                    unit = l_dict.get('unit') or ""
                    rate = l_dict.get('rate') if l_dict.get('rate') is not None else 0.0
                    curr = l_dict.get('currency') or loaded_estimate.currency
                    
                    if not name and l_dict.get('labor_id'):
                        legacy = self._load_legacy_item(cursor, l_dict['labor_id'], "labor")
                        if legacy:
                            name, unit, rate, curr = legacy['trade'], legacy['unit'], legacy['rate'], legacy['currency']
                            
                    task_obj.add_labor(name, l['hours'], rate, currency=curr, formula=l['formula'], unit=unit)

                # Load Equipment
                equips = self._load_task_items(cursor, task_data['id'], "estimate_equipment")
                for e in equips:
                    e_dict = dict(e)
                    name = e_dict.get('name_trade') or ""
                    unit = e_dict.get('unit') or ""
                    rate = e_dict.get('rate') if e_dict.get('rate') is not None else 0.0
                    curr = e_dict.get('currency') or loaded_estimate.currency

                    if not name and e_dict.get('equipment_id'):
                        legacy = self._load_legacy_item(cursor, e_dict['equipment_id'], "equipment")
                        if legacy:
                            name, unit, rate, curr = legacy['name'], legacy['unit'], legacy['rate'], legacy['currency']

                    task_obj.add_equipment(name, e['hours'], rate, currency=curr, formula=e['formula'], unit=unit)

                # Load Plant
                plants = self._load_task_items(cursor, task_data['id'], "estimate_plant")
                for p in plants:
                    p_dict = dict(p)
                    name = p_dict.get('name_trade') or ""
                    unit = p_dict.get('unit') or ""
                    rate = p_dict.get('rate') if p_dict.get('rate') is not None else 0.0
                    curr = p_dict.get('currency') or loaded_estimate.currency
                    
                    if not name and p_dict.get('plant_id'):
                        legacy = self._load_legacy_item(cursor, p_dict['plant_id'], "plant")
                        if legacy:
                            name, unit, rate, curr = legacy['name'], legacy['unit'], legacy['rate'], legacy['currency']

                    task_obj.add_plant(name, p['hours'], rate, currency=curr, formula=p['formula'], unit=unit)

                # Load Indirect Costs
                indirects = self._load_task_items(cursor, task_data['id'], "estimate_indirect_costs")
                for ind in indirects:
                    ind_dict = dict(ind)
                    desc = ind_dict.get('description') or ""
                    unit = ind_dict.get('unit') or ""
                    amount = ind_dict.get('amount') if ind_dict.get('amount') is not None else 0.0
                    curr = ind_dict.get('currency') or loaded_estimate.currency
                    
                    if not desc and ind_dict.get('indirect_id'):
                        legacy = self._load_legacy_item(cursor, ind_dict['indirect_id'], "indirect_costs")
                        if legacy:
                            desc, unit, amount, curr = legacy['description'], legacy['unit'], legacy['amount'], legacy['currency']

                    task_obj.add_indirect_cost(desc, amount, unit=unit, currency=curr, formula=ind['formula'])

                loaded_estimate.add_task(task_obj)

            # Load Exchange Rates
            cursor.execute("SELECT currency, rate, date, operator FROM estimate_exchange_rates WHERE estimate_id = ?", (estimate_id,))
            for row in cursor.fetchall():
                loaded_estimate.exchange_rates[row['currency']] = {
                    'rate': row['rate'], 'date': row['date'], 'operator': row['operator']
                }

            # Load Sub-Rates
            loaded_estimate.sub_rates = []
            cursor.execute("CREATE TABLE IF NOT EXISTS estimate_sub_rates (id INTEGER PRIMARY KEY, estimate_id INTEGER, sub_rate_id INTEGER, quantity REAL DEFAULT 1.0, formula TEXT, converted_unit TEXT, FOREIGN KEY(estimate_id) REFERENCES estimates(id) ON DELETE CASCADE)")
            self._ensure_column(cursor, "estimate_sub_rates", "quantity", "quantity REAL DEFAULT 1.0")
            self._ensure_column(cursor, "estimate_sub_rates", "formula", "formula TEXT")
            self._ensure_column(cursor, "estimate_sub_rates", "converted_unit", "converted_unit TEXT")
            
            cursor.execute("SELECT sub_rate_id, quantity, formula, converted_unit FROM estimate_sub_rates WHERE estimate_id = ?", (estimate_id,))
            sub_rate_rows = cursor.fetchall()
            for row in sub_rate_rows:
                sub_rate_id = row['sub_rate_id']
                sub_rate = self.load_estimate_details(sub_rate_id)
                if sub_rate:
                    # Determine quantity/formula safely from sqlite row
                    sub_rate.quantity = row['quantity'] if row['quantity'] is not None else 1.0
                    sub_rate.formula = row['formula']
                    if 'converted_unit' in row.keys() and row['converted_unit']:
                        sub_rate.converted_unit = row['converted_unit']
                    loaded_estimate.add_sub_rate(sub_rate)

            return loaded_estimate
        finally:
            conn.close()

    def _load_task_items(self, cursor, task_id, link_table):
        """Helper to load items for a task directly from the estimate item table."""
        sql = f"SELECT * FROM {link_table} WHERE task_id = ?"
        cursor.execute(sql, (task_id,))
        return cursor.fetchall()

    def _load_legacy_item(self, cursor, item_id, source_table):
        """Helper for backward compatibility to load item details from library."""
        cursor.execute(f"SELECT * FROM {source_table} WHERE id = ?", (item_id,))
        return cursor.fetchone()

    def delete_estimate(self, estimate_id):
        """Deletes an estimate and all its associated data."""
        return self._execute_simple_delete("estimates", estimate_id)
        
    def _execute_simple_delete(self, table, item_id):
        conn = self._get_connection()
        try:
            conn.cursor().execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Delete Error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def duplicate_estimate(self, estimate_id):
        """Duplicates an estimate by loading it, modifying it, and saving it as a new entry."""
        original_estimate = self.load_estimate_details(estimate_id)
        if not original_estimate:
            return False

        original_estimate.id = None
        original_estimate.project_name = f"Copy of {original_estimate.project_name}"
        return self.save_estimate(original_estimate)

    def update_estimate_metadata(self, estimate_id, project_name, client_name, date):
        """Updates metadata of an existing estimate."""
        conn = self._get_connection()
        try:
            sql = "UPDATE estimates SET project_name = ?, client_name = ?, date_created = ? WHERE id = ?"
            conn.cursor().execute(sql, (project_name, client_name, date, estimate_id))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Metadata Update Error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def update_estimate_field(self, estimate_id, field, value):
        """Updates a single field for a record in the estimates table."""
        conn = self._get_connection()
        try:
            conn.cursor().execute(f"UPDATE estimates SET {field} = ? WHERE id = ?", (value, estimate_id))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Update Estimate Field Error: {e}")
            return False
        finally:
            conn.close()

    def get_recent_estimates(self, limit=5):
        """Retrieves the N most recent estimates."""
        conn = self._get_connection()
        try:
            sql = "SELECT id, project_name, client_name, date_created, grand_total FROM estimates ORDER BY date_created DESC LIMIT ?"
            return conn.cursor().execute(sql, (limit,)).fetchall()
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
            conn.cursor().execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()
            return True
        finally:
            conn.close()

    def convert_to_rate_db(self, estimate_obj):
        """Copies an estimate to construction_rates.db and assigns a Rate Code."""
        import copy
        rates_db_manager = DatabaseManager("construction_rates.db")
        
        # Clone for the new database
        rate_estimate = copy.deepcopy(estimate_obj)
        rate_estimate.id = None # New entry in the rates DB
        # Archive with current timestamp
        rate_estimate.date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Use existing category if set, otherwise default to Miscellaneous
        if not getattr(rate_estimate, 'category', ""):
            rate_estimate.category = "Miscellaneous"
            
        rate_estimate.rate_code = rates_db_manager.generate_next_rate_code(rate_estimate.category)
        
        if rates_db_manager.save_estimate(rate_estimate):
            return rate_estimate.rate_code
        return None

    def generate_next_rate_code(self, category):
        """Generates the next available Rate Code for a given category (e.g., ETWK1A)."""
        prefix = CATEGORY_PREFIXES.get(category, "MISC")
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Find all rate_codes starting with the prefix
            cursor.execute("SELECT rate_code FROM estimates WHERE rate_code LIKE ?", (f"{prefix}%",))
            codes = [row['rate_code'] for row in cursor.fetchall()]
        finally:
            conn.close()
            
        if not codes:
            return f"{prefix}1A"
            
        import re
        # Pattern: Prefix + Numbers + Single Letter
        pattern = re.compile(rf"^{re.escape(prefix)}(\d+)([A-Z])$")
        
        max_num = 0
        max_letter = 'A'
        
        valid_found = False
        for code in codes:
            if not code: continue
            match = pattern.match(code)
            if match:
                valid_found = True
                num = int(match.group(1))
                letter = match.group(2)
                if num > max_num:
                    max_num = num
                    max_letter = letter
                elif num == max_num:
                    if letter > max_letter:
                        max_letter = letter
        
        if not valid_found:
            return f"{prefix}1A"
            
        # Increment logic: ETWK1A -> ETWK1B ... ETWK1Z -> ETWK2A
        if max_letter == 'Z':
            next_num = max_num + 1
            next_letter = 'A'
        else:
            next_num = max_num
            next_letter = chr(ord(max_letter) + 1)
            
        return f"{prefix}{next_num}{next_letter}"

    def get_rates_data(self):
        """Fetches all rates from construction_rates.db for the manager window."""
        rates_db = DatabaseManager("construction_rates.db")
        conn = rates_db._get_connection()
        try:
            return conn.cursor().execute("""
                SELECT id, rate_code, project_name, unit, currency, net_total, grand_total, adjustment_factor, date_created, notes, rate_type 
                FROM estimates 
                ORDER BY rate_code ASC
            """).fetchall()
        finally:
            conn.close()
