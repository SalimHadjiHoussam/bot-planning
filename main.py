import os
import time
import threading
import requests
from flask import Flask

app = Flask(__name__)

# Récupération du token depuis les variables d'environnement Render
TOKEN = os.getenv("TELEGRAM_TOKEN")

@app.route('/')
def home():
    return "Bot en ligne !"

def verifier_commandes_telegram():
    if not TOKEN:
        print("ERREUR : Aucun TELEGRAM_TOKEN trouvé dans les variables d'environnement.")
        return

    print("Boucle Telegram démarrée...")
    offset = None

    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
            params = {"timeout": 10, "offset": offset}
            res = requests.get(url, params=params).json()

            if res.get("ok") and res.get("result"):
                for update in res["result"]:
                    offset = update["update_id"] + 1
                    
                    if "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        texte = update["message"]["text"].strip().lower()
                        print(f"Message reçu : {texte}")

                        # Réponses du bot
                        if "planning" in texte or texte in ["/start", "/aujourdhui", "/demain"]:
                            msg = "📅 **Voici ton planning :**\n- Lundi : Cours à 9h\n- Mardi : TP à 14h"
                        elif "sport" in texte:
                            msg = "🏋️ **Séance du jour :** 45 min de musculation + cardio."
                        elif "repas" in texte:
                            msg = "🍲 **Idée repas :** Poulet, riz et légumes."
                        else:
                            msg = f"Reçu : {texte}. Tape 'planning' pour voir l'emploi du temps."

                        # Envoi de la réponse
                        send_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
                        requests.post(send_url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

        except Exception as e:
            print(f"Erreur dans la boucle Telegram : {e}")
        
        time.sleep(2)

# Lancement de la boucle Telegram en arrière-plan
threading.Thread(target=verifier_commandes_telegram, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)