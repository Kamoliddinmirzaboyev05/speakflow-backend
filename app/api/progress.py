from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.core.config import settings
from app.models import TelegramUser, PracticeSession, AnalysisResult
from pydantic import BaseModel
import hashlib
import hmac
import urllib.parse
from datetime import datetime

router = APIRouter(prefix="/progress", tags=["progress"])


class WebAppInitData(BaseModel):
    init_data: str


class PhoneNumberRequest(BaseModel):
    phone_number: str


def validate_telegram_init_data(init_data: str) -> Optional[dict]:
    """
    Telegram WebApp initData'sini validate qiladi
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Bot token not configured")
    
    # Parse init_data
    parsed = urllib.parse.parse_qs(init_data)
    if not parsed:
        return None
    
    # Hash ni ajratib olish
    hash_value = parsed.get('hash', [None])[0]
    if not hash_value:
        return None
    
    # Hash dan boshqa barcha maydonlarni ajratib, sort qilish
    data_check = []
    for key, value in parsed.items():
        if key != 'hash' and value:
            data_check.append(f"{key}={value[0]}")
    
    # Alphabetic tartibda sortlash
    data_check.sort()
    data_check_string = '\n'.join(data_check)
    
    # Secret key yaratish (bot tokenidan SHA256)
    secret_key = hmac.new(
        key=b'WebAppData',
        msg=settings.TELEGRAM_BOT_TOKEN.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    
    # Data check stringidan HMAC-SHA256 hash yaratish
    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    # Hashlarni solishtirish - use compare_digest to prevent timing attacks
    if not hmac.compare_digest(calculated_hash, hash_value):
        return None
    
    # User ma'lumotlarini qaytarish
    user_str = parsed.get('user', [None])[0]
    if user_str:
        import json
        return json.loads(user_str)
    
    return None


def get_analysis_score_safe(analysis_result) -> Optional[int]:
    """
    Safely extract overall_score from analysis_data, handling different data formats.
    The analysis_data might be a dict (fresh from AI) or have nested structures.
    """
    if not analysis_result or not analysis_result.analysis_data:
        return None
    
    data = analysis_result.analysis_data
    
    # Direct key access
    if isinstance(data, dict):
        score = data.get('overall_score')
        if score is not None:
            return score
        # Try nested 'analysis_data' key (some stored formats)
        nested = data.get('analysis_data', {})
        if isinstance(nested, dict):
            score = nested.get('overall_score')
            if score is not None:
                return score
    
    return None


def get_analysis_data_safe(analysis_result) -> Optional[dict]:
    """
    Safely extract the full analysis data dict, handling nested formats.
    """
    if not analysis_result or not analysis_result.analysis_data:
        return None
    
    data = analysis_result.analysis_data
    
    if isinstance(data, dict):
        # If analysis_data has 'overall_score' at top level, return as-is
        if 'overall_score' in data:
            return data
        # If nested under 'analysis_data' key
        nested = data.get('analysis_data')
        if isinstance(nested, dict) and 'overall_score' in nested:
            return nested
    
    return data if isinstance(data, dict) else None


def get_user_progress_data(user: TelegramUser, db: Session) -> dict:
    sessions = db.query(PracticeSession).filter(
        PracticeSession.telegram_user_id == user.id
    ).order_by(PracticeSession.created_at.desc()).all()
    
    scores = []
    for session in sessions:
        score = get_analysis_score_safe(session.analysis_result)
        if score is not None:
            scores.append(score)
    
    avg_score = sum(scores) / len(scores) if scores else 0
    
    # Oxirgi analysis result ni topish
    latest_analysis = None
    if sessions:
        latest_session = sessions[0]
        latest_data = get_analysis_data_safe(latest_session.analysis_result)
        if latest_data:
            latest_analysis = {
                "id": latest_session.analysis_result.id,
                "analysis_data": latest_data
            }
    
    return {
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "phone_number": user.phone_number,
            "target_band": user.target_band,
            "english_level": user.english_level,
            "native_language": user.native_language
        },
        "total_sessions": len(sessions),
        "average_score": round(avg_score, 2),
        "latest_score": scores[0] if scores else None,
        "sessions": [
            {
                "id": s.id,
                "practice_mode": s.practice_mode,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "score": get_analysis_score_safe(s.analysis_result)
            }
            for s in sessions[:10]
        ],
        "latest_analysis": latest_analysis
    }


@router.get("/users", response_model=List[dict])
def list_users(db: Session = Depends(get_db)):
    users = db.query(TelegramUser).all()
    return [
        {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "first_name": user.first_name,
            "username": user.username,
            "target_band": user.target_band
        }
        for user in users
    ]


@router.get("/user/{telegram_id}", response_model=dict)
def get_user_progress(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
    if not user:
        return {"error": "User not found"}
    return get_user_progress_data(user, db)


@router.post("/webapp", response_model=dict)
def get_webapp_progress(data: WebAppInitData, db: Session = Depends(get_db)):
    """
    Telegram Mini App uchun endpoint - initData orqali foydalanuvchini aniqlab progressini qaytaradi
    """
    # InitData ni validate qilish
    user_data = validate_telegram_init_data(data.init_data)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid init data")
    
    telegram_id = user_data.get('id')
    if not telegram_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # Foydalanuvchini bazadan topish yoki yangisini yaratish
    user = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not registered yet")
    
    return get_user_progress_data(user, db)


@router.post("/by-phone", response_model=dict)
def get_progress_by_phone(request: PhoneNumberRequest, db: Session = Depends(get_db)):
    """
    Telefon raqami orqali foydalanuvchini topib progressini qaytaradi
    """
    phone_number = request.phone_number.strip()
    if not phone_number:
        raise HTTPException(status_code=400, detail="Phone number is required")
    
    # Foydalanuvchini telefon raqami orqali topish
    user = db.query(TelegramUser).filter(TelegramUser.phone_number == phone_number).first()
    if not user:
        # Agar telefon raqami + bilan boshlanmagan bo'lsa, qo'shib qidirish
        if not phone_number.startswith('+'):
            user = db.query(TelegramUser).filter(TelegramUser.phone_number == '+' + phone_number).first()
        elif phone_number.startswith('+'):
            user = db.query(TelegramUser).filter(TelegramUser.phone_number == phone_number[1:]).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found with this phone number")
    
    return get_user_progress_data(user, db)