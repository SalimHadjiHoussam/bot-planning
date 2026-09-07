import datetime
import json
import os
import re
import threading
import time
from flask import Flask
import pandas as pd
import requests
import schedule

# Serveur Flask pour maintenir le Web Service Render actif
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot Telegram En Ligne !", 200


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# ================= CONFIGURATION =================
TOKEN = "8689345394:AAGnTvrCBtLBNqNC1uQy-ZZUnYX9umZU0eg"
CHAT_ID = "5962735174"
EXCEL_FILE = "planning.xlsx"
CONFIG_FILE = "user_config.json"
EXAMS_FILE = "examens.json"
# =================================================


def charger_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"groupe": "TOUT"}


def sauvegarder_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)


def charger_examens():
    if os.path.exists(EXAMS_FILE):
        with open(EXAMS_FILE, "r") as f:
            return json.load(f)
    return []


def sauvegarder_examens(examens):
    with open(EXAMS_FILE, "w") as f:
        json.dump(examens, f)


def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Erreur d'envoi Telegram : {e}")


def charger_et_parser_planning():
    if not os.path.exists(EXCEL_FILE):
        return pd.DataFrame()

    xls = pd.ExcelFile(EXCEL_FILE)
    sheet = (
        "Semestre 1 - P1 - P2"
        if "Semestre 1 - P1 - P2" in xls.sheet_names
        else xls.sheet_names[0]
    )
    df_s1 = pd.read_excel(EXCEL_FILE, sheet_name=sheet)

    days = df_s1.iloc[0].values
    hours = df_s1.iloc[1].values

    current_day = None
    col_days = []
    for d in days:
        if pd.notna(d):
            current_day = str(d).strip()
        col_days.append(current_day)

    current_hour = None
    col_hours = []
    for h in hours:
        if pd.notna(h):
            current_hour = str(h).strip().replace("/", "-").replace("h", ":")
        col_hours.append(current_hour)

    day_offsets = {
        "Lundi": 0,
        "Mardi": 1,
        "Mercredi": 2,
        "Jeudi": 3,
        "Vendredi": 4,
    }
    rows_data = []

    for row_idx in range(2, len(df_s1)):
        row = df_s1.iloc[row_idx]
        sem_info = str(row.iloc[0])
        if sem_info == "nan" or not sem_info.strip():
            continue

        match = re.search(
            r"(\d{2}/\d{2}/\d{2,4})\s+au\s+(\d{2}/\d{2}/\d{2,4})", sem_info
        )
        if not match:
            continue

        start_date_str = match.group(1)
        parts = start_date_str.split("/")
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        if year < 100:
            year += 2000
        monday_date = datetime.datetime(year, month, day)

        for col_idx in range(1, len(row)):
            cell_val = str(row.iloc[col_idx])
            if cell_val == "nan" or not cell_val.strip():
                continue

            day_name = col_days[col_idx]
            hour_range = col_hours[col_idx]
            if not day_name or not hour_range or day_name not in day_offsets:
                continue

            h_parts = hour_range.split("-")
            if len(h_parts) != 2:
                continue

            h_start, h_end = (
                h_parts[0].strip().zfill(5),
                h_parts[1].strip().zfill(5),
            )
            course_date = monday_date + datetime.timedelta(
                days=day_offsets[day_name]
            )
            date_str = course_date.strftime("%Y-%m-%d")

            lines = [
                line.strip() for line in cell_val.split("\n") if line.strip()
            ]
            salle = "GS"
            salle_match = re.search(
                r"\b(GS\s?\d+|Amphi\s?\w+)\b", cell_val, re.IGNORECASE
            )
            if salle_match:
                salle = salle_match.group(1).upper().replace(" ", "")

            type_cours = "CM"
            if re.search(r"\bTD\b", cell_val, re.IGNORECASE):
                type_cours = "TD"
            elif re.search(r"\bTP\b", cell_val, re.IGNORECASE):
                type_cours = "TP"

            groupe = "TOUT"
            grp_match = re.search(r"\b(G1|G2|G3)\b", cell_val, re.IGNORECASE)
            if grp_match:
                groupe = grp_match.group(1).upper()

            matiere = lines[0] if lines else "Cours"

            rows_data.append(
                {
                    "Date": date_str,
                    "Jour": day_name,
                    "Heure_Debut": h_start,
                    "Heure_Fin": h_end,
                    "Matiere": matiere,
                    "Type": type_cours,
                    "Groupe": groupe,
                    "Salle": salle,
                    "Raw": cell_val,
                }
            )

    df_result = pd.DataFrame(rows_data)
    if not df_result.empty:
        df_result = df_result.drop_duplicates(
            subset=["Date", "Heure_Debut", "Heure_Fin", "Raw"]
        ).reset_index(drop=True)
    return df_result


