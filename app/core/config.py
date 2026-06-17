from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "SpeakFlow Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    DATABASE_URL: str = "sqlite:///./speakflow.db"
    
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    # Must be HTTPS for Telegram Web App keyboard buttons
    WEB_APP_URL: str = "https://speakflow-app-xi.vercel.app"
    
    GROQ_API_KEY: Optional[str] = None
    
    REDIS_URL: str = "redis://localhost:6379/0"
    
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    class Config:
        env_file = ".env"


settings = Settings()
