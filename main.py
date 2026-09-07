import os
import re
import json
import time
import threading
import datetime

import requests
import pandas as pd
import schedule
from flask import Flask
from zoneinfo import ZoneInfo

app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
EXCEL_PATH = "planning.xlsx"
USERS_FILE = "users.json"
TIMEZONE = ZoneInfo("Europe/Paris")
REMINDER_HOURS = 20


def maintenant():
    return datetime.datetime.now(TIMEZONE)


@app.route("/")
def home():
    return {"status": "online", "message": "Bot Planning Telegram en ligne", "telegram": bool(TOKEN)}


@app.route("/health")
def health():
    return {"status": "ok", "time": maintenant().strftime("%Y-%m-%d %H:%M:%S")}


def charger_utilisateurs():
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Erreur lecture users.json : {e}")
        return []


def sauvegarder_utilisateurs(utilisateurs):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(utilisateurs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erreur sauvegarde utilisateurs : {e}")


def ajouter_utilisateur(chat_id):
    utilisateurs = charger_utilisateurs()
    chat_id = str(chat_id)
    if chat_id not in utilisateurs:
        utilisateurs.append(chat_id)
        sauvegarder_utilisateurs(utilisateurs)
        print(f"Nouvel utilisateur enregistré : {chat_id}")


def verifier_telegram():
    if not TOKEN:
        print("TELEGRAM_TOKEN introuvable")
        return False
    try:
        r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=15)
        data = r.json()
        if data.get("ok"):
            print("Bot connecté : @" + data["result"].get("username", "inconnu"))
            return True
        print("Telegram refuse le token :", data)
    except Exception as e:
        print("Erreur connexion Telegram :", e)
    return False


def envoyer_message(chat_id, texte):
    if not TOKEN or not chat_id:
        print("TOKEN ou chat_id manquant")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": texte, "parse_mode": "Markdown"},
            timeout=20,
        )
        data = r.json()
        if data.get("ok"):
            print(f"Message envoyé à {chat_id}")
            return True
        print("Erreur Telegram :", data)
    except Exception as e:
        print("Erreur envoi Telegram :", e)
    return False


def charger_cours_du_jour(date_cible):
    if not os.path.exists(EXCEL_PATH):
        return "Le fichier planning.xlsx est introuvable sur le serveur."

    try:
        # On lit la première feuille par défaut pour rester compatible avec ton ancien fichier.
        df = pd.read_excel(EXCEL_PATH, header=None)
    except Exception as e:
        return f"Impossible de lire le planning.xlsx : {e}"

    pattern = re.compile(r"(\d{2}/\d{2}/\d{2})\s+au\s+(\d{2}/\d{2}/\d{2})")
    ligne_semaine = None

    for idx in range(len(df)):
        for col in range(df.shape[1]):
            val = str(df.iloc[idx, col])
            match = pattern.search(val)
            if match:
                try:
                    debut = datetime.datetime.strptime(match.group(1), "%d/%m/%y").date()
                    fin = datetime.datetime.strptime(match.group(2), "%d/%m/%y").date()
                    if debut <= date_cible <= fin:
                        ligne_semaine = idx
                        break
                except ValueError:
                    pass
        if ligne_semaine is not None:
            break

    if ligne_semaine is None:
        return f"Aucun planning trouvé pour le {date_cible.strftime('%d/%m/%Y')}."

    # Pour conserver la logique de ton planning actuel, on récupère les cellules non vides
    # de la ligne de la semaine. Cela évite de dépendre d'indices de colonnes fragiles.
    cours = []
    for col in range(df.shape[1]):
        valeur = df.iloc[ligne_semaine, col]
        if pd.notna(valeur):
            texte = str(valeur).strip()
            if texte and texte.lower() != "nan":
                cours.append(texte)

    jour = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"][date_cible.weekday()]

    if date_cible.weekday() >= 5:
        return f"Pas de cours prévu le {jour} {date_cible.strftime('%d/%m/%Y')}. Bon week-end !"

    if not cours:
        return f"Aucun cours trouvé pour le {jour} {date_cible.strftime('%d/%m/%Y')}."

    return f"📅 *Planning du {jour} {date_cible.strftime('%d/%m/%Y')}*\n\n" + "\n\n━━━━━━━━━━━━━━\n\n".join(cours)


