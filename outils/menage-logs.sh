#!/bin/bash
set -euo pipefail

### Script qui archive les fichiers de log plus vieux que "N" jours. Par défaut, archive tout ce qui est plus vieux que 2 jours.

# 1. Initialisation des variables
JOURS=2
SIMULATION=0
DOSSIER="."

# 2. Traitement des options
while getopts ":nj:" opt; do
  case "$opt" in
    n)
      SIMULATION=1
      echo "Option SIMULATION activée"
      ;;
    j)
      JOURS="$OPTARG"
      ;;
    :)
      echo "Erreur : L'option -$OPTARG exige un argument." >&2
      exit 1
      ;;
    \?)
      echo "Erreur : Option -$OPTARG invalide." >&2
      exit 1
      ;;
  esac
done

shift $((OPTIND - 1))

# 3. Récupération du dossier (si fourni)
if [ -n "${1:-}" ]; then
  DOSSIER="$1"
fi

if [ ! -d "$DOSSIER" ]; then
  echo "Erreur : Le dossier '$DOSSIER' n'existe pas ou n'est pas un répertoire." >&2
  exit 2
fi

# 4. Compteur et recherche des fichiers
TROUVE=0

while IFS= read -r -d '' f; do
  TROUVE=1
  if [ "$SIMULATION" -eq 1 ]; then
    echo "[SIMULATION] Fichier à compresser : $f"
  else
    gzip -- "$f"
    echo "Compressé : $f.gz"
  fi
done < <(find "$DOSSIER" -maxdepth 1 -type f -name '*.log' -mtime +"$((JOURS - 1))" -print0)

if [ "$TROUVE" -eq 0 ]; then
  echo "Aucun fichier .log correspondant trouvé."
fi
