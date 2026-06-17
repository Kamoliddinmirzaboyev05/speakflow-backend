from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class TelegramUser(Base):
    __tablename__ = "telegram_users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    first_name = Column(String(255))
    last_name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True, unique=True, index=True)
    native_language = Column(String(100), default="Uzbek")
    english_level = Column(String(50), default="intermediate")
    target_band = Column(String(10), default="7.0")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    practice_sessions = relationship("PracticeSession", back_populates="telegram_user")


class Admin(Base):
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    native_language = Column(String(100))
    english_level = Column(String(50))
    target_band = Column(String(10))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    practice_sessions = relationship("PracticeSession", back_populates="user")


class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    telegram_user_id = Column(Integer, ForeignKey("telegram_users.id"), nullable=True)
    practice_mode = Column(String(50))
    question = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="practice_sessions")
    telegram_user = relationship("TelegramUser", back_populates="practice_sessions")
    analysis_result = relationship("AnalysisResult", uselist=False, back_populates="session")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("practice_sessions.id"))
    transcript = Column(Text)
    analysis_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    session = relationship("PracticeSession", back_populates="analysis_result")


class SpeakingQuestion(Base):
    __tablename__ = "speaking_questions"
    
    id = Column(Integer, primary_key=True, index=True)
    part = Column(Integer)  # 1, 2, or 3
    question = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
