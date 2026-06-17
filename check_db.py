#!/usr/bin/env python3
from app.core.database import SessionLocal, engine
from app.models import TelegramUser, PracticeSession, AnalysisResult

print("=== Checking Database ===")

db = SessionLocal()

# Check users
print("\n=== Telegram Users ===")
users = db.query(TelegramUser).all()
for user in users:
    print(f"ID: {user.id}, Telegram ID: {user.telegram_id}, Name: {user.first_name}")
    
# Check practice sessions
print("\n=== Practice Sessions ===")
sessions = db.query(PracticeSession).all()
for s in sessions:
    print(f"Session ID: {s.id}, User ID: {s.telegram_user_id}, Score: {s.analysis_result.analysis_data.get('overall_score') if s.analysis_result else None}")

db.close()
