import os
import requests

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

print("=" * 40)
print("TEST DU BOT TELEGRAM")
print("=" * 40)

if not TOKEN:
    print("ERREUR : TELEGRAM_TOKEN est introuvable")
    raise SystemExit(1)

if not CHAT_ID:
    print("ERREUR : TELEGRAM_CHAT_ID est introuvable")
    raise SystemExit(1)

try:
    r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=15)
    data = r.json()
    print("getMe :", data)
    if not data.get("ok"):
        raise SystemExit(1)

    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": "🧪 TEST RÉUSSI : le bot Telegram fonctionne."},
        timeout=15,
    )
    print("sendMessage :", r.json())
except Exception as e:
    print("Erreur :", e)
