#!/bin/bash

# 1. Vérification des privilèges root
if [ "$EUID" -ne 0 ]; then
    echo "Erreur : Ce script doit être exécuté en tant que root (ou avec sudo)."
    exit 1
fi

USERNAME="malik"

# 2. Création de l'utilisateur s'il n'existe pas encore
if id "$USERNAME" &>/dev/null; then
    echo "L'utilisateur '$USERNAME' existe déjà."
else
    useradd -m -s /bin/bash "$USERNAME"
    echo "Utilisateur '$USERNAME' créé avec son dossier /home/$USERNAME."
fi

# 3. Ajout du rôle sudo (gestion Debian/Ubuntu ou RHEL/Fedora)
if grep -q "^sudo:" /etc/group; then
    usermod -aG sudo "$USERNAME"
    echo "L'utilisateur '$USERNAME' a été ajouté au groupe 'sudo'."
elif grep -q "^wheel:" /etc/group; then
    usermod -aG wheel "$USERNAME"
    echo "L'utilisateur '$USERNAME' a été ajouté au groupe 'wheel'."
fi

# 4. Configuration du mot de passe
echo "--- Définition du mot de passe pour $USERNAME ---"
passwd "$USERNAME"
