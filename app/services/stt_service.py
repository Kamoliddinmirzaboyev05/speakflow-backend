import io
from groq import AsyncGroq
from app.core.config import settings


class STTService:
    def __init__(self):
        self.client = None
        
        if settings.GROQ_API_KEY:
            self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    
    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.ogg") -> str:
        try:
            if not self.client:
                raise Exception("GROQ_API_KEY not configured")
                
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = filename
            
            transcription = await self.client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3",
                language="en"
            )
            return transcription.text
        except Exception as e:
            print(f"STT error: {e}")
            raise Exception(f"Speech-to-text failed: {str(e)}")


stt_service = STTService()
