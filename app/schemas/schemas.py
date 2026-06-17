from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Optional
from datetime import datetime


class AdminCreate(BaseModel):
    email: EmailStr
    password: str


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class AdminResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class SpeakingQuestionCreate(BaseModel):
    part: int
    question: str


class SpeakingQuestionUpdate(BaseModel):
    part: Optional[int] = None
    question: Optional[str] = None
    is_active: Optional[bool] = None


class SpeakingQuestionResponse(BaseModel):
    id: int
    part: int
    question: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisRequest(BaseModel):
    transcript: str = Field(..., description="Student's spoken English transcript")
    native_language: str = Field(..., description="Student's native language")
    english_level: str = Field(..., description="Student's English level: beginner, intermediate, advanced")
    target_band: str = Field(..., description="Target IELTS band score")
    practice_mode: str = Field(..., description="Practice mode: part1, part2, part3")
    question: str = Field(default="", description="The IELTS speaking question that was asked")


class Mistake(BaseModel):
    type: str
    wrong: str
    correct: str
    explanation: str


class VocabularyUpgrade(BaseModel):
    original: str
    better: List[str]
    example: str


class AnalysisResponse(BaseModel):
    transcript: str
    language: str
    level: str
    learning_goal: str
    goal_detail: str
    overall_score: int
    score_label: str
    skill_scores: Dict[str, int]
    summary: str
    mistakes: List[Mistake]
    vocabulary_upgrades: List[VocabularyUpgrade]
    improved_answer: str
    mini_exercise: str
    next_task: str
    confidence_notes: str


class AnalysisResultCreate(BaseModel):
    user_id: Optional[int] = None
    transcript: str
    analysis_data: AnalysisResponse
