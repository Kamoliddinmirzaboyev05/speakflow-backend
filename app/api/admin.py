from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.database import get_db
from app.core.config import settings
from app.models import TelegramUser, PracticeSession, AnalysisResult, Admin, SpeakingQuestion
from app.api.progress import get_analysis_score_safe, get_analysis_data_safe
from app.schemas.schemas import (
    AdminCreate, AdminResponse, Token,
    SpeakingQuestionCreate, SpeakingQuestionUpdate, SpeakingQuestionResponse
)


def _compute_streak(session_dates: list) -> int:
    """Consecutive-day practice streak ending today or yesterday."""
    day_set = {d.date() for d in session_dates if d is not None}
    if not day_set:
        return 0
    cursor = datetime.utcnow().date()
    if cursor not in day_set:
        cursor = cursor - timedelta(days=1)
    streak = 0
    while cursor in day_set:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak

router = APIRouter(prefix="/admin", tags=["admin"])

# Password hashing and JWT
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/admin/login")

# JWT helper functions
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str):
    return pwd_context.hash(password)

def get_admin(db: Session, email: str):
    return db.query(Admin).filter(Admin.email == email).first()

async def get_current_admin(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    admin = get_admin(db, email=email)
    if admin is None:
        raise credentials_exception
    return admin

# Admin Auth Endpoints
@router.post("/register", response_model=AdminResponse)
def create_admin(admin: AdminCreate, db: Session = Depends(get_db)):
    db_admin = get_admin(db, email=admin.email)
    if db_admin:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = get_password_hash(admin.password)
    db_admin = Admin(email=admin.email, hashed_password=hashed_password)
    db.add(db_admin)
    db.commit()
    db.refresh(db_admin)
    return db_admin

@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    admin = get_admin(db, email=form_data.username)
    if not admin or not verify_password(form_data.password, admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": admin.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=AdminResponse)
async def read_admin_me(current_admin: Admin = Depends(get_current_admin)):
    return current_admin

# Admin Stats & Data Endpoints
@router.get("/users", response_model=List[dict])
def get_all_users(db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)):
    users = db.query(TelegramUser).all()
    out = []
    for u in users:
        sessions = (
            db.query(PracticeSession)
            .filter(PracticeSession.telegram_user_id == u.id)
            .order_by(PracticeSession.created_at.desc())
            .all()
        )
        scores = [s for s in (get_analysis_score_safe(x.analysis_result) for x in sessions) if s is not None]
        out.append({
            "id": u.id,
            "telegram_id": u.telegram_id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "username": u.username,
            "phone_number": u.phone_number,
            "native_language": u.native_language,
            "english_level": u.english_level,
            "target_band": u.target_band,
            "is_active": u.is_active,
            "created_at": u.created_at,
            # Aggregates for an at-a-glance roster.
            "total_sessions": len(sessions),
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "best_score": max(scores) if scores else None,
            "last_active": sessions[0].created_at if sessions else None,
        })
    return out


@router.get("/users/{user_id}", response_model=dict)
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Full per-student profile: identity, computed stats, score history, and recent sessions."""
    u = db.query(TelegramUser).filter(TelegramUser.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Student not found")

    sessions = (
        db.query(PracticeSession)
        .filter(PracticeSession.telegram_user_id == u.id)
        .order_by(PracticeSession.created_at.desc())
        .all()
    )

    session_list = []
    scores = []
    part_counts = {1: 0, 2: 0, 3: 0}
    for s in sessions:
        score = get_analysis_score_safe(s.analysis_result)
        if score is not None:
            scores.append(score)
        digits = "".join(c for c in (s.practice_mode or "") if c.isdigit())
        if digits in {"1", "2", "3"}:
            part_counts[int(digits)] += 1
        session_list.append({
            "id": s.id,
            "practice_mode": s.practice_mode,
            "question": s.question,
            "score": score,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })

    latest_analysis = None
    if sessions and sessions[0].analysis_result:
        data = get_analysis_data_safe(sessions[0].analysis_result)
        if data:
            latest_analysis = {
                "id": sessions[0].analysis_result.id,
                "transcript": sessions[0].analysis_result.transcript,
                "analysis_data": data,
                "created_at": sessions[0].analysis_result.created_at.isoformat()
                if sessions[0].analysis_result.created_at else None,
            }

    return {
        "user": {
            "id": u.id,
            "telegram_id": u.telegram_id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "username": u.username,
            "phone_number": u.phone_number,
            "native_language": u.native_language,
            "english_level": u.english_level,
            "target_band": u.target_band,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        },
        "stats": {
            "total_sessions": len(sessions),
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "best_score": max(scores) if scores else None,
            "latest_score": scores[0] if scores else None,
            "streak": _compute_streak([s.created_at for s in sessions]),
            "last_active": sessions[0].created_at.isoformat() if sessions and sessions[0].created_at else None,
            "part_counts": part_counts,
        },
        # Oldest -> newest for charting.
        "score_history": [
            {"score": s["score"], "created_at": s["created_at"]}
            for s in reversed(session_list) if s["score"] is not None
        ],
        "sessions": session_list[:30],
        "latest_analysis": latest_analysis,
    }

@router.get("/sessions", response_model=List[dict])
def get_all_sessions(db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)):
    sessions = db.query(PracticeSession).order_by(PracticeSession.created_at.desc()).limit(100).all()
    return [
        {
            "id": s.id,
            "telegram_user_id": s.telegram_user_id,
            "practice_mode": s.practice_mode,
            "question": s.question,
            "created_at": s.created_at
        }
        for s in sessions
    ]

@router.get("/results", response_model=List[dict])
def get_all_results(db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)):
    results = db.query(AnalysisResult).order_by(AnalysisResult.created_at.desc()).limit(100).all()
    out = []
    for r in results:
        session = r.session
        user = session.telegram_user if session else None
        student_name = None
        if user:
            student_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username
        out.append({
            "id": r.id,
            "session_id": r.session_id,
            "telegram_user_id": session.telegram_user_id if session else None,
            "student_name": student_name,
            "practice_mode": session.practice_mode if session else None,
            "question": session.question if session else None,
            "transcript": r.transcript,
            "score": get_analysis_score_safe(r),
            "analysis_data": r.analysis_data,
            "created_at": r.created_at,
        })
    return out


@router.get("/analytics", response_model=dict)
def get_analytics(db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)):
    """Aggregated metrics for the analytics dashboard (charts + KPIs)."""
    sessions = db.query(PracticeSession).all()
    results = db.query(AnalysisResult).all()
    user_count = db.query(TelegramUser).count()
    active_questions = db.query(SpeakingQuestion).filter(SpeakingQuestion.is_active == True).count()  # noqa: E712

    # Sessions per day, last 14 days.
    today = datetime.utcnow().date()
    day_index = {(today - timedelta(days=i)): 0 for i in range(13, -1, -1)}
    for s in sessions:
        if s.created_at:
            d = s.created_at.date()
            if d in day_index:
                day_index[d] += 1
    sessions_per_day = [{"date": d.isoformat(), "count": c} for d, c in sorted(day_index.items())]

    # Scores: distribution + average.
    scores = [s for s in (get_analysis_score_safe(r) for r in results) if s is not None]
    buckets = [
        {"range": "0-49", "count": 0},
        {"range": "50-59", "count": 0},
        {"range": "60-69", "count": 0},
        {"range": "70-79", "count": 0},
        {"range": "80-100", "count": 0},
    ]
    for sc in scores:
        if sc < 50:
            buckets[0]["count"] += 1
        elif sc < 60:
            buckets[1]["count"] += 1
        elif sc < 70:
            buckets[2]["count"] += 1
        elif sc < 80:
            buckets[3]["count"] += 1
        else:
            buckets[4]["count"] += 1

    # Practice-part distribution.
    part_dist = {"Part 1": 0, "Part 2": 0, "Part 3": 0, "Other": 0}
    for s in sessions:
        digits = "".join(c for c in (s.practice_mode or "") if c.isdigit())
        if digits == "1":
            part_dist["Part 1"] += 1
        elif digits == "2":
            part_dist["Part 2"] += 1
        elif digits == "3":
            part_dist["Part 3"] += 1
        else:
            part_dist["Other"] += 1

    # Active users in the last 7 days.
    week_ago = datetime.utcnow() - timedelta(days=7)
    active_user_ids = {
        s.telegram_user_id for s in sessions
        if s.created_at and s.created_at.replace(tzinfo=None) >= week_ago and s.telegram_user_id
    }

    return {
        "kpis": {
            "total_users": user_count,
            "total_sessions": len(sessions),
            "total_analyses": len(results),
            "active_questions": active_questions,
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "active_users_7d": len(active_user_ids),
        },
        "sessions_per_day": sessions_per_day,
        "score_distribution": buckets,
        "part_distribution": [{"name": k, "value": v} for k, v in part_dist.items()],
    }

@router.get("/stats", response_model=dict)
def get_stats(db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)):
    user_count = db.query(TelegramUser).count()
    session_count = db.query(PracticeSession).count()
    result_count = db.query(AnalysisResult).count()
    question_count = db.query(SpeakingQuestion).count()
    return {
        "total_users": user_count,
        "total_sessions": session_count,
        "total_analyses": result_count,
        "total_questions": question_count
    }

# Speaking Question CRUD Endpoints
@router.get("/questions", response_model=List[SpeakingQuestionResponse])
def get_speaking_questions(
    part: int | None = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    query = db.query(SpeakingQuestion)
    if part:
        query = query.filter(SpeakingQuestion.part == part)
    return query.order_by(SpeakingQuestion.part, SpeakingQuestion.created_at.desc()).all()

@router.post("/questions", response_model=SpeakingQuestionResponse)
def create_speaking_question(
    question: SpeakingQuestionCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    db_question = SpeakingQuestion(part=question.part, question=question.question)
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question

@router.get("/questions/{question_id}", response_model=SpeakingQuestionResponse)
def get_speaking_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    question = db.query(SpeakingQuestion).filter(SpeakingQuestion.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question

@router.put("/questions/{question_id}", response_model=SpeakingQuestionResponse)
def update_speaking_question(
    question_id: int,
    question_update: SpeakingQuestionUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    db_question = db.query(SpeakingQuestion).filter(SpeakingQuestion.id == question_id).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    update_data = question_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_question, key, value)
    
    db.commit()
    db.refresh(db_question)
    return db_question

@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_speaking_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    db_question = db.query(SpeakingQuestion).filter(SpeakingQuestion.id == question_id).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(db_question)
    db.commit()
