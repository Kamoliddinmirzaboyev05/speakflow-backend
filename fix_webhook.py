
import os
import requests
from app.core.config import settings

# First, check webhook status
url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getWebhookInfo"
response = requests.get(url)
print("getWebhookInfo response:", response.json())

# Delete the webhook if any
url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/deleteWebhook"
response = requests.get(url)
print("deleteWebhook response:", response.json())