def filtrer_cours(df):
    if df.empty:
        return df
    cfg = charger_config()
    grp = cfg.get("groupe", "TOUT")
    if grp == "TOUT":
        return df

    return df[
        (df["Type"].astype(str).str.upper() == "CM")
        | (df["Groupe"].astype(str).str.upper() == f"G{grp}")
        | (df["Groupe"].astype(str).str.upper() == grp)
        | (df["Groupe"].astype(str).str.upper() == "TOUT")
    ]


def verifier_commandes_telegram():
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    try:
        res = requests.get(url, timeout=5).json()
        if not res.get("result"):
            return

        for update in res["result"]:
            message = update.get("message", {})
            text = message.get("text", "")
            update_id = update.get("update_id")

            if text.startswith("/groupe"):
                parts = text.split()
                if len(parts) > 1:
                    grp = parts[1].upper()
                    cfg = charger_config()
                    cfg["groupe"] = grp
                    sauvegarder_config(cfg)
                    envoyer_telegram(
                        f"✅ *Groupe mis à jour !*\nVous recevrez les notifications pour le **Groupe {grp}** ainsi que tous les CM."
                    )
                else:
                    envoyer_telegram(
                        "ℹ️ Usage : `/groupe 1`, `/groupe 2` ou `/groupe TOUT`."
                    )

            elif text == "/demain":
                demain = datetime.datetime.now() + datetime.timedelta(days=1)
                date_str = demain.strftime("%Y-%m-%d")
                df = charger_et_parser_planning()
                cours = filtrer_cours(df)
                if not cours.empty:
                    cours = cours[cours["Date"].astype(str) == date_str]

                cfg = charger_config()
                grp_txt = (
                    f" (Groupe {cfg['groupe']})"
                    if cfg["groupe"] != "TOUT"
                    else ""
                )

                if cours.empty:
                    msg = f"🎉 *Demain ({date_str})* : Aucun cours prévu !"
                else:
                    msg = f"📚 *PROGRAMME DE DEMAIN{grp_txt}* ({date_str}) :\n\n"
                    for _, row in cours.iterrows():
                        msg += f"• *{row['Heure_Debut']} - {row['Heure_Fin']}* : {row['Matiere']} ({row['Type']}) — Salle {row['Salle']}\n"
                envoyer_telegram(msg)

            elif text == "/aujourdhui":
                aujourdhui = datetime.datetime.now()
                date_str = aujourdhui.strftime("%Y-%m-%d")
                df = charger_et_parser_planning()
                cours = filtrer_cours(df)
                if not cours.empty:
                    cours = cours[cours["Date"].astype(str) == date_str]

                cfg = charger_config()
                grp_txt = (
                    f" (Groupe {cfg['groupe']})"
                    if cfg["groupe"] != "TOUT"
                    else ""
                )

                if cours.empty:
                    msg = f"🎉 *Aujourd'hui ({date_str})* : Aucun cours prévu !"
                else:
                    msg = f"📚 *PROGRAMME D'AUJOURD'HUI{grp_txt}* ({date_str}) :\n\n"
                    for _, row in cours.iterrows():
                        msg += f"• *{row['Heure_Debut']} - {row['Heure_Fin']}* : {row['Matiere']} ({row['Type']}) — Salle {row['Salle']}\n"
                envoyer_telegram(msg)

            elif text.startswith("/examen"):
                try:
                    parts = text.split(" ", 3)
                    date_ex, heure_ex, nom_ex = parts[1], parts[2], parts[3]
                    examens = charger_examens()
                    examens.append(
                        {"date": date_ex, "heure": heure_ex, "nom": nom_ex}
                    )
                    sauvegarder_examens(examens)
                    envoyer_telegram(
                        f"🚨 *Examen/CC ajouté !*\n📌 *{nom_ex}*\n📅 Date : {date_ex} à {heure_ex}"
                    )
                except Exception:
                    envoyer_telegram(
                        "⚠️ Format attendu : `/examen AAAA-MM-JJ HH:MM Nom_Examen`\nExemple : `/examen 2026-09-25 14:00 Statistique`"
                    )

            elif text == "/examens_liste":
                examens = charger_examens()
                if not examens:
                    envoyer_telegram(
                        "📝 Aucun examen ou CC enregistré pour le moment."
                    )
                else:
                    msg = "📝 *LISTE DES EXAMENS & CC :*\n\n"
                    for ex in examens:
                        msg += f"• *{ex['date']} à {ex['heure']}* : {ex['nom']}\n"
                    envoyer_telegram(msg)

            requests.get(f"{url}?offset={update_id + 1}", timeout=5)
    except requests.exceptions.RequestException as e:
        print(f"Réseau instable (réessai au prochain cycle) : {e}")
    except Exception as e:
        print(f"Erreur lors de la vérification des commandes : {e}")



