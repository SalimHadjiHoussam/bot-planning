MISE A JOUR DU BOT
===================

1. Remplace ton ancien projet par les fichiers de ce ZIP.
2. Garde ton fichier planning.xlsx dans le meme dossier que main.py.
3. Sur ton hebergeur, ajoute :
   - TELEGRAM_TOKEN = ton NOUVEAU token BotFather
   - TELEGRAM_CHAT_ID = ton chat ID Telegram (pour lancer test.py uniquement)
4. IMPORTANT : revoque l'ancien token Telegram expose dans ton ancien projet et genere un nouveau token.
5. Redemarre/deploie le service.
6. Envoie /start au bot Telegram : ton chat_id sera automatiquement sauvegarde pour les rappels.

FONCTIONNEMENT :
- /planning : planning du jour
- /demain : planning du lendemain
- /rappel : test
- Rappel automatique toutes les 20 heures apres le demarrage du service
- Planning automatique du lendemain a 20h00 (heure du serveur Python)

ATTENTION : si ton hebergeur met le service en veille, les rappels ne pourront pas etre envoyes pendant cette veille.
