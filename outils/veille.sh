#!/usr/bin/env bash
# Veille de la guilde Ponant, lancée par cron toutes les 2 minutes :
#   attaquants du journal SSH -> réputation Vigie (enrichir.py) -> tickets (tickets.py, seuil 80).
# Le jeton est lu dans /etc/mistral/vigie.env : il n'est jamais écrit dans la crontab ni dans le dépôt.
set -uo pipefail

# Chemins absolus : cron ne connaît ni notre PATH, ni notre dossier courant
DEPOT="${DEPOT:-/guilde}"
OUTILS="$DEPOT/outils"
JOURNAL_AUTH="${JOURNAL_AUTH:-/var/log/mistral/auth.log}"
FICHIER_JETON="${FICHIER_JETON:-/etc/mistral/vigie.env}"
ETAT="${ETAT:-/var/lib/mistral/veille}"
SEUIL=80
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

log() {
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] $*"
}

if ! mkdir -p "$ETAT" || ! exec 9>"$ETAT/veille.lock"; then
    log "ERREUR : impossible de créer $ETAT/veille.lock (droits ?), veille arrêtée"
    exit 1
fi

# Verrou : si une veille tourne encore, celle-ci sort tout de suite, sans erreur
if ! flock -n 9; then
    log "veille précédente encore en cours : on passe ce tour"
    exit 0
fi

log "début de la veille"

# Le jeton, depuis le fichier protégé (set -a exporte VIGIE_TOKEN pour les outils Python)
if [[ ! -r "$FICHIER_JETON" ]]; then
    log "ERREUR : $FICHIER_JETON illisible, veille arrêtée"
    exit 3
fi
set -a
# shellcheck source=/dev/null
. "$FICHIER_JETON"
set +a

# Le Python du venv s'il a requests, sinon celui du système
if [[ -x "$DEPOT/.venv/bin/python" ]] && "$DEPOT/.venv/bin/python" -c 'import requests' 2>/dev/null; then
    PY="$DEPOT/.venv/bin/python"
else
    PY="$(command -v python3)"
fi

# 1. Toutes les adresses en échec du journal (-q : pas de rapport dans rapports/)
if ! "$OUTILS/top-attaquants.sh" -q -n 100000 "$JOURNAL_AUTH" > "$ETAT/attaquants.txt"; then
    log "ERREUR : top-attaquants.sh a échoué, veille arrêtée"
    exit 1
fi
log "étape 1 : $(grep -c . "$ETAT/attaquants.txt") adresses en échec dans $JOURNAL_AUTH"

# 2. Leur réputation ; code 4 = Vigie tombée en route, rapport partiel repris au tour suivant
"$PY" "$OUTILS/enrichir.py" --entree "$ETAT/attaquants.txt" --sortie "$ETAT"
code=$?
if [[ $code -eq 4 ]]; then
    log "étape 2 : Vigie indisponible, rapport partiel (adresses manquées reprises à la prochaine veille)"
elif [[ $code -ne 0 ]]; then
    log "ERREUR : enrichir.py a échoué (code $code), veille arrêtée"
    exit 1
else
    log "étape 2 : réputations à jour dans $ETAT/rapport.json"
fi

# 3. Un ticket, et un seul, pour chaque adresse dont le score atteint le seuil
"$PY" "$OUTILS/tickets.py" --rapport "$ETAT/rapport.json" --seuil "$SEUIL"
code=$?
if [[ $code -ne 0 ]]; then
    log "ERREUR : tickets.py a échoué (code $code)"
    exit 1
fi
log "étape 3 : tickets vérifiés (seuil $SEUIL)"

log "fin de la veille"
