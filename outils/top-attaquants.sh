#!/bin/bash
set -euo pipefail

# Fonction d'affichage de l'aide
afficher_aide() {
  cat << EOF
Usage: $(basename "$0") [-h] [-n N] [FICHIER]

Analyse un fichier de log d'authentification pour identifier les IP ayant le plus grand nombre d'échecs de connexion ("Failed password").

Options:
  -h          Affiche cette aide et quitte.
  -n N        Nombre d'attaquants à afficher (défaut : 5).

Arguments:
  FICHIER     Chemin du fichier log à analyser (défaut : /var/log/mistral/auth.log).

Exemples:
  $(basename "$0") -n 10
  $(basename "$0") -n 3 /var/log/auth.log
EOF
}

# 1. Valeurs par défaut
N=5
FILE="/var/log/mistral/auth.log"
RES="top-attaquants-$(date +%Y-%m-%d-%H-%M).txt"

# 2. Gestion des options avec getopts
while getopts ":hn:" opt; do
  case "$opt" in
    h)
      afficher_aide
      exit 0
      ;;
    n)
      N="$OPTARG"
      ;;
    :)
      echo "Erreur : L'option -$OPTARG exige un argument." >&2
      echo "Utilisez '$(basename "$0") -h' pour afficher l'aide." >&2
      exit 1
      ;;
    \?)
      echo "Erreur : Option -$OPTARG invalide." >&2
      echo "Utilisez '$(basename "$0") -h' pour afficher l'aide." >&2
      exit 1
      ;;
  esac
done

# Décalage des arguments traités par getopts
shift $((OPTIND - 1))

# 3. Récupération du fichier passé en argument positionnel (si présent)
if [ -n "${1:-}" ]; then
  FILE="$1"
fi

# 4. Vérification de la lisibilité du fichier (Erreur code 2)
if [ ! -r "$FILE" ]; then
  echo "Erreur : Le fichier '$FILE' est introuvable ou illisible." >&2
  exit 2
fi

# 5. Extraction, comptage, tri, affichage écran ET sauvegarde fichier
grep 'Failed password' "$FILE" | \
  awk '{ for (i = 1; i <= NF; i++) if ($i == "from") print $(i+1) }' | \
  sort | \
  uniq -c | \
  sort -rn | \
  head -n "$N" | \
  awk '{print $1, $2}' | \
  tee "$RES"

echo "Résultats stockés dans $RES." >&2
