"""
Speaking-question source of truth.

The Telegram bot and the admin panel both read IELTS speaking questions
from the `speaking_questions` table. This module:
  * seeds a sensible default question bank on first run (so the bot always
    has content and the admin can see/edit them), and
  * exposes helpers the bot uses to pull active questions per part.
"""
import random
from sqlalchemy.orm import Session
from app.models import SpeakingQuestion

# Fallback bank — also used to seed the DB the first time it is empty.
DEFAULT_QUESTIONS: dict[int, list[str]] = {
    1: [
        "Tell me about your hobbies. What do you like to do in your free time?",
        "What kind of music do you like to listen to?",
        "Tell me about your family.",
        "What do you do for work or study?",
        "Tell me about your hometown.",
        "Do you prefer mornings or evenings? Why?",
        "How do you usually spend your weekends?",
    ],
    2: [
        "Describe a book you recently read. You should say: what the book is about, "
        "why you read it, what you liked about it, and explain if you would recommend it to others.",
        "Describe a trip you went on that you enjoyed. You should say: where you went, "
        "who you went with, what you did, and explain why you enjoyed it.",
        "Describe a person who has influenced you. You should say: who they are, "
        "how you know them, what they did, and explain why they influenced you.",
        "Describe a skill you would like to learn. You should say: what it is, "
        "why you want to learn it, how you would learn it, and how it would help you.",
    ],
    3: [
        "How has technology changed the way people read?",
        "What are the advantages and disadvantages of international travel?",
        "Do you think people rely too much on social media? Why or why not?",
        "How important is it for children to learn a second language?",
    ],
}

# Valid IELTS speaking parts.
VALID_PARTS = (1, 2, 3)


def seed_default_questions(db: Session) -> int:
    """Insert the default question bank if the table is empty. Returns inserted count."""
    if db.query(SpeakingQuestion).count() > 0:
        return 0
    inserted = 0
    for part, questions in DEFAULT_QUESTIONS.items():
        for text in questions:
            db.add(SpeakingQuestion(part=part, question=text, is_active=True))
            inserted += 1
    db.commit()
    return inserted


def get_active_questions(db: Session, part: int) -> list[SpeakingQuestion]:
    return (
        db.query(SpeakingQuestion)
        .filter(SpeakingQuestion.part == part, SpeakingQuestion.is_active == True)  # noqa: E712
        .all()
    )


def pick_question(db: Session, part: int) -> str:
    """Pick a random active question for the given part, falling back to defaults."""
    if part not in VALID_PARTS:
        part = 1
    questions = get_active_questions(db, part)
    if questions:
        return random.choice(questions).question
    return random.choice(DEFAULT_QUESTIONS.get(part, DEFAULT_QUESTIONS[1]))
