#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--csv", required=True)
parser.add_argument("--sortie", required=True)
args = parser.parse_args()

# Lecture du CSV transmis par comptes.sh
with open(args.csv, encoding="utf-8", newline="") as fichier:
    lignes = list(csv.DictReader(fichier, delimiter=";"))

print(f"MOCK : {len(lignes)} saisonniers reçus")

# Création du dossier de sortie
sortie = Path(args.sortie)
sortie.mkdir(parents=True, exist_ok=True)

# Simulation des deux premiers comptes acceptés
with open(sortie / "comptes.csv", "w", encoding="utf-8", newline="") as fichier:
    writer = csv.writer(fichier, delimiter=";")
    writer.writerow(["login", "email", "nom", "prenom", "site", "date_arrivee"])

    for numero, ligne in enumerate(lignes[:2], start=1):
        writer.writerow([
            f"test{numero}",
            ligne["email"],
            ligne["nom"],
            ligne["prenom"],
            ligne["site"],
            ligne["date_arrivee"]
        ])

# Simulation du rejet des autres lignes
with open(sortie / "rejets.csv", "w", encoding="utf-8", newline="") as fichier:
    writer = csv.writer(fichier, delimiter=";")
    writer.writerow(["ligne", "raison"])

    for numero in range(3, len(lignes) + 1):
        writer.writerow([numero + 1, "Rejet simule"])

print("MOCK : fichiers comptes.csv et rejets.csv générés")
