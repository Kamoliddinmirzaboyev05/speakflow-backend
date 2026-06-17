
import urllib.request
import json
from app.core.config import settings

BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN

print(f"Using bot token: {BOT_TOKEN[:10]}...")

# Check webhook info
url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
with urllib.request.urlopen(url) as f:
    data = json.load(f)
    print("getWebhookInfo:", json.dumps(data, indent=2))

# Delete the webhook
url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
with urllib.request.urlopen(url) as f:
    data = json.load(f)
    print("deleteWebhook:", json.dumps(data, indent=2))
