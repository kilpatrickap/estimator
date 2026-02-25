import os
import copy
from datetime import datetime
from sqlalchemy import create_engine, inspect, func
from sqlalchemy.orm import sessionmaker
from models import Task, Estimate
from orm_models import (
    Base, Material, Labor, Equipment, Plant, IndirectCost, Setting, 
    DBEstimate, DBTask, DBEstimateMaterial, DBEstimateLabor, 
    DBEstimateEquipment, DBEstimatePlant, DBEstimateIndirectCost, 
    DBEstimateExchangeRate, DBEstimateSubRate
)

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
    """Manages all interactions with the database using SQLAlchemy ORM."""

    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self.engine = create_engine(f"sqlite:///{self.db_file}")
        self.Session = sessionmaker(bind=self.engine)

        if not os.path.exists(self.db_file):
            self._init_db()
        else:
            self._migrate_db()

    def _init_db(self):
        Base.metadata.create_all(self.engine)
        self._insert_sample_data()

    def _migrate_db(self):
        # In a real large-team project, you'd use Alembic. 
        # Here we just ensure all tables exist.
        Base.metadata.create_all(self.engine)

    def _insert_sample_data(self):
        now = datetime.now().strftime('%Y-%m-%d')
        with self.Session() as session:
            # Add Settings
            session.add_all([
                Setting(key='currency', value='GHS (₵)'),
                Setting(key='overhead', value='15.0'),
                Setting(key='profit', value='10.0')
            ])

            # Add Materials
            session.add_all([
                Material(name='Concrete 3000 PSI', unit='cubic_yard', price=150.00, date_added=now, location='Accra', remarks='Standard mix'),
                Material(name='2x4 Lumber 8ft', unit='each', price=4.50, date_added=now, location='Kumasi', remarks='Treated pine'),
                Material(name='1/2" Drywall Sheet 4x8', unit='sheet', price=12.00, date_added=now, location='Accra', remarks='Moisture resistant'),
                Material(name='Latex Paint', unit='gallon', price=35.00, date_added=now, location='Tema', remarks='Interior silk')
            ])

            # Add Labor
            session.add_all([
                Labor(trade='General Laborer', unit='hr', rate=25.0, date_added=now, location='Nationwide', remarks='-'),
                Labor(trade='Carpenter', unit='hr', rate=45.0, date_added=now, location='Accra', remarks='Experienced'),
                Labor(trade='Electrician', unit='hr', rate=65.0, date_added=now, location='Kumasi', remarks='Certified'),
                Labor(trade='Painter', unit='hr', rate=35.0, date_added=now, location='Tema', remarks='-')
            ])

            # Add Equipment
            session.add_all([
                Equipment(name='Skid Steer', unit='hr', rate=75.0, date_added=now, location='Rental Depot', remarks='Daily rate'),
                Equipment(name='Excavator', unit='hr', rate=120.0, date_added=now, location='Project Site', remarks='Hourly with fuel'),
                Equipment(name='Concrete Mixer', unit='hr', rate=40.0, date_added=now, location='Warehouse', remarks='-'),
                Equipment(name='Scissor Lift', unit='hr', rate=60.0, date_added=now, location='Rental Depot', remarks='19ft reach')
            ])

            # Add Plant
            session.add_all([
                Plant(name='Tower Crane', unit='hr', rate=250.0, date_added=now, location='Site', remarks='Large capacity'),
                Plant(name='Forklift', unit='hr', rate=80.0, date_added=now, location='Warehouse', remarks='5-ton capacity'),
                Plant(name='Generator 50kVA', unit='hr', rate=60.0, date_added=now, location='Site', remarks='Diesel powered')
            ])

            # Add Indirect Costs
            session.add_all([
                IndirectCost(description='Site Supervision', unit='month', amount=5000.0, date_added=now),
                IndirectCost(description='Insurance', unit='lot', amount=2000.0, date_added=now),
                IndirectCost(description='Temporary Water', unit='month', amount=300.0, date_added=now)
            ])

            session.commit()

    def _get_model_class(self, table_name):
        mapping = {
            'materials': Material,
            'labor': Labor,
            'equipment': Equipment,
            'plant': Plant,
            'indirect_costs': IndirectCost
        }
        return mapping.get(table_name)

    def _to_dict(self, obj):
        if not obj: return None
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

    def get_items(self, table_name):
        model = self._get_model_class(table_name)
        if not model: return []
        with self.Session() as session:
            sort_attr = model.description if table_name == 'indirect_costs' else (model.trade if table_name == 'labor' else model.name)
            items = session.query(model).order_by(sort_attr).all()
            return [self._to_dict(item) for item in items]

    def add_item(self, table_name, data):
        """Adds a new item to the cost library and returns its ID."""
        model = self._get_model_class(table_name)
        if not model: return None
        with self.Session() as session:
            try:
                # data is a tuple exactly matching the old sqlite parameter bindings.
                if table_name == 'materials':
                    obj = model(name=data[0], unit=data[1], currency=data[2], price=data[3], formula=data[4], date_added=data[5], location=data[6], contact=data[7], remarks=data[8])
                elif table_name == 'labor':
                    obj = model(trade=data[0], unit=data[1], currency=data[2], rate=data[3], formula=data[4], date_added=data[5], location=data[6], contact=data[7], remarks=data[8])
                elif table_name == 'indirect_costs':
                    obj = model(description=data[0], unit=data[1], currency=data[2], amount=data[3], formula=data[4], date_added=data[5])
                else: # equipment, plant
                    obj = model(name=data[0], unit=data[1], currency=data[2], rate=data[3], formula=data[4], date_added=data[5], location=data[6], contact=data[7], remarks=data[8])
                session.add(obj)
                session.commit()
                return obj.id
            except Exception as e:
                session.rollback()
                return None

    def update_item(self, table_name, item_id, data):
        model = self._get_model_class(table_name)
        if not model: return
        with self.Session() as session:
            obj = session.query(model).get(item_id)
            if not obj: return
            if table_name == 'materials':
                obj.name, obj.unit, obj.currency, obj.price, obj.formula, obj.date_added, obj.location, obj.contact, obj.remarks = data
            elif table_name == 'labor':
                obj.trade, obj.unit, obj.currency, obj.rate, obj.formula, obj.date_added, obj.location, obj.contact, obj.remarks = data
            elif table_name == 'indirect_costs':
                obj.description, obj.unit, obj.currency, obj.amount, obj.formula, obj.date_added = data
            else:
                obj.name, obj.unit, obj.currency, obj.rate, obj.formula, obj.date_added, obj.location, obj.contact, obj.remarks = data
            session.commit()

    def update_item_currency(self, table_name, item_id, currency):
        self.update_item_field(table_name, 'currency', currency, item_id)

    def update_item_date(self, table_name, item_id, date_str):
        self.update_item_field(table_name, 'date_added', date_str, item_id)

    def update_item_field(self, table_name, column, value, item_id):
        model = self._get_model_class(table_name)
        if not model: return
        with self.Session() as session:
            obj = session.query(model).get(item_id)
            if obj:
                setattr(obj, column, value)
                session.commit()

    def delete_item(self, table_name, item_id):
        model = self._get_model_class(table_name)
        if not model: return
        with self.Session() as session:
            obj = session.query(model).get(item_id)
            if obj:
                session.delete(obj)
                session.commit()

    def get_item_id_by_name(self, table_name, name, session=None):
        close_session = False
        if not session:
            session = self.Session()
            close_session = True
        try:
            model = self._get_model_class(table_name)
            if not model: return None
            col_attr = model.description if table_name == 'indirect_costs' else (model.trade if table_name == 'labor' else model.name)
            obj = session.query(model).filter(col_attr == name).first()
            return obj.id if obj else None
        finally:
            if close_session:
                session.close()

    def save_estimate(self, estimate_obj):
        totals = estimate_obj.calculate_totals()
        
        with self.Session() as session:
            try:
                if estimate_obj.id:
                    db_est = session.query(DBEstimate).get(estimate_obj.id)
                    db_est.project_name = estimate_obj.project_name
                    db_est.client_name = estimate_obj.client_name
                    db_est.overhead_percent = estimate_obj.overhead_percent
                    db_est.profit_margin_percent = estimate_obj.profit_margin_percent
                    db_est.currency = estimate_obj.currency
                    db_est.date_created = estimate_obj.date
                    db_est.grand_total = totals['grand_total']
                    db_est.net_total = totals['subtotal']
                    db_est.rate_code = estimate_obj.rate_code
                    db_est.unit = estimate_obj.unit
                    db_est.notes = estimate_obj.notes
                    db_est.adjustment_factor = estimate_obj.adjustment_factor
                    db_est.category = getattr(estimate_obj, 'category', "")
                    db_est.rate_type = getattr(estimate_obj, 'rate_type', "Simple")
                    
                    # Delete old tasks
                    for task in db_est.tasks:
                        session.delete(task)
                    for rate in db_est.exchange_rates:
                        session.delete(rate)
                    for sub in db_est.sub_rates:
                        session.delete(sub)
                else:
                    db_est = DBEstimate(
                        project_name=estimate_obj.project_name, client_name=estimate_obj.client_name,
                        overhead_percent=estimate_obj.overhead_percent, profit_margin_percent=estimate_obj.profit_margin_percent,
                        currency=estimate_obj.currency, date_created=estimate_obj.date,
                        grand_total=totals['grand_total'], net_total=totals['subtotal'],
                        rate_code=estimate_obj.rate_code, unit=estimate_obj.unit, notes=estimate_obj.notes,
                        adjustment_factor=estimate_obj.adjustment_factor, 
                        category=getattr(estimate_obj, 'category', ""), rate_type=getattr(estimate_obj, 'rate_type', "Simple")
                    )
                    session.add(db_est)
                    session.flush() # get ID
                    estimate_obj.id = db_est.id

                # Save tasks
                for task_obj in estimate_obj.tasks:
                    db_task = DBTask(estimate_id=db_est.id, description=task_obj.description)
                    session.add(db_task)
                    session.flush()
                    
                    for item in task_obj.materials:
                        mat_id = self.get_item_id_by_name('materials', item['name'], session)
                        session.add(DBEstimateMaterial(task_id=db_task.id, material_id=mat_id, quantity=item['qty'], formula=item.get('formula'), name=item['name'], unit=item['unit'], price=item['unit_cost'], currency=item.get('currency')))
                    for item in task_obj.labor:
                        lab_id = self.get_item_id_by_name('labor', item['trade'], session)
                        session.add(DBEstimateLabor(task_id=db_task.id, labor_id=lab_id, hours=item['hours'], formula=item.get('formula'), name_trade=item['trade'], unit=item.get('unit'), rate=item['rate'], currency=item.get('currency')))
                    for item in task_obj.equipment:
                        eq_id = self.get_item_id_by_name('equipment', item['name'], session)
                        session.add(DBEstimateEquipment(task_id=db_task.id, equipment_id=eq_id, hours=item['hours'], formula=item.get('formula'), name_trade=item['name'], unit=item.get('unit'), rate=item['rate'], currency=item.get('currency')))
                    for item in task_obj.plant:
                        pl_id = self.get_item_id_by_name('plant', item['name'], session)
                        session.add(DBEstimatePlant(task_id=db_task.id, plant_id=pl_id, hours=item['hours'], formula=item.get('formula'), name_trade=item['name'], unit=item.get('unit'), rate=item['rate'], currency=item.get('currency')))
                    for item in task_obj.indirect_costs:
                        ind_id = self.get_item_id_by_name('indirect_costs', item['description'], session)
                        session.add(DBEstimateIndirectCost(task_id=db_task.id, indirect_id=ind_id, amount=item['amount'], formula=item.get('formula'), description=item['description'], unit=item.get('unit'), currency=item.get('currency')))

                # Save exchange rates
                for curr, data in estimate_obj.exchange_rates.items():
                    op = data.get('operator', '*')
                    session.add(DBEstimateExchangeRate(estimate_id=db_est.id, currency=curr, rate=data['rate'], date=data['date'], operator=op))

                # Save sub-rates
                for sub_rate in estimate_obj.sub_rates:
                    if sub_rate.id:
                        qty = getattr(sub_rate, 'quantity', 1.0)
                        formula = getattr(sub_rate, 'formula', None)
                        c_unit = getattr(sub_rate, 'converted_unit', None)
                        session.add(DBEstimateSubRate(estimate_id=db_est.id, sub_rate_id=sub_rate.id, quantity=qty, formula=formula, converted_unit=c_unit))

                session.commit()
                return True
            except Exception as e:
                session.rollback()
                print(f"Database error (ORM): {e}")
                return False

    def get_saved_estimates_summary(self):
        with self.Session() as session:
            ests = session.query(DBEstimate).order_by(DBEstimate.date_created.desc()).all()
            return [{'id': e.id, 'project_name': e.project_name, 'client_name': e.client_name, 'date_created': e.date_created} for e in ests]

    def _load_legacy_item(self, session, legacy_id, table_name):
        model = self._get_model_class(table_name)
        if not model: return None
        obj = session.query(model).get(legacy_id)
        return self._to_dict(obj)

    def load_estimate_details(self, estimate_id):
        with self.Session() as session:
            db_est = session.query(DBEstimate).get(estimate_id)
            if not db_est: return None

            loaded = Estimate(
                db_est.project_name, db_est.client_name, 
                db_est.overhead_percent, db_est.profit_margin_percent, 
                currency=db_est.currency or "GHS (₵)", date=db_est.date_created,
                unit=db_est.unit or "", notes=db_est.notes or ""
            )
            loaded.id = db_est.id
            loaded.rate_code = db_est.rate_code
            loaded.adjustment_factor = db_est.adjustment_factor if db_est.adjustment_factor is not None else 1.0
            loaded.category = db_est.category or ""
            loaded.rate_type = db_est.rate_type or "Simple"

            for db_task in db_est.tasks:
                task_obj = Task(db_task.description)
                
                for m in db_task.materials:
                    name = m.name or ""
                    unit = m.unit or ""
                    price = m.price if m.price is not None else 0.0
                    curr = m.currency or loaded.currency
                    if not name and m.material_id:
                        legacy = self._load_legacy_item(session, m.material_id, "materials")
                        if legacy:
                            name, unit, price, curr = legacy['name'], legacy['unit'], legacy['price'], legacy['currency']
                    task_obj.add_material(name, m.quantity, unit, price, currency=curr, formula=m.formula)

                for l in db_task.labor:
                    name = l.name_trade or ""
                    unit = l.unit or ""
                    rate = l.rate if l.rate is not None else 0.0
                    curr = l.currency or loaded.currency
                    if not name and l.labor_id:
                        legacy = self._load_legacy_item(session, l.labor_id, "labor")
                        if legacy:
                            name, unit, rate, curr = legacy['trade'], legacy['unit'], legacy['rate'], legacy['currency']
                    task_obj.add_labor(name, l.hours, rate, currency=curr, formula=l.formula, unit=unit)

                for e in db_task.equipment:
                    name = e.name_trade or ""
                    unit = e.unit or ""
                    rate = e.rate if e.rate is not None else 0.0
                    curr = e.currency or loaded.currency
                    if not name and e.equipment_id:
                        legacy = self._load_legacy_item(session, e.equipment_id, "equipment")
                        if legacy:
                            name, unit, rate, curr = legacy['name'], legacy['unit'], legacy['rate'], legacy['currency']
                    task_obj.add_equipment(name, e.hours, rate, currency=curr, formula=e.formula, unit=unit)

                for p in db_task.plant:
                    name = p.name_trade or ""
                    unit = p.unit or ""
                    rate = p.rate if p.rate is not None else 0.0
                    curr = p.currency or loaded.currency
                    if not name and p.plant_id:
                        legacy = self._load_legacy_item(session, p.plant_id, "plant")
                        if legacy:
                            name, unit, rate, curr = legacy['name'], legacy['unit'], legacy['rate'], legacy['currency']
                    task_obj.add_plant(name, p.hours, rate, currency=curr, formula=p.formula, unit=unit)

                for i in db_task.indirect_costs:
                    desc = i.description or ""
                    unit = i.unit or ""
                    amount = i.amount if i.amount is not None else 0.0
                    curr = i.currency or loaded.currency
                    if not desc and i.indirect_id:
                        legacy = self._load_legacy_item(session, i.indirect_id, "indirect_costs")
                        if legacy:
                            desc, unit, amount, curr = legacy['description'], legacy['unit'], legacy['amount'], legacy['currency']
                    task_obj.add_indirect_cost(desc, amount, unit=unit, currency=curr, formula=i.formula)

                loaded.add_task(task_obj)

            for er in db_est.exchange_rates:
                loaded.exchange_rates[er.currency] = {'rate': er.rate, 'date': er.date, 'operator': er.operator}

            for sr in db_est.sub_rates:
                sub_loaded = self.load_estimate_details(sr.sub_rate_id)
                if sub_loaded:
                    sub_loaded.quantity = sr.quantity
                    sub_loaded.formula = sr.formula
                    sub_loaded.converted_unit = sr.converted_unit
                    loaded.add_sub_rate(sub_loaded)

            return loaded

    def delete_estimate(self, estimate_id):
        with self.Session() as session:
            try:
                db_est = session.query(DBEstimate).get(estimate_id)
                if db_est:
                    session.delete(db_est)
                    session.commit()
                    return True
                return False
            except Exception:
                session.rollback()
                return False

    def duplicate_estimate(self, estimate_id):
        original = self.load_estimate_details(estimate_id)
        if not original: return False
        original.id = None
        original.project_name = f"Copy of {original.project_name}"
        return self.save_estimate(original)

    def update_estimate_metadata(self, estimate_id, project_name, client_name, date):
        with self.Session() as session:
            db_est = session.query(DBEstimate).get(estimate_id)
            if db_est:
                db_est.project_name = project_name
                db_est.client_name = client_name
                db_est.date_created = date
                session.commit()
                return True
            return False

    def update_estimate_field(self, estimate_id, field, value):
        with self.Session() as session:
            db_est = session.query(DBEstimate).get(estimate_id)
            if db_est:
                setattr(db_est, field, value)
                session.commit()
                return True
            return False

    def get_recent_estimates(self, limit=5):
        with self.Session() as session:
            ests = session.query(DBEstimate).order_by(DBEstimate.date_created.desc()).limit(limit).all()
            return [{'id': e.id, 'project_name': e.project_name, 'client_name': e.client_name, 'date_created': e.date_created, 'grand_total': e.grand_total} for e in ests]

    def get_total_estimates_count(self):
        with self.Session() as session:
            return session.query(func.count(DBEstimate.id)).scalar()

    def get_total_estimates_value(self):
        with self.Session() as session:
            val = session.query(func.sum(DBEstimate.grand_total)).scalar()
            return val if val else 0.0

    def get_setting(self, key, default=None):
        with self.Session() as session:
            s = session.query(Setting).get(key)
            return s.value if s else default

    def set_setting(self, key, value):
        with self.Session() as session:
            s = session.query(Setting).get(key)
            if s:
                s.value = str(value)
            else:
                session.add(Setting(key=key, value=str(value)))
            session.commit()
            return True

    def convert_to_rate_db(self, estimate_obj):
        rates_db_manager = DatabaseManager("construction_rates.db")
        rate_estimate = copy.deepcopy(estimate_obj)
        rate_estimate.id = None
        rate_estimate.date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if not getattr(rate_estimate, 'category', ""):
            rate_estimate.category = "Miscellaneous"
        rate_estimate.rate_code = rates_db_manager.generate_next_rate_code(rate_estimate.category)
        
        if rates_db_manager.save_estimate(rate_estimate):
            return rate_estimate.rate_code
        return None

    def generate_next_rate_code(self, category):
        prefix = CATEGORY_PREFIXES.get(category, "MISC")
        with self.Session() as session:
            codes = [row[0] for row in session.query(DBEstimate.rate_code).filter(DBEstimate.rate_code.like(f"{prefix}%")).all()]
            
        if not codes:
            return f"{prefix}1A"
            
        import re
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
            
        if max_letter == 'Z':
            next_num = max_num + 1
            next_letter = 'A'
        else:
            next_num = max_num
            next_letter = chr(ord(max_letter) + 1)
            
        return f"{prefix}{next_num}{next_letter}"

    def get_rates_data(self):
        rates_db = DatabaseManager("construction_rates.db")
        with rates_db.Session() as session:
            ests = session.query(DBEstimate).order_by(DBEstimate.rate_code.asc()).all()
            return [{'id': e.id, 'rate_code': e.rate_code, 'project_name': e.project_name, 'unit': e.unit, 'currency': e.currency, 'net_total': e.net_total, 'grand_total': e.grand_total, 'adjustment_factor': e.adjustment_factor, 'date_created': e.date_created, 'notes': e.notes, 'rate_type': e.rate_type} for e in ests]

    def get_estimates_using_resource(self, table_name, resource_name):
        with self.Session() as session:
            if table_name == 'materials':
                return [r[0] for r in session.query(DBEstimate.id).join(DBTask).join(DBEstimateMaterial).filter(DBEstimateMaterial.name == resource_name).distinct().all()]
            elif table_name == 'labor':
                return [r[0] for r in session.query(DBEstimate.id).join(DBTask).join(DBEstimateLabor).filter(DBEstimateLabor.name_trade == resource_name).distinct().all()]
            elif table_name == 'equipment':
                return [r[0] for r in session.query(DBEstimate.id).join(DBTask).join(DBEstimateEquipment).filter(DBEstimateEquipment.name_trade == resource_name).distinct().all()]
            elif table_name == 'plant':
                return [r[0] for r in session.query(DBEstimate.id).join(DBTask).join(DBEstimatePlant).filter(DBEstimatePlant.name_trade == resource_name).distinct().all()]
            elif table_name == 'indirect_costs':
                return [r[0] for r in session.query(DBEstimate.id).join(DBTask).join(DBEstimateIndirectCost).filter(DBEstimateIndirectCost.description == resource_name).distinct().all()]
        return []

    def update_resource_in_all_estimates(self, table_name, resource_name, new_val, new_curr, new_unit=None):
        est_ids = self.get_estimates_using_resource(table_name, resource_name)
        if not est_ids: return 0

        type_map = {
            'materials': 'material', 'labor': 'labor', 'equipment': 'equipment',
            'plant': 'plant', 'indirect_costs': 'indirect_costs'
        }
        item_type = type_map.get(table_name)
        if not item_type: return 0

        name_key_map = {
            'material': 'name', 'labor': 'trade', 'equipment': 'name',
            'plant': 'name', 'indirect_costs': 'description'
        }
        name_key = name_key_map.get(item_type)
        rate_key = 'price' if item_type == 'material' else ('amount' if item_type == 'indirect_costs' else 'rate')

        updated_count = 0
        for eid in est_ids:
            est = self.load_estimate_details(eid)
            if not est: continue
            
            changed = False
            for task in est.tasks:
                items = getattr(task, table_name, [])
                for item in items:
                    if item.get(name_key) == resource_name:
                        if item.get(rate_key) != new_val or item.get('currency') != new_curr or (new_unit and item.get('unit') != new_unit):
                            item[rate_key] = new_val
                            if new_curr: item['currency'] = new_curr
                            if new_unit: item['unit'] = new_unit
                            qty_key = 'qty' if item_type == 'material' else ('amount' if item_type == 'indirect_costs' else 'hours')
                            
                            qty = item.get(qty_key, 1.0)
                            if item_type == 'indirect_costs':
                                item['amount'] = new_val
                                item['total'] = new_val
                            else:
                                item['total'] = qty * new_val
                            changed = True

            if changed:
                self.save_estimate(est)
                updated_count += 1

        return updated_count

    def recalculate_all_estimates(self):
        with self.Session() as session:
            ids = [r[0] for r in session.query(DBEstimate.id).all()]
        for eid in ids:
            est = self.load_estimate_details(eid)
            if est:
                self.save_estimate(est)
