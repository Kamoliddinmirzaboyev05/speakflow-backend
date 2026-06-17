from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
from telegram.request import HTTPXRequest
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.config import settings
from app.models import TelegramUser, PracticeSession, AnalysisResult
from app.services.ai_service import ai_service
from app.services.stt_service import stt_service
from app.services.questions import pick_question, seed_default_questions, DEFAULT_QUESTIONS
from contextlib import contextmanager
import random
import asyncio
import os

# States
(
    SET_NAME,
    SET_PHONE,
    SET_LANGUAGE,
    SET_LEVEL,
    SET_TARGET,
    CHOOSE_PRACTICE,
    PRACTICING
) = range(7)

# ── Safe DB context manager ─────────────────────────────────────────────────────

@contextmanager
def get_db_session():
    """Context manager that ensures the DB session is always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def with_db(func):
    """Decorator that provides a managed db session to handler functions."""
    import functools
    @functools.wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        with get_db_session() as db:
            return await func(update, context, db, *args, **kwargs)
    return wrapper

# Questions now live in the DB (speaking_questions table), managed via the
# admin panel. `pick_question` reads active questions per part and falls back
# to DEFAULT_QUESTIONS when none exist.


def _part_number(practice_mode: str) -> int:
    """Map 'part1'/'part2'/'part3' -> 1/2/3 (defaults to 1)."""
    digits = "".join(c for c in practice_mode if c.isdigit())
    return int(digits) if digits in {"1", "2", "3"} else 1


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    with get_db_session() as db:
        db_user = db.query(TelegramUser).filter(TelegramUser.telegram_id == user.id).first()
        if db_user:
            db.delete(db_user)
            db.commit()
    
    context.user_data.clear()
    
    await update.message.reply_text("✅ Ro'yxatdan o'tish yangilandi! Qaytadan boshlaylik.\n\nIsmingiz nima?")
    return SET_NAME


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    with get_db_session() as db:
        db_user = db.query(TelegramUser).filter(TelegramUser.telegram_id == user.id).first()
        
        if db_user and db_user.phone_number:
            # User already registered, go to practice menu
            keyboard = [
                [KeyboardButton("Part 1"), KeyboardButton("Part 2")],
                [KeyboardButton("Part 3"), KeyboardButton("📊 Dashboard")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text(
                f"Welcome back, {db_user.first_name}! 🎯\n\nWhich part of the IELTS Speaking test would you like to practice?",
                reply_markup=reply_markup
            )
            return CHOOSE_PRACTICE
    
    # First time or no phone, ask for name
    await update.message.reply_text(
        f"Hi! 👋 Welcome to SpeakFlow - your AI IELTS Speaking coach!\n\nFirst, what's your name?"
    )
    return SET_NAME


async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text
    context.user_data['name'] = name
    
    # Ask for phone number WITH the keyboard!
    contact_button = KeyboardButton("📱 Share my phone number", request_contact=True)
    keyboard = [[contact_button]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        f"Nice to meet you, {name}! 😊\n\nNow, please share your phone number so I can remember you!",
        reply_markup=reply_markup
    )
    return SET_PHONE


async def set_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.contact:
        phone_number = update.message.contact.phone_number
    else:
        phone_number = update.message.text
    
    context.user_data['phone_number'] = phone_number
    name = context.user_data.get('name', 'User')
    
    user = update.effective_user
    with get_db_session() as db:
        # Save user to DB
        db_user = db.query(TelegramUser).filter(TelegramUser.telegram_id == user.id).first()
        if not db_user:
            db_user = TelegramUser(
                telegram_id=user.id,
                first_name=name,
                last_name=user.last_name,
                username=user.username,
                phone_number=phone_number
            )
        else:
            db_user.first_name = name
            db_user.phone_number = phone_number
        db.add(db_user)
        db.commit()
    
    # Ask for native language
    keyboard = [
        [KeyboardButton("Uzbek"), KeyboardButton("Russian")],
        [KeyboardButton("English"), KeyboardButton("Arabic")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "Great! Now, what's your native language?",
        reply_markup=reply_markup
    )
    return SET_LANGUAGE


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = update.message.text
    user = update.effective_user
    with get_db_session() as db:
        db_user = db.query(TelegramUser).filter(TelegramUser.telegram_id == user.id).first()
        if not db_user:
            await update.message.reply_text("Iltimos, avval /start buyrug'ini yuboring.")
            return ConversationHandler.END
        db_user.native_language = lang
        db.commit()
    
    keyboard = [
        [KeyboardButton("beginner"), KeyboardButton("intermediate")],
        [KeyboardButton("advanced")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Perfect! Now, what's your current English level?", reply_markup=reply_markup)
    return SET_LEVEL


async def set_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    level = update.message.text
    user = update.effective_user
    with get_db_session() as db:
        db_user = db.query(TelegramUser).filter(TelegramUser.telegram_id == user.id).first()
        if not db_user:
            await update.message.reply_text("Iltimos, avval /start buyrug'ini yuboring.")
            return ConversationHandler.END
        db_user.english_level = level
        db.commit()
    
    keyboard = [
        [KeyboardButton("5.5"), KeyboardButton("6.0"), KeyboardButton("6.5")],
        [KeyboardButton("7.0"), KeyboardButton("7.5"), KeyboardButton("8.0")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Excellent! What's your target IELTS band score?", reply_markup=reply_markup)
    return SET_TARGET


async def set_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    target = update.message.text
    user = update.effective_user
    with get_db_session() as db:
        db_user = db.query(TelegramUser).filter(TelegramUser.telegram_id == user.id).first()
        if not db_user:
            await update.message.reply_text("Iltimos, avval /start buyrug'ini yuboring.")
            return ConversationHandler.END
        db_user.target_band = target
        db.commit()
    
    keyboard = [
        [KeyboardButton("Part 1"), KeyboardButton("Part 2")],
        [KeyboardButton("Part 3"), KeyboardButton("📊 Dashboard")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        f"You're all set up! 🎯\n\nNow, which part of the IELTS Speaking test would you like to practice?",
        reply_markup=reply_markup
    )
    return CHOOSE_PRACTICE


def get_web_app_url() -> str | None:
    """Return a valid HTTPS Web App URL or None (Telegram rejects http://localhost)."""
    raw = (settings.WEB_APP_URL or "").strip().rstrip("/")
    if raw.startswith("https://"):
        return f"{raw}/"
    print(f"⚠️ WEB_APP_URL is not HTTPS ({raw!r}) — dashboard Web App button disabled.")
    return None


def build_dashboard_keyboard(extra_rows: list[list[KeyboardButton]] | None = None) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    web_app_url = get_web_app_url()
    if web_app_url:
        rows.append([KeyboardButton("📊 Open Dashboard", web_app=WebAppInfo(url=web_app_url))])
    else:
        rows.append([KeyboardButton("Back")])
    if extra_rows:
        rows.extend(extra_rows)
    elif web_app_url:
        rows.append([KeyboardButton("Back")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


async def choose_practice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    
    # Handle Skip button — go back to main menu
    if text == "Skip":
        return await new_practice(update, context)
    
    if text == "📊 Dashboard":
        web_app_url = get_web_app_url()
        if web_app_url:
            reply_markup = build_dashboard_keyboard()
            await update.message.reply_text(
                "Click the button below to open your progress dashboard!",
                reply_markup=reply_markup,
            )
        else:
            keyboard = [[KeyboardButton("Back")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text(
                "Dashboard hozircha faqat HTTPS orqali ochiladi.\n"
                "`.env` faylida `WEB_APP_URL` ni Vercel manzilingizga o'rnating.",
                reply_markup=reply_markup,
            )
        return CHOOSE_PRACTICE
    
    if text == "Back":
        keyboard = [
            [KeyboardButton("Part 1"), KeyboardButton("Part 2")],
            [KeyboardButton("Part 3"), KeyboardButton("📊 Dashboard")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("What would you like to do?", reply_markup=reply_markup)
        return CHOOSE_PRACTICE
    
    practice_mode = text.lower().replace(" ", "")
    context.user_data['practice_mode'] = practice_mode

    # Pull an active question for this part from the DB (admin-managed),
    # falling back to the built-in bank when the table has none.
    with get_db_session() as db:
        question = pick_question(db, _part_number(practice_mode))
    context.user_data['current_question'] = question
    
    keyboard = [[KeyboardButton("Skip")], [KeyboardButton("Back")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        f"Okay! Here's your question:\n\n🎤 {question}\n\nPlease send a voice message with your answer! 🎧",
        reply_markup=reply_markup
    )
    return PRACTICING


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    
    with get_db_session() as db:
        db_user = db.query(TelegramUser).filter(TelegramUser.telegram_id == user.id).first()
        
        if not db_user:
            return await start(update, context)
        
        await update.message.reply_text("🎧 Processing your voice message... This may take a moment!")
        
        voice_file = await update.message.voice.get_file()
        voice_bytes = await voice_file.download_as_bytearray()
        
        try:
            transcript = await stt_service.transcribe_audio(bytes(voice_bytes))
            await update.message.reply_text(f"✅ I heard:\n\"{transcript}\"\n\nNow analyzing...")
            
            practice_mode = context.user_data.get('practice_mode', 'part1')
            current_question = context.user_data.get('current_question', DEFAULT_QUESTIONS[1][0])
            
            session = PracticeSession(
                telegram_user_id=db_user.id,
                practice_mode=practice_mode,
                question=current_question
            )
            db.add(session)
            db.commit()
            
            analysis_data = await ai_service.analyze_ielts_speaking(
                transcript=transcript,
                native_language=db_user.native_language,
                english_level=db_user.english_level,
                target_band=db_user.target_band,
                practice_mode=practice_mode,
                question=current_question
            )
            
            result = AnalysisResult(
                session_id=session.id,
                transcript=transcript,
                analysis_data=analysis_data
            )
            db.add(result)
            db.commit()
            
            feedback = f"""📊 Feedback!

🎯 Band: {analysis_data['score_label']}
📈 Score: {analysis_data['overall_score']}/100

📝 Xulosa:
{analysis_data['summary']}

❌ Tuzatish kerak ({len(analysis_data.get('mistakes', []))} ta):
"""
            
            for mistake in analysis_data['mistakes'][:2]:
                feedback += f"- \"{mistake['wrong']}\" → \"{mistake['correct']}\"\n  Sabab: {mistake['explanation']}\n"
            
            if analysis_data.get('vocabulary_upgrades'):
                feedback += f"\n📚 Yaxshiroq so'zlar:\n"
                for upgrade in analysis_data['vocabulary_upgrades'][:1]:
                    feedback += f"- {upgrade['original']} → {', '.join(upgrade['better'])}\n  Misol: \"{upgrade['example']}\"\n"
            
            feedback += f"\n✨ Yaxshilangan javob:\n{analysis_data['improved_answer'][:300]}"
            feedback += f"\n\n🎯 Mini mashq:\n{analysis_data['mini_exercise']}"
            feedback += f"\n\n💪 Keyingi vazifa:\n{analysis_data['next_task']}\n"
            
            extra = [[KeyboardButton("New Practice"), KeyboardButton("Skip")]]
            if get_web_app_url():
                reply_markup = build_dashboard_keyboard(extra_rows=extra)
            else:
                keyboard = extra
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            
            await update.message.reply_text(feedback, reply_markup=reply_markup)
            return CHOOSE_PRACTICE
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print("=" * 60)
            print(f"❌ ERROR in handle_voice for user @{user.username or user.id}:")
            print(error_details)
            print("=" * 60)
            await update.message.reply_text(
                f"❌ Oops! Something went wrong.\n\n"
                f"📋 Error: {str(e)[:200]}\n\n"
                f"Please try again or contact support."
            )
            return PRACTICING


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Okay, let's start over!")
    return ConversationHandler.END


async def new_practice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [KeyboardButton("Part 1"), KeyboardButton("Part 2")],
        [KeyboardButton("Part 3"), KeyboardButton("📊 Dashboard")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Which part would you like to practice?", reply_markup=reply_markup)
    return CHOOSE_PRACTICE


def build_application():
    """Build and configure the Telegram Application (handlers attached).

    Returns the ready-to-run Application without starting polling, so it can
    be driven either standalone (main()) or embedded in the FastAPI process.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set!")

    # Ensure the question bank is populated so the bot always has content.
    with get_db_session() as db:
        seeded = seed_default_questions(db)
        if seeded:
            print(f"🌱 Seeded {seeded} default speaking questions.")
    
    # Check if proxy is configured via environment variables
    proxy_url = os.environ.get("TELEGRAM_PROXY") or os.environ.get("https_proxy") or os.environ.get("http_proxy")
    
    if proxy_url:
        print(f"🔌 Using proxy: {proxy_url}")
        request = HTTPXRequest(proxy_url=proxy_url, connect_timeout=30, read_timeout=30)
        application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).request(request).build()
    else:
        print("ℹ️ No proxy configured. Connecting directly...")
        request = HTTPXRequest(connect_timeout=60, read_timeout=60)
        application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).request(request).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CommandHandler('reset', reset)],
        states={
            SET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_name)],
            SET_PHONE: [
                MessageHandler(filters.CONTACT, set_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_phone)
            ],
            SET_LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_language)],
            SET_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_level)],
            SET_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_target)],
            CHOOSE_PRACTICE: [
                MessageHandler(filters.Regex('^(Part 1|Part 2|Part 3|📊 Dashboard|Back)$') & ~filters.COMMAND, choose_practice),
                MessageHandler(filters.Regex('^New Practice$') & ~filters.COMMAND, new_practice)
            ],
            PRACTICING: [
                MessageHandler(filters.VOICE, handle_voice),
                MessageHandler(filters.Regex('^(Skip|Back)$') & ~filters.COMMAND, choose_practice),
                MessageHandler(filters.Regex('^New Practice$') & ~filters.COMMAND, new_practice)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start), CommandHandler('reset', reset)]
    )
    
    application.add_handler(conv_handler)

    return application


async def start_polling(application):
    """Initialize + start polling on an already-built Application.

    Used both by standalone main() and by the FastAPI lifespan hook so the
    bot runs inside the same process/event loop as the web server.
    """
    print("✅ Telegram bot started!")
    print("⏳ Waiting for messages...")

    await application.initialize()
    # Drop pending updates and any leftover webhook to avoid getUpdates conflicts.
    print("Dropping pending updates...")
    await application.bot.delete_webhook(drop_pending_updates=True)

    await application.start()
    await application.updater.start_polling()


async def stop_polling(application):
    """Gracefully stop a polling Application."""
    await application.updater.stop()
    await application.stop()
    await application.shutdown()


async def main():
    application = build_application()
    await start_polling(application)

    # Keep the bot running until interrupted
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await stop_polling(application)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())