def verifier_cours_imminents():
    maintenant = datetime.datetime.now()
    df = charger_et_parser_planning()
    cours = filtrer_cours(df)
    if cours.empty:
        return

    # Définition des 3 créneaux de rappel (60 min, 30 min et 10 min)
    rappels = [
        (60, "🔔 *Dans 1 heure*"),
        (30, "⏳ *Dans 30 minutes*"),
        (10, "🚨 *Dans 10 minutes*"),
    ]

    for minutes_avant, titre in rappels:
        cible = maintenant + datetime.timedelta(minutes=minutes_avant)
        date_str = cible.strftime("%Y-%m-%d")
        heure_str = cible.strftime("%H:%M")

        cours_trouves = cours[
            (cours["Date"].astype(str) == date_str)
            & (cours["Heure_Debut"].astype(str) == heure_str)
        ]

        for _, row in cours_trouves.iterrows():
            msg = (
                f"{titre} :\n\n"
                f"📖 *Matière :* {row['Matiere']}\n"
                f"🏷️ *Type :* {row['Type']}\n"
                f"⏰ *Horaire :* {row['Heure_Debut']} - {row['Heure_Fin']}\n"
                f"📍 *Salle :* {row['Salle']}"
            )
            envoyer_telegram(msg)







def rappel_du_soir():
    demain = datetime.datetime.now() + datetime.timedelta(days=1)
    date_str = demain.strftime("%Y-%m-%d")

    try:
        df = charger_et_parser_planning()
        cours_demain = filtrer_cours(df)
        if not cours_demain.empty:
            cours_demain = cours_demain[
                cours_demain["Date"].astype(str) == date_str
            ]

        cfg = charger_config()
        grp_txt = (
            f" (Groupe {cfg['groupe']})" if cfg["groupe"] != "TOUT" else ""
        )

        if cours_demain.empty:
            msg = f"🎉 *Demain ({date_str})* : Aucun cours prévu !"
        else:
            msg = f"📚 *PROGRAMME DE DEMAIN{grp_txt}* ({date_str}) :\n\n"
            for _, row in cours_demain.iterrows():
                msg += (
                    f"• *{row['Heure_Debut']} - {row['Heure_Fin']}* : "
                    f"{row['Matiere']} ({row['Type']}) — Salle {row['Salle']}\n"
                )

        envoyer_telegram(msg)
    except Exception as e:
        print(f"Erreur rappel du soir : {e}")


# Démarrer le serveur HTTP Flask dans un thread séparé
threading.Thread(target=run_flask, daemon=True).start()

# Programmateurs de tâches
schedule.every(1).minutes.do(verifier_cours_imminents)
schedule.every(5).seconds.do(verifier_commandes_telegram)
schedule.every().day.at("20:00").do(rappel_du_soir)

while True:
    schedule.run_pending()
    time.sleep(1)