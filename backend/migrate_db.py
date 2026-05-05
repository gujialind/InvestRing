import sys
import json
sys.path.insert(0, ".")

from app.database import engine, Base, SessionLocal
from sqlalchemy import text, inspect
from app.models import *


def backup_data(db):
    data = {}

    r = db.execute(text("SELECT code, name, role, phone, email, password_hash, last_login_at, created_at, updated_at FROM investor"))
    data["investor"] = [dict(zip(r.keys(), row)) for row in r.fetchall()]

    r = db.execute(text("SELECT date, is_open, created_at FROM trading_calendar"))
    data["trading_calendar"] = [dict(zip(r.keys(), row)) for row in r.fetchall()]

    return data


def recreate_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("All tables recreated with new schema.")


def restore_data(db, data):
    if data.get("investor"):
        for row in data["investor"]:
            cols = ", ".join(row.keys())
            placeholders = ", ".join([f":{k}" for k in row.keys()])
            db.execute(text(f"INSERT INTO investor ({cols}) VALUES ({placeholders})"), row)

    if data.get("trading_calendar"):
        for row in data["trading_calendar"]:
            db.execute(text("INSERT INTO trading_calendar (date, is_open, created_at) VALUES (:date, :is_open, :created_at)"), row)

    db.commit()
    print(f"Restored {len(data.get('investor', []))} investors, {len(data.get('trading_calendar', []))} calendar entries.")


def main():
    db = SessionLocal()
    try:
        print("Backing up data...")
        data = backup_data(db)
        print(f"Backed up {len(data.get('investor', []))} investors, {len(data.get('trading_calendar', []))} calendar entries.")
    finally:
        db.close()

    recreate_database()

    db = SessionLocal()
    try:
        restore_data(db, data)
    finally:
        db.close()

    print("Migration complete!")


if __name__ == "__main__":
    main()
