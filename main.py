import os
import time
import threading
import datetime
import requests
import pandas as pd
from flask import Flask

app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
EXCEL_PATH = "planning.xlsx"

@app.route('/')
def home():
    return "Bot Planning en ligne !"

def envoyer_message(chat_id, texte):
    if not TOKEN or not chat_id:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": texte, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erreur envoi message : {e}")

def charger_cours_du_jour(date_cible):
    """Extrait tous les cours de la date donnée depuis le fichier Excel."""
    if not os.path.exists(EXCEL_PATH):
        return "⚠️ Le fichier `planning.xlsx` est introuvable sur le serveur."

    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name='Semestre 1 - P1 - P2')
        
        # Trouver la ligne de la semaine correspondante
        ligne_semaine = None
        for idx in range(2, len(df)):
            cell_val = str(df.iloc[idx, 0])
            if "au" in cell_val:
                try:
                    dates_str = cell_val.split('\n')[-1] if '\n' in cell_val else cell_val
                    debut_str, fin_str = dates_str.split(' au ')
                    debut = datetime.datetime.strptime(debut_str.strip(), "%d/%m/%y").date()
                    fin = datetime.datetime.strptime(fin_str.strip(), "%d/%m/%y").date()
                    if debut <= date_cible <= fin:
                        ligne_semaine = idx
                        break
                except Exception:
                    continue

        if ligne_semaine is None:
            return f"Aucun cours trouvé dans le planning pour la date du {date_cible.strftime('%d/%m/%Y')}."

        # Mapping des colonnes pour les jours
        jours_colonnes = {
            0: (1, 8),    # Lundi
            1: (9, 17),   # Mardi
            2: (18, 24),  # Mercredi
            3: (25, 32),  # Jeudi
            4: (33, 40)   # Vendredi
        }

        jour_index = date_cible.weekday()
        if jour_index not in jours_colonnes:
            return f"Pas de cours le {date_cible.strftime('%A %d/%m/%Y')} (week-end)."

        col_start, col_end = jours_colonnes[jour_index]
        row_s1 = df.iloc[ligne_semaine]
        hours_row = df.iloc[1]

        cours_liste = []
        for col_idx in range(col_start, col_end + 1):
            val = row_s1.iloc[col_idx]
            if pd.notna(val) and str(val).strip() != "":
                horaire = hours_row.iloc[col_idx]
                horaire_str = str(horaire) if pd.notna(horaire) else "Horaire non précisé"
                
                # Nettoyage du texte du cours
                details = str(val).strip()
                cours_liste.append(f"⏰ **{horaire_str}**\n{details}")

        if not cours_liste:
            return f"🎉 Aucun cours prévu le {date_cible.strftime('%d/%m/%Y')} !"

        nom_jour = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"][jour_index]
        reponse = f"📅 **Planning du {nom_jour} {date_cible.strftime('%d/%m/%Y')} :**\n\n"
        reponse += "\n\n-------------------\n\n".join(cours_liste)
        return reponse

    except Exception as e:
        return f"Erreur lors de la lecture du fichier Excel : {e}"

def gestionnaire_telegram():
    if not TOKEN:
        print("ERREUR : TELEGRAM_TOKEN non défini !")
        return

    offset = None
    chat_ids_enregistres = set()

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
                        chat_ids_enregistres.add(chat_id)
                        texte = update["message"]["text"].strip().lower()

                        aujourdhui = datetime.date.today()

                        if texte in ["/aujourdhui", "aujourdhui", "planning", "/planning", "/start"]:
                            msg = charger_cours_du_jour(aujourdhui)
                            envoyer_message(chat_id, msg)

                        elif texte in ["/demain", "demain"]:
                            demain = aujourdhui + datetime.timedelta(days=1)
                            msg = charger_cours_du_jour(demain)
                            envoyer_message(chat_id, msg)

                        elif "sport" in texte:
                            envoyer_message(chat_id, "🏋️ **Idée Sport :** 45 min de musculation / cardio !")
                        elif "repas" in texte or "plat" in texte:
                            envoyer_message(chat_id, "🍲 **Idée Repas :** Poulet riz légumes.")
                        else:
                            envoyer_message(chat_id, "Tape **/aujourdhui** ou **/demain** pour voir ton planning complet.")

        except Exception as e:
            print(f"Erreur Telegram : {e}")

        time.sleep(2)

# Lancement du bot
threading.Thread(target=gestionnaire_telegram, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)