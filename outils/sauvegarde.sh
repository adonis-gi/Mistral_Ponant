#!/usr/bin/env bash
set -euo pipefail
usage() {
 echo "usage : $0 [-k N] SOURCE [DESTINATION]" >&2
 exit 1
}

log() {
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] $1" | tee -a /var/log/mistral/sauvegarde.log
}


GARDER=7

while getopts ":k:h" opt; do
    case "$opt" in
        k) GARDER="$OPTARG" ;;
        *) usage ;;
    esac
done

shift $((OPTIND - 1))



[[ $# -ge 1 ]] || usage
SOURCE="${1%/}"
#chemin relatif du dossier 
NAME=$(basename "$SOURCE")
# nom du dossier
PARENT=$(dirname "$SOURCE")
# chemin du dossier parent
DEST="${2:-/srv/sauvegardes}"
#dossier de destination et par defaut on met dans ~/srv/sauvegardes

if [[ ! -d "$SOURCE" ]]; then
    echo "Erreur : le dossier $SOURCE n'existe pas" >&2
    exit 2
fi
#condition si le chemin mis n'existe pas ou est invalide

mkdir -p "$DEST"
log "Début de la sauvegarde de $SOURCE"
DATE=$(date +%Y%m%d-%H%M%S)
FILE="${NAME}-${DATE}.tar.gz"

TEMP="$DEST/$FILE.part"

nettoyer() {
    if [[ -f "$TEMP" ]]; then
        rm -- "$TEMP"
    fi
}

trap nettoyer EXIT
tar -czvf "$TEMP" -C "$PARENT" "$NAME"
mv -- "$TEMP" "$DEST/$FILE"
# archivage du dossier comme demandé dans la consigne 
log "Archive créée : $DEST/$FILE"

while [[ $(find "$DEST" -maxdepth 1 -type f -name "${NAME}-*-*.tar.gz" -printf '%f\n' | wc -l) -gt "$GARDER" ]]; do

    ANCIENNE=$(find "$DEST" -maxdepth 1 -type f -name "${NAME}-*-*.tar.gz" | sort -r | tail -n 1)

    rm -- "$ANCIENNE"
    log "Archive supprimée : $ANCIENNE"
done
