from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import jwt
import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from app.core.database import get_db
from app.core.config import settings
from app.models import TelegramUser, Admin
from app.api.admin import verify_password, get_password_hash, pwd_context

router = APIRouter(prefix="/auth", tags=["auth"])


class TelegramAuthRequest(BaseModel):
    initData: str


class AdminLoginRequest(BaseModel):
    email: str
    password: str


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_telegram_webapp_data(init_data: str) -> dict:
    parsed = dict(parse_qsl(init_data))
    hash_val = parsed.pop("hash", None)
    
    data_check_arr = sorted([f"{k}={v}" for k, v in parsed.items()])
    data_check_string = "\n".join(data_check_arr)
    
    secret_key = hmac.new(b"WebAppData", settings.TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
    hmac_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(hmac_hash, hash_val or ""):
        raise HTTPException(status_code=401, detail="Invalid Telegram data")
    
    return parsed


@router.post("/telegram")
def auth_telegram(request: TelegramAuthRequest, db: Session = Depends(get_db)):
    try:
        data = verify_telegram_webapp_data(request.initData)
        
        user_data = json.loads(data.get("user", "{}"))
        telegram_id = user_data.get("id")
        first_name = user_data.get("first_name", "")
        last_name = user_data.get("last_name")
        username = user_data.get("username")
        
        db_user = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
        if not db_user:
            db_user = TelegramUser(
                telegram_id=telegram_id,
                first_name=first_name,
                last_name=last_name,
                username=username
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
        
        token_data = {
            "id": db_user.id,
            "telegramId": str(telegram_id),
            "role": "student"
        }
        
        access_token = create_access_token(token_data)
        
        return {
            "token": access_token,
            "user": {
                "id": db_user.id,
                "telegramId": str(telegram_id),
                "firstName": db_user.first_name,
                "lastName": db_user.last_name,
                "username": db_user.username,
                "nativeLanguage": db_user.native_language,
                "englishLevel": db_user.english_level,
                "targetBand": db_user.target_band,
                "role": "student"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/admin")
def auth_admin(request: AdminLoginRequest, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.email == request.email).first()
    
    if not admin:
        # If no admin exists with this email, check default credentials
        if request.email == "admin@speakflow.com" and request.password == "admin123":
            hashed_pw = get_password_hash(request.password)
            admin = Admin(email=request.email, hashed_password=hashed_pw)
            db.add(admin)
            db.commit()
            db.refresh(admin)
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Use bcrypt verification (consistent with admin.py)
    if not verify_password(request.password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token_data = {"id": admin.id, "email": admin.email, "role": "admin"}
    access_token = create_access_token(token_data)
    
    return {
        "token": access_token,
        "user": {"id": admin.id, "email": admin.email, "role": "admin"}
    }