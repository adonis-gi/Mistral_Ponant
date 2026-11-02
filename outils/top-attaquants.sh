#!/bin/bash
set -euo pipefail

# 1. Valeurs par défaut
N=5
FILE="/var/log/mistral/auth.log"
RES="top-attaquants-$(date +%Y-%m-%d-%H-%M).txt"

# 2. Gestion de l'option -n avec getopts
while getopts "n:" opt; do
  case "$opt" in
    n)
      N="$OPTARG"
      ;;
    *)
      echo "Usage: $0 [-n N] [FICHIER]" >&2
      exit 1
      ;;
  esac
done

# Décalage des arguments traités par getopts
shift $((OPTIND - 1))

# 3. Récupération du fichier passé en argument positionnel (si présent)
if [ -n "$1" ]; then
  FILE="$1"
fi

# 4. Vérification de la lisibilité du fichier (Erreur code 2)
if [ ! -r "$FILE" ]; then
  echo "Erreur : Le fichier '$FILE' est introuvable ou illisible." >&2
  exit 2
fi

# 5. Extraction, comptage, tri et mise en forme (sans espace au début)
grep 'Failed password' "$FILE" | \
  awk '{ for (i = 1; i <= NF; i++) if ($i == "from") print $(i+1) }' | \
  sort | \
  uniq -c | \
  sort -rn | \
  head -n "$N" | \
  awk '{print $1, $2}' > "$RES"

echo "Résultats stockés dans $RES". >&2
