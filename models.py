from datetime import datetime

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

    def add_task(self, task): self.tasks.append(task)

    def calculate_totals(self):
        subtotal = sum(t.get_subtotal() for t in self.tasks)
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
