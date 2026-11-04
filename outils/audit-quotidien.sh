#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage : $0 [AAAA-MM-JJ]" >&2
    exit 2
}

# Vérifier le nombre d'arguments
if [[ $# -gt 1 ]]; then
    usage
fi

# Date du jour par défaut
DATE_AUDIT="${1:-$(date +%F)}"

# Vérifier le format AAAA-MM-JJ
if [[ ! "$DATE_AUDIT" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "Erreur : format de date invalide" >&2
    exit 2
fi

# Vérifier que la date existe réellement
if ! DATE_VERIFIEE=$(date -d "$DATE_AUDIT" +%F 2>/dev/null); then
    echo "Erreur : date inexistante" >&2
    exit 2
fi

if [[ "$DATE_VERIFIEE" != "$DATE_AUDIT" ]]; then
    echo "Erreur : date invalide" >&2
    exit 2
fi

echo "Date de l'audit : $DATE_AUDIT"

# Script PowerShell à exécuter
AUDIT_PS1="${AUDIT_PS1:-/guilde/outils/Audit-Parc.ps1}"

# Inventaire des postes Windows
FICHIER_POSTES="/srv/mistral/parc/postes.json"

# Créer un dossier temporaire pour les résultats
SORTIE_AUDIT=$(mktemp -d)

# Supprimer les fichiers temporaires en fin d'exécution
nettoyer() {
    rm -rf -- "$SORTIE_AUDIT"
}
trap nettoyer EXIT

# Vérifier la présence du script PowerShell
if [[ ! -f "$AUDIT_PS1" ]]; then
    echo "Erreur : script PowerShell introuvable : $AUDIT_PS1" >&2
    exit 1
fi

# Lancer l'audit PowerShell
if pwsh -NoProfile -File "$AUDIT_PS1" \
    -Fichier "$FICHIER_POSTES" \
    -Sortie "$SORTIE_AUDIT" \
    -Date "$DATE_AUDIT"; then

    echo "Audit PowerShell exécuté avec succès"
else
    code=$?
    echo "Erreur : audit PowerShell échoué (code $code)" >&2
    exit "$code"
fi

# Vérifier que le rapport CSV a été produit
if [[ ! -f "$SORTIE_AUDIT/non-conformes.csv" ]]; then
    echo "Erreur : rapport non-conformes.csv absent" >&2
    exit 1
fi

echo "Rapport CSV produit avec succès"

# Compter les postes non conformes dans le CSV
NON_CONFORMES=$(awk -F';' 'NR > 1 && $1 != "" {compte++} END {print compte+0}' \
    "$SORTIE_AUDIT/non-conformes.csv")

echo "Postes non conformes le $DATE_AUDIT : $NON_CONFORMES"

# Chemin de l'historique
HISTORIQUE="${HISTORIQUE:-/var/lib/mistral/audit/historique.csv}"

# Créer le dossier si nécessaire
DOSSIER_HISTORIQUE=$(dirname -- "$HISTORIQUE")
mkdir -p "$DOSSIER_HISTORIQUE"

# Initialiser le fichier CSV si absent
if [[ ! -f "$HISTORIQUE" ]]; then
    printf 'date;non_conformes\n' > "$HISTORIQUE"
fi

# Préparer un fichier temporaire
TEMP_HIST=$(mktemp "$DOSSIER_HISTORIQUE/.historique.XXXXXX")

{
    # Écrire l'en-tête
    printf 'date;non_conformes\n'

    {
        # Conserver les autres dates
        awk -F';' -v jour="$DATE_AUDIT" \
            'NR > 1 && $1 != jour && $1 != "" {print $1 ";" $2}' \
            "$HISTORIQUE"

        # Ajouter le résultat du jour
        printf '%s;%s\n' "$DATE_AUDIT" "$NON_CONFORMES"

    } | LC_ALL=C sort -t';' -k1,1

} > "$TEMP_HIST"

# Remplacer l'ancien historique
mv -- "$TEMP_HIST" "$HISTORIQUE"

echo "Historique mis à jour : $HISTORIQUE"

# Rechercher la date précédente dans l'historique
PRECEDENT=$(awk -F';' -v jour="$DATE_AUDIT" '
    NR > 1 && $1 < jour && $1 > date_precedente {
        date_precedente=$1
        nombre=$2
    }
    END {
        if (date_precedente != "") {
            print date_precedente ";" nombre
        }
    }
' "$HISTORIQUE")

if [[ -n "$PRECEDENT" ]]; then

    # Séparer la date et le nombre précédent
    IFS=';' read -r DATE_PRECEDENTE NOMBRE_PRECEDENT <<< "$PRECEDENT"

    # Calculer la différence
    ECART=$((NON_CONFORMES - NOMBRE_PRECEDENT))

    printf 'Écart par rapport au %s : %+d poste(s) non conforme(s)\n' \
        "$DATE_PRECEDENTE" "$ECART"

else
    echo "Écart : aucun jour précédent enregistré."
fi
