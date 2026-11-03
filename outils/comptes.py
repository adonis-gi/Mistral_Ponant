#!/usr/bin/env python3
"""Crée les comptes des saisonniers à partir de l'export RH (comptes.csv et rejets.csv)."""
import argparse
import csv
import os
import re
import sys
import unicodedata
from datetime import datetime


class CustomArgumentParser(argparse.ArgumentParser):
    """Affiche automatiquement l'aide complète en cas d'erreur d'arguments (exit code 2)."""

    def error(self, message):
        sys.stderr.write(f"Erreur d'utilisation : {message}\n\n")
        self.print_help(sys.stderr)
        sys.exit(2)


def normaliser_chaine(texte):
    """Transforme une chaîne pour le login : minuscules, sans accents, seulement a-z et le tiret."""
    if not texte:
        return ""
    texte_nfd = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in texte_nfd if unicodedata.category(c) != "Mn")
    sans_accents = sans_accents.lower().strip()
    return re.sub(r"[^a-z-]", "", sans_accents)


def normaliser_date(date_str):
    """Convertit une date JJ/MM/AAAA au format ISO (AAAA-MM-JJ). Lève ValueError si absente ou impossible."""
    return datetime.strptime(date_str.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")


def generer_login(prenom, nom, logins_pris):
    """Génère un login unique : prenom.nom, puis prenom.nom2, prenom.nom3..."""
    base_login = f"{normaliser_chaine(prenom)}.{normaliser_chaine(nom)}"
    login, i = base_login, 2
    while login in logins_pris:
        login, i = f"{base_login}{i}", i + 1
    logins_pris.add(login)
    return login


def traiter_ligne(row, num_ligne, logins_pris, personnes_acceptees, domaine):
    """
    Traite une ligne du CSV selon l'ordre strict des contrôles :
    1. Nom vide -> nom manquant
    2. Prénom vide -> prenom manquant
    3. Date absente ou impossible -> date invalide
    4. Même nom, prénom et e-mail qu'une personne déjà acceptée (sans tenir compte des majuscules) -> doublon
    """
    row_clean = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}

    nom_rh = row_clean.get("nom", "")
    prenom_rh = row_clean.get("prenom", "")
    email_perso = row_clean.get("email_perso", "").lower()
    site = row_clean.get("site", "")
    date_raw = row_clean.get("date_arrivee", "")

    # 1. Nom vide
    if not nom_rh:
        return None, [num_ligne, "nom manquant"]

    # 2. Prénom vide
    if not prenom_rh:
        return None, [num_ligne, "prenom manquant"]

    # 3. Date absente ou impossible (strptime lève ValueError, par exemple pour le 31/02)
    try:
        date_iso = normaliser_date(date_raw)
    except ValueError:
        return None, [num_ligne, "date invalide"]

    # 4. Doublon : même nom, même prénom et même e-mail, sans tenir compte des majuscules
    cle_personne = (nom_rh.lower(), prenom_rh.lower(), email_perso)
    if cle_personne in personnes_acceptees:
        return None, [num_ligne, "doublon"]

    # Ligne acceptée
    personnes_acceptees.add(cle_personne)
    login = generer_login(prenom_rh, nom_rh, logins_pris)
    compte = [login, f"{login}@{domaine}", nom_rh, prenom_rh, site, date_iso]
    return compte, None


def main():
    parser = CustomArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="fichier CSV de la RH (obligatoire)")
    parser.add_argument("--sortie", required=True, help="dossier où écrire comptes.csv et rejets.csv (obligatoire)")
    parser.add_argument("--domaine", default="mistral.test", help="domaine des e-mails (défaut : mistral.test)")
    args = parser.parse_args()

    logins_pris = set()
    personnes_acceptees = set()
    comptes_valides = []
    rejets = []

    try:
        # utf-8-sig retire le BOM ajouté par le tableur
        with open(args.csv, mode="r", encoding="utf-8-sig", newline="") as f_in:
            reader = csv.DictReader(f_in, delimiter=";")
            for num_ligne, row in enumerate(reader, start=2):
                compte, rejet = traiter_ligne(row, num_ligne, logins_pris, personnes_acceptees, args.domaine)
                if compte:
                    comptes_valides.append(compte)
                else:
                    rejets.append(rejet)
    except FileNotFoundError:
        print(f"Erreur : le fichier '{args.csv}' est introuvable.", file=sys.stderr)
        return 2

    # Tri par ordre alphabétique du login (première colonne)
    comptes_valides.sort(key=lambda compte: compte[0])

    os.makedirs(args.sortie, exist_ok=True)
    fichier_comptes = os.path.join(args.sortie, "comptes.csv")
    fichier_rejets = os.path.join(args.sortie, "rejets.csv")

    with open(fichier_comptes, mode="w", encoding="utf-8", newline="") as f_out:
        writer = csv.writer(f_out, delimiter=";")
        writer.writerow(["login", "email", "nom", "prenom", "site", "date_arrivee"])
        writer.writerows(comptes_valides)

    with open(fichier_rejets, mode="w", encoding="utf-8", newline="") as f_rej:
        writer = csv.writer(f_rej, delimiter=";")
        writer.writerow(["ligne", "raison"])
        writer.writerows(rejets)

    print(f"{len(comptes_valides)} comptes créés dans {fichier_comptes}, {len(rejets)} lignes rejetées dans {fichier_rejets}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

