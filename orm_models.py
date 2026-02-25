from sqlalchemy import Column, Integer, String, Float, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Material(Base):
    __tablename__ = 'materials'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True)
    unit = Column(String)
    currency = Column(String, default="GHS (₵)")
    price = Column(Float)
    formula = Column(String)
    date_added = Column(String)
    location = Column(String)
    contact = Column(String)
    remarks = Column(String)

class Labor(Base):
    __tablename__ = 'labor'
    id = Column(Integer, primary_key=True, autoincrement=True)
    trade = Column(String, unique=True)
    unit = Column(String)
    currency = Column(String, default="GHS (₵)")
    rate = Column(Float)
    formula = Column(String)
    date_added = Column(String)
    location = Column(String)
    contact = Column(String)
    remarks = Column(String)

class Equipment(Base):
    __tablename__ = 'equipment'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True)
    unit = Column(String)
    currency = Column(String, default="GHS (₵)")
    rate = Column(Float)
    formula = Column(String)
    date_added = Column(String)
    location = Column(String)
    contact = Column(String)
    remarks = Column(String)

class Plant(Base):
    __tablename__ = 'plant'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True)
    unit = Column(String)
    currency = Column(String, default="GHS (₵)")
    rate = Column(Float)
    formula = Column(String)
    date_added = Column(String)
    location = Column(String)
    contact = Column(String)
    remarks = Column(String)

class IndirectCost(Base):
    __tablename__ = 'indirect_costs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String, unique=True)
    unit = Column(String)
    currency = Column(String, default="GHS (₵)")
    amount = Column(Float)
    formula = Column(String)
    date_added = Column(String)

class Setting(Base):
    __tablename__ = 'settings'
    key = Column(String, primary_key=True)
    value = Column(String)

class DBEstimate(Base):
    __tablename__ = 'estimates'
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_name = Column(String)
    client_name = Column(String)
    overhead_percent = Column(Float)
    profit_margin_percent = Column(Float)
    currency = Column(String)
    date_created = Column(String)
    grand_total = Column(Float, default=0.0)
    net_total = Column(Float, default=0.0)
    rate_code = Column(String)
    unit = Column(String)
    notes = Column(String)
    adjustment_factor = Column(Float, default=1.0)
    category = Column(String)
    rate_type = Column(String, default='Simple')

    tasks = relationship("DBTask", back_populates="estimate", cascade="all, delete-orphan")
    exchange_rates = relationship("DBEstimateExchangeRate", back_populates="estimate", cascade="all, delete-orphan")
    sub_rates = relationship("DBEstimateSubRate", back_populates="estimate", cascade="all, delete-orphan")

class DBTask(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    estimate_id = Column(Integer, ForeignKey('estimates.id', ondelete='CASCADE'), nullable=False)
    description = Column(String)

    estimate = relationship("DBEstimate", back_populates="tasks")
    
    materials = relationship("DBEstimateMaterial", back_populates="task", cascade="all, delete-orphan")
    labor = relationship("DBEstimateLabor", back_populates="task", cascade="all, delete-orphan")
    equipment = relationship("DBEstimateEquipment", back_populates="task", cascade="all, delete-orphan")
    plant = relationship("DBEstimatePlant", back_populates="task", cascade="all, delete-orphan")
    indirect_costs = relationship("DBEstimateIndirectCost", back_populates="task", cascade="all, delete-orphan")

class DBEstimateMaterial(Base):
    __tablename__ = 'estimate_materials'
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)
    material_id = Column(Integer, nullable=True) # Weak link to library
    quantity = Column(Float)
    formula = Column(String)
    name = Column(String)
    unit = Column(String)
    price = Column(Float)
    currency = Column(String)

    task = relationship("DBTask", back_populates="materials")

class DBEstimateLabor(Base):
    __tablename__ = 'estimate_labor'
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)
    labor_id = Column(Integer, nullable=True)
    hours = Column(Float)
    formula = Column(String)
    name_trade = Column(String)
    unit = Column(String)
    rate = Column(Float)
    currency = Column(String)

    task = relationship("DBTask", back_populates="labor")

class DBEstimateEquipment(Base):
    __tablename__ = 'estimate_equipment'
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)
    equipment_id = Column(Integer, nullable=True)
    hours = Column(Float)
    formula = Column(String)
    name_trade = Column(String)
    unit = Column(String)
    rate = Column(Float)
    currency = Column(String)

    task = relationship("DBTask", back_populates="equipment")

class DBEstimatePlant(Base):
    __tablename__ = 'estimate_plant'
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)
    plant_id = Column(Integer, nullable=True)
    hours = Column(Float)
    formula = Column(String)
    name_trade = Column(String)
    unit = Column(String)
    rate = Column(Float)
    currency = Column(String)

    task = relationship("DBTask", back_populates="plant")

class DBEstimateIndirectCost(Base):
    __tablename__ = 'estimate_indirect_costs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)
    indirect_id = Column(Integer, nullable=True)
    amount = Column(Float)
    formula = Column(String)
    description = Column(String)
    unit = Column(String)
    currency = Column(String)

    task = relationship("DBTask", back_populates="indirect_costs")

class DBEstimateExchangeRate(Base):
    __tablename__ = 'estimate_exchange_rates'
    id = Column(Integer, primary_key=True, autoincrement=True)
    estimate_id = Column(Integer, ForeignKey('estimates.id', ondelete='CASCADE'), nullable=False)
    currency = Column(String, nullable=False)
    rate = Column(Float, default=1.0)
    date = Column(String)
    operator = Column(String, default="*")

    estimate = relationship("DBEstimate", back_populates="exchange_rates")

class DBEstimateSubRate(Base):
    __tablename__ = 'estimate_sub_rates'
    id = Column(Integer, primary_key=True, autoincrement=True)
    estimate_id = Column(Integer, ForeignKey('estimates.id', ondelete='CASCADE'), nullable=False)
    sub_rate_id = Column(Integer)
    quantity = Column(Float, default=1.0)
    formula = Column(String)
    converted_unit = Column(String)

    estimate = relationship("DBEstimate", back_populates="sub_rates")
