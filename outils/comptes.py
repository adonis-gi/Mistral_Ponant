#!/usr/bin/env python3
import argparse
import csv
from datetime import datetime
import re
import sys
import unicodedata


class CustomArgumentParser(argparse.ArgumentParser):
    """Affiche automatiquement l'aide complète en cas d'erreur d'arguments (exit code 2)."""

    def error(self, message):
        sys.stderr.write(f"Erreur d'utilisation : {message}\n\n")
        self.print_help()
        sys.exit(2)


def normaliser_chaine(texte):
    """Transforme une chaîne pour le login : minuscules, sans accents ni caractères spéciaux."""
    if not texte:
        return ""
    texte_nfd = unicodedata.normalize("NFD", texte)
    sans_accents = "".join(
        c for c in texte_nfd if unicodedata.category(c) != "Mn"
    )
    sans_accents = sans_accents.lower().strip()
    return re.sub(r"[^a-z0-9]", "", sans_accents)


def valider_et_formater_date(date_str):
    """Valide et convertit une date au format ISO (YYYY-MM-DD). Lève ValueError si invalide/absente."""
    date_str = date_str.strip()
    if not date_str:
        raise ValueError("date invalide")

    formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError("date invalide")


def generer_login(prenom, nom, compteur_logins):
    """Génère un login unique au format prenom.nom (ou prenom.nom2...)."""
    prenom_clean = normaliser_chaine(prenom)
    nom_clean = normaliser_chaine(nom)

    base_login = f"{prenom_clean}.{nom_clean}"

    if base_login not in compteur_logins:
        compteur_logins[base_login] = 1
        return base_login
    else:
        compteur_logins[base_login] += 1
        return f"{base_login}{compteur_logins[base_login]}"


def auto_detecter_delimiteur(fichier_path):
    """Détecte automatiquement si le CSV utilise ';' ou ','."""
    with open(fichier_path, "r", encoding="utf-8-sig") as f:
        premiere_ligne = f.readline()
        if ";" in premiere_ligne:
            return ";"
        return ","


def traiter_ligne(row, num_ligne, compteur_logins, lignes_acceptees, domaine):
    """
    Traite une ligne du CSV selon l'ordre strict des contrôles :
    1. Nom vide -> nom manquant
    2. Prénom vide -> prenom manquant
    3. Date absente ou impossible -> date invalide
    4. Mêmes (nom, prénom, e-mail) qu'une ligne déjà acceptée -> doublon
    """
    row_clean = {k.strip().lower(): v.strip() for k, v in row.items() if k}

    nom_rh = row_clean.get("nom", "")
    prenom_rh = row_clean.get("prenom", "")
    site = row_clean.get("site", "")
    date_raw = row_clean.get("date_arrivee", "")
    email_input = row_clean.get("email_perso", row_clean.get("email", ""))

    # 1. Nom vide
    if not nom_rh:
        return None, {"ligne": num_ligne, "raison": "nom manquant"}

    # 2. Prénom vide
    if not prenom_rh:
        return None, {"ligne": num_ligne, "raison": "prenom manquant"}

    # 3. Date absente ou impossible
    try:
        date_iso = valider_et_formater_date(date_raw)
    except ValueError:
        return None, {"ligne": num_ligne, "raison": "date invalide"}

    # 4. Doublon (même nom, même prénom, même email sans tenir compte de la casse)
    cle_doublon = (nom_rh.lower(), prenom_rh.lower(), email_input.lower())
    if cle_doublon in lignes_acceptees:
        return None, {"ligne": num_ligne, "raison": "doublon"}

    # Ligne acceptée : enregistrement de la clé de contrôle des doublons
    lignes_acceptees.add(cle_doublon)

    login = generer_login(prenom_rh, nom_rh, compteur_logins)
    email = f"{login}@{domaine}"

    compte = {
        "login": login,
        "email": email,
        "nom": nom_rh,
        "prenom": prenom_rh,
        "site": site,
        "date_arrivee": date_iso,
    }
    return compte, None


def main():
    parser = CustomArgumentParser(
        description="Nettoie et formate un fichier CSV d'utilisateurs."
    )
    parser.add_argument(
        "--csv", required=True, help="Chemin du fichier CSV source (obligatoire)"
    )
    parser.add_argument(
        "--sortie",
        default="comptes_propres.csv",
        help="CSV de sortie (défaut: comptes_propres.csv)",
    )
    parser.add_argument(
        "--rejets",
        default="rejets.csv",
        help="CSV des rejets (défaut: rejets.csv)",
    )
    parser.add_argument(
        "--domaine",
        default="mistral.test",
        help="Domaine email (défaut: mistral.test)",
    )

    args = parser.parse_args()

    compteur_logins = {}
    lignes_acceptees = set()
    comptes_valides = []
    rejets = []
    fieldnames_propres = [
        "login",
        "email",
        "nom",
        "prenom",
        "site",
        "date_arrivee",
    ]

    action_requise = False

    try:
        separateur = auto_detecter_delimiteur(args.csv)
        if separateur != ",":
            action_requise = True

        with open(args.csv, mode="r", encoding="utf-8-sig") as f_in:
            reader = csv.DictReader(f_in, delimiter=separateur)

            if reader.fieldnames != fieldnames_propres:
                action_requise = True

            # enumerate start=2 : la ligne 1 est l'en-tête, la première personne est la ligne 2
            for num_ligne, row in enumerate(reader, start=2):
                compte, rejet = traiter_ligne(
                    row,
                    num_ligne,
                    compteur_logins,
                    lignes_acceptees,
                    args.domaine,
                )
                if compte:
                    comptes_valides.append(compte)
                    if not action_requise:
                        for k in fieldnames_propres:
                            if row.get(k) != compte.get(k):
                                action_requise = True
                                break
                elif rejet:
                    rejets.append(rejet)
                    action_requise = True

    except FileNotFoundError:
        print(
            f"Erreur : Le fichier '{args.csv}' est introuvable.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Tri par ordre alphabétique du login
    comptes_avant_tri = list(comptes_valides)
    comptes_valides.sort(key=lambda x: x["login"])
    if comptes_avant_tri != comptes_valides:
        action_requise = True

    # Écriture du fichier des comptes propres (séparateur : virgule)
    with open(args.sortie, mode="w", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(
            f_out, fieldnames=fieldnames_propres, delimiter=","
        )
        writer.writeheader()
        writer.writerows(comptes_valides)

    # Écriture du fichier des rejets (séparateur : point-virgule, colonnes : ligne;raison)
    fieldnames_rejets = ["ligne", "raison"]
    with open(args.rejets, mode="w", encoding="utf-8", newline="") as f_rej:
        writer = csv.DictWriter(
            f_rej, fieldnames=fieldnames_rejets, delimiter=";"
        )
        writer.writeheader()
        writer.writerows(rejets)

    # Bilan de l'exécution
    if not action_requise:
        print(
            f"Le fichier '{args.csv}' est déjà propre. Aucune action n'a été requise."
        )
    elif len(rejets) > 0:
        print(
            f"Traitement terminé avec rejets : {len(comptes_valides)} comptes valides dans '{args.sortie}', {len(rejets)} rejets dans '{args.rejets}'."
        )
    else:
        print(
            f"Nettoyage effectué : {len(comptes_valides)} comptes valides exportés dans '{args.sortie}'."
        )


if __name__ == "__main__":
    main()
