#!/bin/bash
set -euo pipefail

### Script qui archive les fichiers de log plus vieux que "N" jours. Par défaut, archive tout ce qui est plus vieux que 2 jours.

# Fonction d'affichage de l'aide
afficher_aide() {
  cat << EOF
Usage: $(basename "$0") [-h] [-n] [-j JOURS] [DOSSIER]

Archive (compresse avec gzip) les fichiers .log d'un répertoire plus vieux que N jours.

Options:
  -h          Affiche cette aide et quitte.
  -n          Mode simulation : affiche les fichiers à compresser sans les modifier.
  -j JOURS    Définir le nombre de jours de rétention (défaut : 2).

Arguments:
  DOSSIER     Chemin du répertoire cible (défaut : répertoire courant '.').

Exemples:
  $(basename "$0") -n                        # Simulation dans le dossier courant
  $(basename "$0") -j 7 /var/log/mistral     # Compresse les logs de plus de 7 jours dans /var/log/mistral
EOF
}

# 1. Initialisation des variables
JOURS=2
SIMULATION=0
DOSSIER="."

# 2. Traitement des options
while getopts ":hnj:" opt; do
  case "$opt" in
    h)
      afficher_aide
      exit 0
      ;;
    n)
      SIMULATION=1
      echo "Option SIMULATION activée"
      ;;
    j)
      JOURS="$OPTARG"
      ;;
    :)
      echo "Erreur : L'option -$OPTARG exige un argument." >&2
      echo "Utilisez '$0 -h' pour voir l'aide." >&2
      exit 1
      ;;
    \?)
      echo "Erreur : Option -$OPTARG invalide." >&2
      echo "Utilisez '$0 -h' pour voir l'aide." >&2
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
