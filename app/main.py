import os
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.api import analysis, admin, progress, auth
from app.services.questions import seed_default_questions
from app.telegram_bot import build_application, start_polling, stop_polling

logger = logging.getLogger("uvicorn.error")

Base.metadata.create_all(bind=engine)

# Seed the default speaking-question bank on first boot.
_db = SessionLocal()
try:
    seed_default_questions(_db)
finally:
    _db.close()


# Run the Telegram bot in the same process as the API when RUN_BOT != "false".
# This lets both share a single Render free web service (the API binds $PORT to
# satisfy Render's HTTP health check; the bot long-polls as a background task).
RUN_BOT = os.getenv("RUN_BOT", "true").lower() not in {"false", "0", "no"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_app = None
    if RUN_BOT and settings.TELEGRAM_BOT_TOKEN:
        try:
            bot_app = build_application()
            await start_polling(bot_app)
            logger.info("Telegram bot polling started (embedded in API process).")
        except Exception:
            logger.exception("Failed to start Telegram bot; API continues without it.")
            bot_app = None
    else:
        logger.info("Telegram bot disabled (RUN_BOT=false or no token).")
    try:
        yield
    finally:
        if bot_app is not None:
            await stop_polling(bot_app)
            logger.info("Telegram bot polling stopped.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)
app.include_router(progress.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": "Welcome to SpeakFlow API", "version": settings.VERSION}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
