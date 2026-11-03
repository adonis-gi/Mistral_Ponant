#!/usr/bin/env python3

from collections import Counter
from pathlib import Path
import re
import argparse

parser = argparse.ArgumentParser(
    description="Croiser les échecs SSH et les erreurs HTTP 404"
)

parser.add_argument(
    "--auth",
    type=Path,
    default=Path("/var/log/mistral/auth.log")
)

parser.add_argument(
    "--access",
    type=Path,
    default=Path("/srv/mistral/web/access.log")
)

args = parser.parse_args()

AUTH_LOG = args.auth
ACCESS_LOG = args.access

echecs_ssh = Counter()

motif_ssh = re.compile(
    r"Failed password .* from (\d{1,3}(?:\.\d{1,3}){3}) port"
)

with AUTH_LOG.open(encoding="utf-8", errors="replace") as fichier:
    for ligne in fichier:
        resultat = motif_ssh.search(ligne)

        if resultat:
            ip = resultat.group(1)
            echecs_ssh[ip] += 1

print(f"IP distinctes avec échecs SSH : {len(echecs_ssh)}")
print(f"Nombre total d'échecs SSH : {sum(echecs_ssh.values())}")

# Comptage des erreurs HTTP 404
erreurs_404 = Counter()

motif_http = re.compile(r'"[^"]*" (\d{3}) ')

with ACCESS_LOG.open(encoding="utf-8", errors="replace") as fichier:
    for ligne in fichier:
        resultat = motif_http.search(ligne)

        if resultat and resultat.group(1) == "404":
            ip = ligne.split()[0]
            erreurs_404[ip] += 1

print(f"IP distinctes avec erreurs 404 : {len(erreurs_404)}")
print(f"Nombre total d'erreurs 404 : {sum(erreurs_404.values())}")

# Rechercher les IP présentes dans les deux journaux
ip_communes = echecs_ssh.keys() & erreurs_404.keys()

# Préparer les résultats : IP, échecs SSH, erreurs 404 et total
resultats = []

for ip in ip_communes:
    ssh = echecs_ssh[ip]
    http = erreurs_404[ip]
    total = ssh + http

    resultats.append((ip, ssh, http, total))

# Trier par nombre total d'événements décroissant
resultats.sort(key=lambda ligne: (-ligne[3], ligne[0]))

# Afficher les résultats
print("\nIP présentes dans les deux journaux :")
print(f"{'IP':<18} {'SSH':>8} {'HTTP 404':>10} {'TOTAL':>8}")
print("-" * 48)

for ip, ssh, http, total in resultats:
    print(f"{ip:<18} {ssh:>8} {http:>10} {total:>8}")

if not resultats:
    print("Aucune adresse IP commune trouvée entre les échecs SSH et les erreurs HTTP 404.")

print(f"\nNombre d'IP communes : {len(resultats)}")


