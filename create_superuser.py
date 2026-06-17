import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal, engine
from app.models import Base, Admin
from app.api.admin import get_password_hash

# Create all tables
Base.metadata.create_all(bind=engine)

# Create default superuser
db = SessionLocal()
try:
    email = "admin@speakflow.ai"
    password = "admin123"
    existing_admin = db.query(Admin).filter(Admin.email == email).first()
    if not existing_admin:
        hashed_password = get_password_hash(password)
        db_admin = Admin(email=email, hashed_password=hashed_password)
        db.add(db_admin)
        db.commit()
        db.refresh(db_admin)
        print(f"Superuser created successfully!")
        print(f"Email: {email}")
        print(f"Password: {password}")
    else:
        print("Superuser already exists!")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
