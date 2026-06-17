
#!/bin/bash
cd /Users/user/Desktop/SpeakFlow/backend

# Get the bot token from settings.py
BOT_TOKEN=$(python3 -c "
from app.core.config import settings
print(settings.TELEGRAM_BOT_TOKEN)
" 2>&1)

echo "Bot token found: ${BOT_TOKEN:0:10}..."

# Check webhook info
echo "Checking webhook..."
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"

# Delete webhook
echo -e "\n\nDeleting webhook..."
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook"
echo
