import json
from typing import Optional
from groq import AsyncGroq
from app.core.config import settings


class AIService:
    def __init__(self):
        self.client = None
        
        if settings.GROQ_API_KEY:
            self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    
    async def analyze_ielts_speaking(
        self,
        transcript: str,
        native_language: str,
        english_level: str,
        target_band: str,
        practice_mode: str,
        question: str
    ) -> dict:
        system_prompt = """You are SpeakFlow's IELTS Speaking coach AI. Analyze the student's spoken English transcript.

IMPORTANT: You must return your response in a HYBRID format — Uzbek labels with English analysis content. 
The student understands Uzbek, so all section headers and explanations should be in Uzbek/Latin.
The actual mistakes/corrections should remain in English.

IELTS CRITERIA YOU MUST COVER:
1. Task Response: Does the answer address the question?
2. Fluency & Coherence: Smooth delivery, logical organization
3. Lexical Resource (Vocabulary): Range and accuracy
4. Grammatical Range & Accuracy: Tenses, structures, articles
5. Pronunciation: Clarity, word stress

INSTRUCTIONS:
1. **Adapt complexity**:
   - Beginner: simple explanations, encouraging, 1-2 mistakes
   - Intermediate: detailed, 2-3 areas
   - Advanced: nuanced, high-level
2. **Tone**: Friendly, supportive coach
3. **Mistakes format**: Wrong → Correct with short explanation in Uzbek
4. **Improved answer**: 1 level higher than student, addressing same question
5. **Mini exercise**: Directly related to the main issue, in Uzbek

IMPORTANT: Return ONLY valid JSON, NO MARKDOWN, NO code blocks!

REQUIRED JSON STRUCTURE:
{
  "transcript": "exact student transcript",
  "language": "native_language",
  "level": "english_level",
  "learning_goal": "ielts",
  "goal_detail": "target_band",
  "overall_score": 0-100,
  "score_label": "Band X.X-X.X",
  "skill_scores": {
    "fluency": 0-100,
    "grammar": 0-100,
    "vocabulary": 0-100,
    "pronunciation": 0-100,
    "task_response": 0-100
  },
  "summary": "short summary in Uzbek — encouraging, highlighting strengths and areas to improve",
  "mistakes": [
    {
      "type": "grammar/vocab/fluency/pronunciation",
      "wrong": "the incorrect English phrase",
      "correct": "the corrected English phrase",
      "explanation": "short explanation in Uzbek (e.g. \"Bu yerda 'a' artiklini qo'shish kerak\")"
    }
  ],
  "vocabulary_upgrades": [
    {
      "original": "simple English word from transcript",
      "better": ["better_word1", "better_word2"],
      "example": "sentence in English using the better word"
    }
  ],
  "improved_answer": "rewritten better answer in English (1 level higher)",
  "mini_exercise": "specific exercise description in Uzbek",
  "next_task": "next IELTS question in English",
  "confidence_notes": "note about score estimation in Uzbek"
}"""

        user_prompt = f"""STUDENT PROFILE:
- Native language: {native_language}
- English level: {english_level}
- Learning goal: IELTS Speaking
- Target band: {target_band}
- Practice mode: {practice_mode}

IELTS QUESTION ASKED:
{question}

STUDENT'S TRANSCRIPT:
{transcript}

Analyze thoroughly and return JSON only!"""
        
        if self.client:
            try:
                completion = await self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
                
                content = completion.choices[0].message.content
                return self._parse_json_response(content)
            except Exception as e:
                print(f"Groq API error: {e}")
                return self._get_mock_response(transcript, native_language, english_level, target_band, practice_mode, question)
        else:
            return self._get_mock_response(transcript, native_language, english_level, target_band, practice_mode, question)
    
    def _parse_json_response(self, content: str) -> dict:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                parsed = json.loads(content[start:end+1])
            else:
                raise ValueError("Failed to parse AI response")
        
        # Ensure all required keys exist with defaults
        defaults = {
            "score_label": "Band 5.5-6.0",
            "overall_score": 65,
            "skill_scores": {"fluency": 60, "grammar": 65, "vocabulary": 70, "pronunciation": 60, "task_response": 70},
            "summary": "Yaxshi boshladingiz! Davom eting va ko'proq gapiring.",
            "mistakes": [],
            "vocabulary_upgrades": [],
            "improved_answer": "",
            "mini_exercise": "Ko'proq gapirishni mashq qiling.",
            "next_task": "Tell me about your hobbies.",
            "confidence_notes": "Taxminiy ball. Rasmiy IELTS bahosi emas."
        }
        
        # Merge defaults with parsed response
        for key, value in defaults.items():
            if key not in parsed:
                parsed[key] = value
        
        return parsed
    
    def _get_mock_response(
        self,
        transcript: str,
        native_language: str,
        english_level: str,
        target_band: str,
        practice_mode: str,
        question: str = ""
    ) -> dict:
        return {
            "transcript": transcript,
            "language": native_language,
            "level": english_level,
            "learning_goal": "ielts",
            "goal_detail": target_band,
            "overall_score": 60,
            "score_label": "Band 4.5-5.0",
            "skill_scores": {
                "fluency": 55,
                "grammar": 50,
                "vocabulary": 65,
                "pronunciation": 60,
                "task_response": 70
            },
            "summary": "Yaxshi boshlang'ich! Fikringizni aniq yetkazdingiz. Keyingi safar bir oz ko'proq gapiring va misol keltiring — band score tez o'sadi! 💪",
            "mistakes": [
                {
                    "type": "grammar",
                    "wrong": "I have big family",
                    "correct": "I have a big family",
                    "explanation": "Article 'a' qo'shish kerak — 'family' hisoblanadigan ot."
                },
                {
                    "type": "grammar",
                    "wrong": "we is happy",
                    "correct": "we are happy",
                    "explanation": "'We' bilan 'are' ishlatiladi, 'is' emas."
                }
            ],
            "vocabulary_upgrades": [
                {
                    "original": "big",
                    "better": ["large", "close-knit"],
                    "example": "I come from a large, close-knit family."
                }
            ],
            "improved_answer": "I come from a large family. I have two siblings and we all live together with our parents. We enjoy spending time together, especially during weekends when we go on trips or cook together.",
            "mini_exercise": "Oila a'zolaringizdan birini tasvirlab bering. 'outgoing', 'supportive' so'zlarini ishlating.",
            "next_task": "Tell me about a trip you have taken recently. Where did you go and what did you do?",
            "confidence_notes": "Taxminiy ball — faqat shu javob asosida. Rasmiy IELTS bahosi emas."
        }


ai_service = AIService()