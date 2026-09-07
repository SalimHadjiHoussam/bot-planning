import requests

TOKEN = "8689345394:AAGnTvrCBtLBNqNC1uQy-ZZUnYX9umZU0eg"
CHAT_ID = "5962735174"

# 1. Vérification du Token auprès de Telegram
res_me = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe").json()
print("1. Résultat Bot Telegram :", res_me)

# 2. Envoi d'un message direct
res_msg = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={
        "chat_id": CHAT_ID,
        "text": "👋 Test direct du bot ! Est-ce que tu me reçois ?",
    },
).json()
print("2. Résultat Envoi Message :", res_msg)