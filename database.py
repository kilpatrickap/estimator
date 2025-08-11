# database.py

import sqlite3
import os
from datetime import datetime


# Keep the model classes here for easy access
class Task:
    def __init__(self, description):
        self.description = description
        self.materials = []
        self.labor = []
        self.equipment = []

    def add_material(self, name, quantity, unit, unit_cost):
        self.materials.append(
            {'name': name, 'qty': quantity, 'unit': unit, 'unit_cost': unit_cost, 'total': quantity * unit_cost})

    def add_labor(self, trade, hours, rate):
        self.labor.append({'trade': trade, 'hours': hours, 'rate': rate, 'total': hours * rate})

    def add_equipment(self, name, hours, rate):
        self.equipment.append({'name': name, 'hours': hours, 'rate': rate, 'total': hours * rate})

    def get_subtotal(self):
        mat_total = sum(m['total'] for m in self.materials)
        lab_total = sum(l['total'] for l in self.labor)
        equip_total = sum(e['total'] for e in self.equipment)
        return mat_total + lab_total + equip_total


class Estimate:
    def __init__(self, project_name, client_name, overhead, profit):
        self.id = None  # Will be set when loaded/saved
        self.project_name = project_name
        self.client_name = client_name
        self.overhead_percent = overhead
        self.profit_margin_percent = profit
        self.tasks = []

    def add_task(self, task): self.tasks.append(task)

    def calculate_totals(self):
        subtotal = sum(task.get_subtotal() for task in self.tasks)
        overhead_cost = subtotal * (self.overhead_percent / 100.0)
        total_cost = subtotal + overhead_cost
        profit_amount = total_cost * (self.profit_margin_percent / 100.0)
        grand_total = total_cost + profit_amount
        return {"subtotal": subtotal, "overhead": overhead_cost, "profit": profit_amount, "grand_total": grand_total}


DB_FILE = "construction_costs.db"


class DatabaseManager:
    """Manages all interactions with the SQLite database."""

    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        if not os.path.exists(self.db_file):
            self._init_db()

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
        cursor.execute('CREATE TABLE materials (id INTEGER PRIMARY KEY, name TEXT UNIQUE, unit TEXT, price REAL)')
        cursor.execute('CREATE TABLE labor (id INTEGER PRIMARY KEY, trade TEXT UNIQUE, rate_per_hour REAL)')
        cursor.execute('CREATE TABLE equipment (id INTEGER PRIMARY KEY, name TEXT UNIQUE, rate_per_hour REAL)')

        # --- Estimate Storage Tables (Updated Schema) ---
        # --- START OF FIX ---
        cursor.execute('''
            CREATE TABLE estimates (
                id INTEGER PRIMARY KEY,
                project_name TEXT,
                client_name TEXT,
                overhead_percent REAL,
                profit_margin_percent REAL,
                date_created TEXT
            )
        ''')
        # --- END OF FIX ---
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
            ('Concrete 3000 PSI', 'cubic_yard', 150.00), ('2x4 Lumber 8ft', 'each', 4.50),
            ('1/2" Drywall Sheet 4x8', 'sheet', 12.00), ('Latex Paint', 'gallon', 35.00)
        ]
        sample_labor = [
            ('General Laborer', 25.00), ('Carpenter', 45.00), ('Electrician', 65.00), ('Painter', 35.00)
        ]
        sample_equipment = [
            ('Skid Steer', 75.00), ('Excavator', 120.00), ('Concrete Mixer', 40.00), ('Scissor Lift', 60.00)
        ]
        cursor.executemany('INSERT INTO materials (name, unit, price) VALUES (?,?,?)', sample_materials)
        cursor.executemany('INSERT INTO labor (trade, rate_per_hour) VALUES (?,?)', sample_labor)
        cursor.executemany('INSERT INTO equipment (name, rate_per_hour) VALUES (?,?)', sample_equipment)

        conn.commit()
        conn.close()

    # --- Methods for Cost Library ---
    def get_items(self, table_name):
        conn = self._get_connection()
        sort_col = "name" if table_name in ["materials", "equipment"] else "trade"
        items = conn.cursor().execute(f"SELECT * FROM {table_name} ORDER BY {sort_col}").fetchall()
        conn.close()
        return items

    def add_item(self, table_name, data):
        conn = self._get_connection()
        try:
            sql_map = {
                'materials': 'INSERT INTO materials (name, unit, price) VALUES (?,?,?)',
                'labor': 'INSERT INTO labor (trade, rate_per_hour) VALUES (?,?)',
                'equipment': 'INSERT INTO equipment (name, rate_per_hour) VALUES (?,?)'
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
            'materials': 'UPDATE materials SET name=?, unit=?, price=? WHERE id=?',
            'labor': 'UPDATE labor SET trade=?, rate_per_hour=? WHERE id=?',
            'equipment': 'UPDATE equipment SET name=?, rate_per_hour=? WHERE id=?'
        }
        sql = sql_map.get(table_name)
        if not sql: return
        conn.cursor().execute(sql, (*data, item_id))
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
        try:
            # 1. Save main estimate record
            sql = "INSERT INTO estimates (project_name, client_name, overhead_percent, profit_margin_percent, date_created) VALUES (?, ?, ?, ?, ?)"
            cursor.execute(sql, (
                estimate_obj.project_name, estimate_obj.client_name,
                estimate_obj.overhead_percent, estimate_obj.profit_margin_percent,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            estimate_id = cursor.lastrowid

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
                                   est_data['profit_margin_percent'])
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