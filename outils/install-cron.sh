#!/usr/bin/env bash
# ==============================================================================
# Script d'installation automatique des tâches cron pour la Guilde
# ==============================================================================
set -euo pipefail

# Définition des tâches cron et de leurs scripts cibles
CRON_JOB_VEILLE="*/2 * * * * /guilde/outils/veille.sh"
TARGET_VEILLE="/guilde/outils/veille.sh"

CRON_JOB_SAUVEGARDE="30 4 * * * /outils/sauvegarde.sh"
TARGET_SAUVEGARDE="/outils/sauvegarde.sh"

# Vérification que le script N'EST PAS exécuté en root
if [[ $EUID -eq 0 ]]; then
   echo "[!] Erreur : Ce script ne doit pas être exécuté en tant que root (ou via sudo)." >&2
   echo "    Veuillez le lancer avec votre utilisateur standard ($USER)." >&2
   exit 1
fi

echo "=== Installation des tâches Cron ==="

# 1. Vérification et préparation des scripts cibles
check_and_chmod() {
    local target="$1"
    if [[ -f "$target" ]]; then
        if [[ ! -x "$target" ]]; then
            echo "[+] Activation des droits d'exécution sur $target"
            chmod +x "$target"
        fi
    else
        echo "[!] Avertissement : Le script '$target' n'existe pas encore à cet emplacement."
    fi
}

check_and_chmod "$TARGET_VEILLE"
check_and_chmod "$TARGET_SAUVEGARDE"

# 2. Lecture de la crontab actuelle (gestion du cas sans crontab active)
EXISTING_CRON=$(crontab -l 2>/dev/null || true)

# 3. Identification des tâches à ajouter
JOBS_TO_ADD=""

if echo "$EXISTING_CRON" | grep -Fq "$CRON_JOB_VEILLE"; then
    echo "[=] La tâche 'veille.sh' est déjà présente dans la crontab."
else
    echo "[+] Ajout prévu pour 'veille.sh' : $CRON_JOB_VEILLE"
    JOBS_TO_ADD="${JOBS_TO_ADD}${CRON_JOB_VEILLE}"$'\n'
fi

if echo "$EXISTING_CRON" | grep -Fq "$CRON_JOB_SAUVEGARDE"; then
    echo "[=] La tâche 'sauvegarde.sh' est déjà présente dans la crontab."
else
    echo "[+] Ajout prévu pour 'sauvegarde.sh' : $CRON_JOB_SAUVEGARDE"
    JOBS_TO_ADD="${JOBS_TO_ADD}${CRON_JOB_SAUVEGARDE}"$'\n'
fi

# 4. Si toutes les tâches sont déjà installées, on quitte
if [[ -z "${JOBS_TO_ADD//[$'\t\r\n ']/}" ]]; then
    echo "[✔] Toutes les tâches cron sont déjà installées. Aucune modification nécessaire."
    exit 0
fi

# 5. Sauvegarde de précaution si une crontab existait
if [[ -n "$EXISTING_CRON" ]]; then
    BACKUP_PATH="/tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt"
    echo "$EXISTING_CRON" > "$BACKUP_PATH"
    echo "[+] Sauvegarde de la crontab existante dans : $BACKUP_PATH"
fi

# 6. Mise à jour de la crontab sans détruire l'existant
NEW_CRON=$(printf "%s\n%s" "$EXISTING_CRON" "$JOBS_TO_ADD" | grep -v '^$')
echo "$NEW_CRON" | crontab -

echo "[✔] Crontab mise à jour avec succès !"