def traiter_commande(chat_id, texte):
    texte = texte.strip().lower()
    ajouter_utilisateur(chat_id)
    today = maintenant().date()

    if texte.startswith("/start"):
        envoyer_message(chat_id, "👋 *Bienvenue sur le Bot Planning !*\n\n📅 /planning : planning du jour\n➡️ /demain : planning de demain\n🔔 /rappel : test des rappels\nℹ️ /aide : aide")
    elif texte in ["/planning", "planning", "/aujourdhui", "aujourdhui", "aujourd'hui", "/aujourd'hui"]:
        envoyer_message(chat_id, charger_cours_du_jour(today))
    elif texte in ["/demain", "demain"]:
        envoyer_message(chat_id, charger_cours_du_jour(today + datetime.timedelta(days=1)))
    elif texte in ["/rappel", "rappel", "/test"]:
        envoyer_message(chat_id, f"🔔 Test réussi. Les rappels sont configurés toutes les {REMINDER_HOURS} heures.")
    elif texte in ["/aide", "aide", "/help", "help"]:
        envoyer_message(chat_id, "📚 *Commandes*\n\n/planning\n/demain\n/rappel\n/aide")
    else:
        envoyer_message(chat_id, "Je n'ai pas compris. Utilise /planning, /demain ou /aide.")


def gestionnaire_telegram():
    # Ne pas quitter définitivement si Telegram est temporairement indisponible.
    offset = None
    print("Gestionnaire Telegram démarré")

    while True:
        try:
            if not TOKEN:
                print("TELEGRAM_TOKEN manquant. Nouvelle tentative dans 60 secondes.")
                time.sleep(60)
                continue

            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset

            r = requests.get(url, params=params, timeout=40)
            data = r.json()
            if not data.get("ok"):
                print("Erreur getUpdates :", data)
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message")
                if not message or "text" not in message:
                    continue
                chat_id = message["chat"]["id"]
                traiter_commande(chat_id, message["text"])

        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            print("Erreur boucle Telegram :", e)
            time.sleep(5)


def envoyer_rappel_automatique():
    utilisateurs = charger_utilisateurs()
    if not utilisateurs:
        print("Aucun utilisateur enregistré pour les rappels")
        return

    heure = maintenant().strftime("%H:%M")
    message = f"🔔 *RAPPEL AUTOMATIQUE*\n\nIl est {heure}. N'oublie pas de consulter ton planning.\n\n📅 /planning\n➡️ /demain"
    for chat_id in utilisateurs:
        envoyer_message(chat_id, message)
        time.sleep(0.5)


def envoyer_planning_demain():
    utilisateurs = charger_utilisateurs()
    demain = maintenant().date() + datetime.timedelta(days=1)
    planning = charger_cours_du_jour(demain)
    message = f"🌙 *TON PLANNING DE DEMAIN*\n\n{planning}"
    for chat_id in utilisateurs:
        envoyer_message(chat_id, message)
        time.sleep(0.5)


def gestionnaire_rappels():
    print("Gestionnaire des rappels démarré")
    schedule.every(REMINDER_HOURS).hours.do(envoyer_rappel_automatique)
    schedule.every().day.at("20:00").do(envoyer_planning_demain)

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print("Erreur système rappel :", e)
        time.sleep(10)


def demarrer_services():
    print("=" * 50)
    print("DEMARRAGE DU BOT PLANNING")
    print("=" * 50)
    print("Planning trouvé :", os.path.exists(EXCEL_PATH))
    print("Token présent :", bool(TOKEN))

    threading.Thread(target=gestionnaire_telegram, daemon=True, name="TelegramThread").start()
    threading.Thread(target=gestionnaire_rappels, daemon=True, name="ReminderThread").start()


# Démarre les services une seule fois, y compris avec gunicorn.
demarrer_services()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
