from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import AnalysisRequest, AnalysisResponse
from app.services.ai_service import ai_service

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/", response_model=AnalysisResponse)
async def analyze_speaking(request: AnalysisRequest, db: Session = Depends(get_db)):
    try:
        result = await ai_service.analyze_ielts_speaking(
            transcript=request.transcript,
            native_language=request.native_language,
            english_level=request.english_level,
            target_band=request.target_band,
            practice_mode=request.practice_mode,
            question=getattr(request, 'question', '')
        )
        return AnalysisResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
