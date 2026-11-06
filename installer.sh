#!/usr/bin/env bash
set -euo pipefail

# Trouver le dossier dans lequel se trouve installer.sh
RACINE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Fichiers Ansible
PLAYBOOK="${PLAYBOOK:-$RACINE/deploiement/deploy.yml}"
INVENTAIRE="${INVENTAIRE:-$RACINE/deploiement/inventaire.ini}"

# Fonction pour afficher une erreur et arrêter le script
erreur() {
    echo "Erreur : $1" >&2
    exit 1
}


JETON=/etc/mistral/vigie.env


JETON="/etc/mistral/vigie.env"

if [[ ! -f "$JETON" ]]; then
    echo "Erreur : le fichier du jeton est introuvable." >&2
    exit 1
fi

if [[ ! -r "$JETON" ]]; then
    echo "Erreur : le jeton n'est pas lisible." >&2
    exit 1
fi


echo "=== Installation du kit Mistral ==="

# Vérifier qu'Ansible est installé
if ! command -v ansible-playbook >/dev/null 2>&1; then
    erreur "Ansible n'est pas installé."
fi

# Vérifier la présence du playbook
if [[ ! -f "$PLAYBOOK" ]]; then
    erreur "Playbook introuvable : $PLAYBOOK"
fi

# Vérifier la présence de l'inventaire
if [[ ! -f "$INVENTAIRE" ]]; then
    erreur "Inventaire introuvable : $INVENTAIRE"
fi

# Lancer l'installation Ansible
echo "Lancement du playbook : $PLAYBOOK"

if ansible-playbook -i "$INVENTAIRE" "$PLAYBOOK"; then
    echo "Installation du kit Mistral terminée avec succès."
else
    code=$?
    echo "Erreur : installation Ansible échouée (code $code)" >&2
    exit "$code"
fi
