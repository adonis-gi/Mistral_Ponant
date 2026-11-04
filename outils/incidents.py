#!/usr/bin/env python3
"""
Outil pour récupérer et compter tous les incidents de l'API Vigie par site et gravité.
"""


import argparse
import csv
import os
import sys
import time
from collections import Counter
import requests


API_URL = os.environ.get("VIGIE_URL", "http://vigie.mistral.test:8080/api/v1")
ESSAIS_MAX = 6


def get_token():
    token = os.environ.get("VIGIE_TOKEN")
    if not token:
        print("Erreur: VIGIE_TOKEN non défini dans l'environnement.", file=sys.stderr)
        sys.exit(3)
    return token


def recuperer_page(session, url, page):
    """Demande une page d'incidents ; sur 429 ou 503, attend Retry-After (1 s par défaut) et réessaie, 6 essais au plus."""
    params = {"page": page, "par_page": 20}
    for essai in range(1, ESSAIS_MAX + 1):
        r = session.get(url, params=params, timeout=5)
        if r.status_code in (429, 503):
            attente = float(r.headers.get("Retry-After", 1))
            print(f"Avertissement: page {page}, essai {essai} : {r.status_code}, attente {attente} s", file=sys.stderr)
            time.sleep(attente)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"page {page} toujours indisponible après {ESSAIS_MAX} essais")


def compter(incidents, compteurs):
    """Ajoute les incidents d'une page au compteur (site, gravité)."""
    for inc in incidents:
        site = inc.get("site", "inconnu")
        gravite = inc.get("gravite", "basse")
        compteurs[(site, gravite)] += 1


def main():
    parser = argparse.ArgumentParser(description="Récupère les incidents Vigie par site et gravité.")
    parser.add_argument("--sortie", required=True, help="Chemin du fichier CSV de sortie")
    args = parser.parse_args()


    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    session = requests.Session()
    session.headers.update(headers)


    url = f"{API_URL}/incidents"
    compteurs = Counter()
    
    # Page 1 : elle donne aussi le nombre total de pages
    try:
        data = recuperer_page(session, url, 1)
        total_pages = data.get("pages", 1)
        compter(data.get("incidents", []), compteurs)

        # Pages suivantes : une page manquée fausserait les totaux, donc on s'arrête en erreur
        for page in range(2, total_pages + 1):
            data = recuperer_page(session, url, page)
            compter(data.get("incidents", []), compteurs)
    except (requests.RequestException, RuntimeError) as e:
        print(f"Erreur lors de la récupération des incidents : {e}", file=sys.stderr)
        return 2


    # Récupération de la liste des sites uniques triés par ordre alphabétique
    sites = sorted(list(set(s for s, g in compteurs.keys())))


    # Écriture du fichier CSV de sortie
    try:
        with open(args.sortie, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["site", "haute", "moyenne", "basse", "total"])
            
            for site in sites:
                haute = compteurs[(site, "haute")]
                moyenne = compteurs[(site, "moyenne")]
                basse = compteurs[(site, "basse")]
                total = haute + moyenne + basse
                writer.writerow([site, haute, moyenne, basse, total])
        print(f"Rapport d'incidents enregistré dans {args.sortie}")
    except OSError as e:
        print(f"Erreur lors de l'écriture du CSV: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
