
import urllib.request
import urllib.parse
import json
from app.core.config import settings

TOKEN = settings.TELEGRAM_BOT_TOKEN
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"


def call_api(method, params=None):
    url = f"{BASE_URL}/{method}"
    data = None
    if params:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=10) as f:
        return json.loads(f.read().decode())


# Step 1: Delete any existing webhook and drop pending updates
print("Deleting webhook and dropping pending updates...")
response = call_api("deleteWebhook", {"drop_pending_updates": "true"})
print(f"Response: {json.dumps(response, indent=2)}")

# Step 2: Check bot info
print("\nGetting bot info...")
response = call_api("getMe")
print(f"Response: {json.dumps(response, indent=2)}")

print("\nAll done!")
