# SpeakFlow Backend

## Setup Instructions

### 1. Create a Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
Copy the example env file and edit it:
```bash
cp .env.example .env
# Edit .env with your actual API keys!
```

#### Required Keys:
- `OPENAI_API_KEY`: OpenAI API key for speech-to-text and AI analysis
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from @BotFather

#### Optional Keys:
- `ANTHROPIC_API_KEY`: For Claude AI instead of GPT

### 4. Run the FastAPI Server
```bash
python -m app.main
```
The server will start at http://localhost:8000

### 5. Run the Telegram Bot
In a new terminal:
```bash
cd backend
source venv/bin/activate
python -m app.telegram_bot
```

## API Endpoints

### Analysis
- `POST /api/v1/analysis/`: Analyze IELTS speaking transcript

### Progress
- `GET /api/v1/progress/user/{telegram_id}`: Get user progress and stats

### Admin
- `GET /api/v1/admin/users`: List all users
- `GET /api/v1/admin/sessions`: List practice sessions
- `GET /api/v1/admin/results`: List analysis results
- `GET /api/v1/admin/stats`: Get platform statistics

## Project Structure
```
backend/
├── app/
│   ├── api/
│   │   ├── analysis.py    # Analysis endpoints
│   │   ├── admin.py       # Admin endpoints
│   │   └── progress.py    # Progress tracking
│   ├── core/
│   │   ├── config.py      # Settings
│   │   └── database.py    # Database setup
│   ├── models/
│   │   └── models.py      # SQLAlchemy models
│   ├── schemas/
│   │   └── schemas.py     # Pydantic models
│   ├── services/
│   │   ├── ai_service.py  # AI analysis
│   │   └── stt_service.py # Speech to text
│   ├── telegram_bot.py    # Telegram bot
│   └── main.py            # FastAPI entry point
├── venv/
├── requirements.txt
└── .env.example
```
