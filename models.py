from datetime import datetime

class Task:
    def __init__(self, description):
        self.description = description
        self.materials = []
        self.labor = []
        self.equipment = []

    def add_material(self, name, quantity, unit, unit_cost, currency=None, formula=None):
        self.materials.append(
            {'name': name, 'qty': quantity, 'unit': unit, 'unit_cost': unit_cost, 
             'total': quantity * unit_cost, 'currency': currency, 'formula': formula})

    def add_labor(self, trade, hours, rate, currency=None, formula=None):
        self.labor.append({'trade': trade, 'hours': hours, 'rate': rate, 
                           'total': hours * rate, 'currency': currency, 'formula': formula})

    def add_equipment(self, name, hours, rate, currency=None, formula=None):
        self.equipment.append({'name': name, 'hours': hours, 'rate': rate, 
                               'total': hours * rate, 'currency': currency, 'formula': formula})

    def get_subtotal(self):
        """Note: This returns the raw sum of items, NOT converted to base currency."""
        mat_total = sum(m['total'] for m in self.materials)
        lab_total = sum(l['total'] for l in self.labor)
        equip_total = sum(e['total'] for e in self.equipment)
        return mat_total + lab_total + equip_total


class Estimate:
    def __init__(self, project_name, client_name, overhead, profit, currency="GHS (₵)", date=None):
        self.id = None  # Will be set when loaded/saved
        self.project_name = project_name
        self.client_name = client_name
        self.overhead_percent = overhead
        self.profit_margin_percent = profit
        self.currency = currency
        if date and len(date) == 10:
            self.date = f"{date} {datetime.now().strftime('%H:%M:%S')}"
        else:
            self.date = date or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.tasks = []
        # Store exchange rates: {currency_name: {'rate': float, 'date': str}}
        self.exchange_rates = {}

    def add_task(self, task): self.tasks.append(task)

    def convert_to_base_currency(self, amount, currency_code):
        """Converts any amount to base currency using exchange rates."""
        currency = currency_code or self.currency
        if currency == self.currency:
            return amount
        
        rate_data = self.exchange_rates.get(currency, {})
        rate = rate_data.get('rate', 1.0)
        operator = rate_data.get('operator', '*')
        
        if operator == '/':
            return amount / rate if rate != 0 else 0.0
        else:
            return amount * rate

    def _get_item_total_in_base_currency(self, item):
        """Helper to get total from an item dict."""
        return self.convert_to_base_currency(item['total'], item.get('currency'))

    def calculate_totals(self):
        # We need to sum up task subtotals. 
        # Since tasks contain items, maybe we should update how task subtotals are calculated
        # or handle it here.
        subtotal = 0
        for task in self.tasks:
            task_subtotal = 0
            for m in task.materials:
                task_subtotal += self._get_item_total_in_base_currency(m)
            for l in task.labor:
                task_subtotal += self._get_item_total_in_base_currency(l)
            for e in task.equipment:
                task_subtotal += self._get_item_total_in_base_currency(e)
            subtotal += task_subtotal

        overhead = subtotal * (self.overhead_percent / 100)
        profit = (subtotal + overhead) * (self.profit_margin_percent / 100)
        grand_total = subtotal + overhead + profit
        return {
            "subtotal": subtotal,
            "overhead": overhead,
            "profit": profit,
            "grand_total": grand_total,
            "currency": self.currency
        }
