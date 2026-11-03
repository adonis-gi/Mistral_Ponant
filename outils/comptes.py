#!/usr/bin/env python3

"""Crée les comptes des saisonniers à partir de l'export RH (comptes, rejets et mdp en CSV ou JSON)."""
#-#-#-#-#-#-#-#-#-#-#-#-#-#-# NOTES : ce script répond aux quêtes annexes : M1, M2, M4, M5, M9 #-#-#-#-#-#-#-#-#-#-#-#-#-#-#

import argparse
import csv
import io
import json
import logging
import os
import re
import secrets
import string
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


def generer_mot_de_passe(longueur=14):
    """Génère un mot de passe sécurisé de 14 caractères avec le module secrets."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
    return "".join(secrets.choice(alphabet) for _ in range(longueur))


def auto_detecter_delimiteur(f_in):
    """Détecte automatiquement si le flux CSV utilise ';' ou ','."""
    pos = f_in.tell()
    premiere_ligne = f_in.readline()
    f_in.seek(pos)
    return ";" if ";" in premiere_ligne else ","


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

    # 3. Date absente ou impossible
    try:
        date_iso = normaliser_date(date_raw)
    except ValueError:
        return None, [num_ligne, "date invalide"]

    # 4. Doublon
    cle_personne = (nom_rh.lower(), prenom_rh.lower(), email_perso)
    if cle_personne in personnes_acceptees:
        return None, [num_ligne, "doublon"]

    personnes_acceptees.add(cle_personne)
    login = generer_login(prenom_rh, nom_rh, logins_pris)
    compte = [login, f"{login}@{domaine}", nom_rh, prenom_rh, site, date_iso]
    return compte, None


def main():
    parser = CustomArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="fichier CSV de la RH ou '-' pour l'entrée standard (obligatoire)")
    parser.add_argument("--sortie", required=True, help="dossier où écrire les fichiers générés (obligatoire)")
    parser.add_argument("--domaine", default="mistral.test", help="domaine des e-mails (défaut : mistral.test)")
    parser.add_argument("--format", choices=["csv", "json"], default="csv", help="format de sortie : csv ou json (défaut : csv)")
    parser.add_argument("-v", "--verbose", action="store_true", help="affiche le détail du traitement (niveau INFO)")
    parser.add_argument("--mdp", action="store_true", help="génère le fichier mdp avec des mots de passe provisoires (droits 600)")
    args = parser.parse_args()

    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    logins_pris = set()
    personnes_acceptees = set()
    comptes_valides = []
    rejets = []

    try:
        logging.info("Lecture de la source CSV : %s", "entrée standard" if args.csv == "-" else args.csv)
        if args.csv == "-":
            contenu = sys.stdin.buffer.read().decode("utf-8-sig")
        else:
            with open(args.csv, mode="r", encoding="utf-8-sig", newline="") as f:
                contenu = f.read()

        f_in = io.StringIO(contenu)
        delimiteur = auto_detecter_delimiteur(f_in)
        reader = csv.DictReader(f_in, delimiter=delimiteur)

        for num_ligne, row in enumerate(reader, start=2):
            compte, rejet = traiter_ligne(row, num_ligne, logins_pris, personnes_acceptees, args.domaine)
            if compte:
                comptes_valides.append(compte)
                logging.info("Ligne %d : compte créé pour %s (%s)", num_ligne, compte[0], compte[1])
            else:
                rejets.append(rejet)
                logging.warning("Ligne %d rejetée : %s", num_ligne, rejet[1])

    except FileNotFoundError:
        print(f"Erreur : le fichier '{args.csv}' est introuvable.", file=sys.stderr)
        return 2

    comptes_valides.sort(key=lambda compte: compte[0])

    os.makedirs(args.sortie, exist_ok=True)
    extension = args.format
    fichier_comptes = os.path.join(args.sortie, f"comptes.{extension}")
    fichier_rejets = os.path.join(args.sortie, f"rejets.{extension}")

    logging.info("Écriture des fichiers au format %s dans le dossier '%s'...", extension.upper(), args.sortie)

    champs_comptes = ["login", "email", "nom", "prenom", "site", "date_arrivee"]

    if args.format == "json":
        # Format JSON : liste d'objets pour comptes
        data_comptes = [dict(zip(champs_comptes, c)) for c in comptes_valides]
        with open(fichier_comptes, mode="w", encoding="utf-8") as f_out:
            json.dump(data_comptes, f_out, ensure_ascii=False, indent=2)

        # Format JSON : liste d'objets pour rejets
        data_rejets = [{"ligne": r[0], "raison": r[1]} for r in rejets]
        with open(fichier_rejets, mode="w", encoding="utf-8") as f_rej:
            json.dump(data_rejets, f_rej, ensure_ascii=False, indent=2)
    else:
        # Format CSV
        with open(fichier_comptes, mode="w", encoding="utf-8", newline="") as f_out:
            writer = csv.writer(f_out, delimiter=";")
            writer.writerow(champs_comptes)
            writer.writerows(comptes_valides)

        with open(fichier_rejets, mode="w", encoding="utf-8", newline="") as f_rej:
            writer = csv.writer(f_rej, delimiter=";")
            writer.writerow(["ligne", "raison"])
            writer.writerows(rejets)

    if args.mdp:
        fichier_mdp = os.path.join(args.sortie, f"mdp.{extension}")
        data_mdp_raw = [[compte[0], generer_mot_de_passe(14)] for compte in comptes_valides]

        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(fichier_mdp, flags, 0o600)
        with open(fd, mode="w", encoding="utf-8", newline="" if args.format == "csv" else None) as f_mdp:
            if args.format == "json":
                data_mdp_json = [{"login": m[0], "mdp": m[1]} for m in data_mdp_raw]
                json.dump(data_mdp_json, f_mdp, ensure_ascii=False, indent=2)
            else:
                writer = csv.writer(f_mdp, delimiter=";")
                writer.writerow(["login", "mdp"])
                writer.writerows(data_mdp_raw)

        os.chmod(fichier_mdp, 0o600)
        logging.info("Mots de passe provisoires générés dans '%s' (droits 600)", fichier_mdp)

    print(f"{len(comptes_valides)} comptes créés dans {fichier_comptes}, {len(rejets)} lignes rejetées dans {fichier_rejets}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

