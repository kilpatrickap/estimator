# database.py

import sqlite3
import os

DB_FILE = "construction_costs.db"


class DatabaseManager:
    """Manages all interactions with the SQLite database."""

    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self.conn = None
        if not os.path.exists(self.db_file):
            self._init_db()

    def _get_connection(self):
        """Creates and returns a database connection."""
        self.conn = sqlite3.connect(self.db_file)
        self.conn.row_factory = sqlite3.Row  # Allows accessing columns by name
        return self.conn

    def _close_connection(self):
        if self.conn:
            self.conn.close()

    def _init_db(self):
        """Initializes the database schema and populates with sample data."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create Tables
        cursor.execute('CREATE TABLE materials (id INTEGER PRIMARY KEY, name TEXT UNIQUE, unit TEXT, price REAL)')
        cursor.execute('CREATE TABLE labor (id INTEGER PRIMARY KEY, trade TEXT UNIQUE, rate_per_hour REAL)')
        cursor.execute(
            'CREATE TABLE estimates (id INTEGER PRIMARY KEY, project_name TEXT, client_name TEXT, overhead REAL, profit REAL)')
        cursor.execute(
            'CREATE TABLE tasks (id INTEGER PRIMARY KEY, estimate_id INTEGER, description TEXT, FOREIGN KEY(estimate_id) REFERENCES estimates(id))')

        # Sample Data
        sample_materials = [
            ('Concrete 3000 PSI', 'cubic_yard', 150.00), ('2x4 Lumber 8ft', 'each', 4.50),
            ('1/2" Drywall Sheet 4x8', 'sheet', 12.00), ('Latex Paint', 'gallon', 35.00)
        ]
        sample_labor = [
            ('General Laborer', 25.00), ('Carpenter', 45.00), ('Electrician', 65.00), ('Painter', 35.00)
        ]
        cursor.executemany('INSERT INTO materials (name, unit, price) VALUES (?,?,?)', sample_materials)
        cursor.executemany('INSERT INTO labor (trade, rate_per_hour) VALUES (?,?)', sample_labor)

        conn.commit()
        self._close_connection()

    def get_items(self, table_name):
        """Fetch all items from a given table (materials or labor)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY id")
        items = cursor.fetchall()
        self._close_connection()
        return items

    def add_item(self, table_name, data):
        """Add a new item to the materials or labor table."""
        conn = self._get_connection()
        try:
            if table_name == 'materials':
                sql = 'INSERT INTO materials (name, unit, price) VALUES (?,?,?)'
            else:  # labor
                sql = 'INSERT INTO labor (trade, rate_per_hour) VALUES (?,?)'
            conn.cursor().execute(sql, data)
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Item already exists
        finally:
            self._close_connection()

    def update_item(self, table_name, item_id, data):
        """Update an item's details."""
        conn = self._get_connection()
        if table_name == 'materials':
            sql = 'UPDATE materials SET name=?, unit=?, price=? WHERE id=?'
        else:  # labor
            sql = 'UPDATE labor SET trade=?, rate_per_hour=? WHERE id=?'
        conn.cursor().execute(sql, (*data, item_id))
        conn.commit()
        self._close_connection()

    def delete_item(self, table_name, item_id):
        """Delete an item by its ID."""
        conn = self._get_connection()
        sql = f"DELETE FROM {table_name} WHERE id = ?"
        conn.cursor().execute(sql, (item_id,))
        conn.commit()
        self._close_connection()


# We still need the model classes from the previous version
class Task:
    def __init__(self, description):
        self.description = description
        self.materials = []
        self.labor = []

    def add_material(self, name, quantity, unit, unit_cost):
        self.materials.append(
            {'name': name, 'qty': quantity, 'unit': unit, 'unit_cost': unit_cost, 'total': quantity * unit_cost})

    def add_labor(self, trade, hours, rate):
        self.labor.append({'trade': trade, 'hours': hours, 'rate': rate, 'total': hours * rate})

    def get_subtotal(self):
        return sum(m['total'] for m in self.materials) + sum(l['total'] for l in self.labor)


class Estimate:
    def __init__(self, project_name, client_name, overhead, profit):
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