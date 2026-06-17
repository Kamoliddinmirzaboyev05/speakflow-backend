
from app.core.config import settings
import sys

print("Testing environment configuration:")
print(f"TELEGRAM_BOT_TOKEN: {settings.TELEGRAM_BOT_TOKEN is not None}")
print(f"GROQ_API_KEY: {settings.GROQ_API_KEY is not None}")
print(f"Token length: {len(settings.TELEGRAM_BOT_TOKEN) if settings.TELEGRAM_BOT_TOKEN else 0}")
print(f"Database URL: {settings.DATABASE_URL}")

try:
    from app.core.database import SessionLocal
    db = SessionLocal()
    print("Database connection successful")
    db.close()
except Exception as e:
    print(f"Database error: {e}")
