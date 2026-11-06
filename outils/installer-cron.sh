#!/usr/bin/env bash
# ==============================================================================
# Installation des tâches cron de la guilde, dans le serveur (en root) :
#   - la veille toutes les 2 minutes ;
#   - la sauvegarde du partage chaque jour à 4:30.
# Relancé, il ne crée aucun doublon : les anciennes lignes de ces deux outils
# sont retirées avant d'ajouter les bonnes. Le jeton n'apparaît jamais ici.
# ==============================================================================
set -euo pipefail

TARGET_VEILLE="/guilde/outils/veille.sh"
TARGET_SAUVEGARDE="/guilde/outils/sauvegarde.sh"

CRON_JOB_VEILLE="*/2 * * * * $TARGET_VEILLE >> /var/log/mistral/veille.log 2>&1"
CRON_JOB_SAUVEGARDE="30 4 * * * $TARGET_SAUVEGARDE /srv/mistral/partage >> /var/log/mistral/sauvegarde-cron.log 2>&1"

echo "=== Installation des tâches Cron ==="

# 1. Vérification et préparation des scripts cibles
check_and_chmod() {
    local target="$1"
    if [[ ! -f "$target" ]]; then
        echo "[!] Erreur : le script '$target' est introuvable." >&2
        exit 1
    fi
    if [[ ! -x "$target" ]]; then
        echo "[+] Activation des droits d'exécution sur $target"
        chmod +x "$target"
    fi
}

check_and_chmod "$TARGET_VEILLE"
check_and_chmod "$TARGET_SAUVEGARDE"
mkdir -p /var/log/mistral

# 2. Lecture de la crontab actuelle (gestion du cas sans crontab active)
EXISTING_CRON=$(crontab -l 2>/dev/null || true)

# 3. Sauvegarde de précaution si une crontab existait
if [[ -n "$EXISTING_CRON" ]]; then
    BACKUP_PATH="/tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt"
    echo "$EXISTING_CRON" > "$BACKUP_PATH"
    echo "[+] Sauvegarde de la crontab existante dans : $BACKUP_PATH"
fi

# 4. On garde tout sauf les anciennes lignes de nos deux outils, puis on ajoute les bonnes :
#    une ligne modifiée est remplacée, jamais ajoutée en double
AUTRES=$(echo "$EXISTING_CRON" | grep -v -e 'outils/veille.sh' -e 'outils/sauvegarde.sh' | grep -v '^$' || true)
{
    if [[ -n "$AUTRES" ]]; then
        echo "$AUTRES"
    fi
    echo "$CRON_JOB_VEILLE"
    echo "$CRON_JOB_SAUVEGARDE"
} | crontab -

echo "[✔] Crontab à jour :"
crontab -l
