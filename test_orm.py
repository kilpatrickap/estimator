import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from orm_models import Base, Material, Labor, Equipment, Plant, IndirectCost, Setting, DBEstimate, DBTask

def test_orm():
    engine = create_engine('sqlite:///construction_costs.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    # Query materials
    mats = session.query(Material).all()
    print(f"Loaded {len(mats)} materials")
    for m in mats:
        print(f" - {m.name}: {m.price}")

    settings = session.query(Setting).all()
    print(f"Loaded {len(settings)} settings")

    estimates = session.query(DBEstimate).all()
    print(f"Loaded {len(estimates)} estimates")

    session.close()

if __name__ == '__main__':
    test_orm()
