#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage : $0 FICHIER_CSV DOSSIER" >&2
    exit 2
}

if [[ $# -ne 2 ]]; then
    usage
fi

CSV="$1"
DEST="$2"

TEMP=$(mktemp)
#on crée un fichier temporaire pour ne pas modifier directement le fichier original 

nettoyer() {
    rm -f -- "$TEMP"
}
#focntion pour supprimer le ficher temporaire

echo "Fichier temporaire : $TEMP"
trap nettoyer EXIT


# Vérification de l'existence du CSV
if [[ ! -f "$CSV" || ! -r "$CSV" ]]; then
    echo "Erreur : fichier CSV absent ou illisible" >&2
    exit 2
fi

# Par défaut, on utilise le CSV original
ENTREE="$CSV"

# Si le fichier n'est pas en UTF-8, on le convertit
if ! iconv -f utf-8 -t utf-8 "$CSV" >/dev/null 2>&1; then
    iconv -f latin1 -t utf-8 "$CSV" > "$TEMP"
    ENTREE="$TEMP"
    echo "Conversion Latin-1 vers UTF-8 effectuée"
else
    echo "Le fichier est déjà en UTF-8"
fi


# Choix de l'interpréteur Python
if [[ -x /guilde/.venv/bin/python ]]; then
    PYTHON="/guilde/.venv/bin/python"
else
    PYTHON="python3"
fi

# Exécution du script Python avec le CSV préparé
# Utilisation du vrai script par défaut, ou d'un simulateur pour les tests
SCRIPT_PY="${COMPTES_SCRIPT:-/guilde/outils/comptes.py}"

"$PYTHON" "$SCRIPT_PY" --csv "$ENTREE" --sortie "$DEST"

# Comptage des comptes créés et des lignes rejetées
COMPTES=$(( $(wc -l < "$DEST/comptes.csv") - 1 ))
REJETS=$(( $(wc -l < "$DEST/rejets.csv") - 1 ))

# Création du dossier de journalisation si nécessaire
mkdir -p /var/log/mistral

# Enregistrement du résultat dans le journal
echo "[$(date +%Y-%m-%dT%H:%M:%S)] $COMPTES comptes crees, $REJETS lignes rejetees" | tee -a /var/log/mistral/comptes.log













