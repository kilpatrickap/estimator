from datetime import datetime

class Task:
    """Represents a work package containing cost items."""
    def __init__(self, description):
        self.description = description
        self.materials = []
        self.labor = []
        self.equipment = []
        self.plant = []
        self.indirect_costs = []

    def add_material(self, name, quantity, unit, unit_cost, currency=None, formula=None):
        self._add_item(self.materials, {
            'name': name, 'qty': quantity, 'unit': unit, 'unit_cost': unit_cost,
            'total': quantity * unit_cost, 'currency': currency, 'formula': formula
        })

    def add_labor(self, trade, hours, rate, currency=None, formula=None, unit=None):
        self._add_item(self.labor, {
            'trade': trade, 'hours': hours, 'rate': rate, 'unit': unit,
            'total': hours * rate, 'currency': currency, 'formula': formula
        })

    def add_equipment(self, name, hours, rate, currency=None, formula=None, unit=None):
        self._add_item(self.equipment, {
            'name': name, 'hours': hours, 'rate': rate, 'unit': unit,
            'total': hours * rate, 'currency': currency, 'formula': formula
        })

    def add_plant(self, name, hours, rate, currency=None, formula=None, unit=None):
        self._add_item(self.plant, {
            'name': name, 'hours': hours, 'rate': rate, 'unit': unit,
            'total': hours * rate, 'currency': currency, 'formula': formula
        })

    def add_indirect_cost(self, description, amount, unit=None, currency=None, formula=None):
        self._add_item(self.indirect_costs, {
            'description': description, 'amount': amount, 'unit': unit,
            'total': amount, 'currency': currency, 'formula': formula
        })

    def _add_item(self, list_ref, item_dict):
        list_ref.append(item_dict)

    @property
    def all_items(self):
        """Yields all cost items across categories."""
        yield from self.materials
        yield from self.labor
        yield from self.equipment
        yield from self.plant
        yield from self.indirect_costs


class Estimate:
    """Represents a project estimate with multiple tasks and global settings."""
    def __init__(self, project_name, client_name, overhead, profit, currency="GHS (₵)", date=None, unit="", remarks=""):
        self.id = None
        self.rate_id = None
        self.project_name = project_name
        self.client_name = client_name
        self.overhead_percent = overhead
        self.profit_margin_percent = profit
        self.currency = currency
        self.unit = unit
        self.remarks = remarks
        self.adjustment_factor = 1.0
        
        if date:
            self.date = date if len(date) > 10 else f"{date} {datetime.now().strftime('%H:%M:%S')}"
        else:
            self.date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        self.tasks = []
        # Structure: {currency_code: {'rate': float, 'date': str, 'operator': '*' or '/'}}
        self.exchange_rates = {}

    def add_task(self, task):
        self.tasks.append(task)

    def convert_to_base_currency(self, amount, currency_code):
        """Converts an amount from a given currency to the project base currency."""
        target_currency = currency_code or self.currency
        if target_currency == self.currency:
            return amount
        
        rate_data = self.exchange_rates.get(target_currency, {})
        rate = rate_data.get('rate', 1.0)
        operator = rate_data.get('operator', '*')
        
        if operator == '/':
            return amount / rate if rate != 0 else 0.0
        return amount * rate

    def _get_item_total_in_base_currency(self, item):
        """Helper to compute an item's total cost in base currency."""
        return self.convert_to_base_currency(item['total'], item.get('currency'))

    def calculate_totals(self):
        """Calculates project financial summary including overhead and profit."""
        subtotal = 0.0
        
        for task in self.tasks:
            task_total = sum(self._get_item_total_in_base_currency(item) for item in task.all_items)
            subtotal += task_total

        # Apply adjustment factor to subtotal
        adj_factor = getattr(self, 'adjustment_factor', 1.0)
        subtotal *= adj_factor

        overhead = subtotal * (self.overhead_percent / 100.0)
        # Profit is calculated on (Subtotal + Overhead)
        profit = (subtotal + overhead) * (self.profit_margin_percent / 100.0)
        
        return {
            "subtotal": subtotal,
            "overhead": overhead,
            "profit": profit,
            "grand_total": subtotal + overhead + profit,
            "currency": self.currency
        }
