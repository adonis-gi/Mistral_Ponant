
#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage : $0 [-k N] SOURCE [DESTINATION]" >&2
    exit 1
}

log() {
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] $1" | tee -a /var/log/mistral/sauvegarde.log
}


if getopts ":h" pot; then
    echo "Usage : $0 [-k N] SOURCE [DESTINATION]
Options :
  -k N          Nombre de sauvegardes à conserver (7 par défaut)
  -h            Afficher cette aide

Arguments :
  SOURCE        Dossier à sauvegarder
  DESTINATION   Dossier où stocker les archives (par défaut /srv/sauvegardes)

Exemple :
  $0 -k 3 /srv/mistral/partage /tmp/essai"
    exit
fi



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

# Récupération du nom du dossier à sauvegarder
NAME=$(basename "$SOURCE")

# Récupération du chemin parent pour utiliser tar avec l'option -C
PARENT=$(dirname "$SOURCE")

DEST="${2:-/srv/sauvegardes}"

# Vérification de l'existence du dossier source avant la sauvegarde
if [[ ! -d "$SOURCE" ]]; then
    echo "Erreur : le dossier $SOURCE n'existe pas" >&2
    exit 2
fi

mkdir -p "$DEST"
log "Début de la sauvegarde de $SOURCE"

DATE=$(date +%Y%m%d-%H%M%S)
FILE="${NAME}-${DATE}.tar.gz"

# Création d'un chemin temporaire pour éviter de conserver
# une archive incomplète si la compression échoue
TEMP="$DEST/$FILE.part"

nettoyer() {
    if [[ -f "$TEMP" ]]; then
        rm -- "$TEMP"
    fi
}

trap nettoyer EXIT

# Création de l'archive temporaire puis renommage en .tar.gz
# uniquement lorsque la compression est terminée
tar -czvf "$TEMP" -C "$PARENT" "$NAME"
mv -- "$TEMP" "$DEST/$FILE"
#creation de l'empreint sha256
sha256sum "$DEST/$FILE" > "$DEST/$FILE.sha256"
log "Archive créée : $DEST/$FILE"

# Tant que le nombre d'archives dépasse GARDER,
# on supprime la sauvegarde la plus ancienne
while [[ $(find "$DEST" -maxdepth 1 -type f -name "${NAME}-*-*.tar.gz" -printf '%f\n' | wc -l) -gt "$GARDER" ]]; do

    # Recherche des archives de la même source, triées
    # par nom décroissant, puis sélection de la dernière (la plus ancienne)
    ANCIENNE=$(find "$DEST" -maxdepth 1 -type f -name "${NAME}-*-*.tar.gz" | sort -r | tail -n 1)

    # Suppression de l'ancienne archive et enregistrement dans le journal
    rm -- "$ANCIENNE"
    log "Archive supprimée : $ANCIENNE"
done
