"""Enrichit une liste d'adresses avec leur réputation Vigie (rapport.json, rapport.csv, enrichir.log)."""
import csv
import json
import logging
import os
import random
import sys
import time
from collections import deque

import requests

from mistral_commun import ParseurArguments

log = logging.getLogger("enrichir")


# ---------------------------------------------------------------------------
# Client de l'API Vigie : jeton, limiteur, reprises et erreurs claires
# ---------------------------------------------------------------------------

# Adresse de l'API (VIGIE_URL permet de la changer pour un test, sans toucher au code)
BASE_URL = os.environ.get("VIGIE_URL", "http://vigie.mistral.test:8080/api/v1")

log_vigie = logging.getLogger("vigie")


class JetonAbsent(Exception):
    """VIGIE_TOKEN est vide ou absent."""


class JetonRefuse(Exception):
    """Vigie a répondu 401 : le jeton est faux ou révoqué. Réessayer ne sert à rien."""


class VigieIndisponible(Exception):
    """Vigie ne répond plus, ou répond 429/503, après tous les essais."""


def lire_jeton():
    """Renvoie le jeton lu dans VIGIE_TOKEN, ou lève JetonAbsent."""
    jeton = os.environ.get("VIGIE_TOKEN", "").strip()
    if not jeton:
        raise JetonAbsent("VIGIE_TOKEN est vide : charge /etc/mistral/vigie.env (set -a; . /etc/mistral/vigie.env; set +a)")
    return jeton


class Vigie:
    """Un client de l'API Vigie : une session avec le jeton, au plus 5 requêtes par seconde, 6 essais par appel."""

    def __init__(self, jeton, base_url=BASE_URL, par_seconde=5, essais=6, session=None):
        self.base_url = base_url
        self.par_seconde = par_seconde
        self.essais = essais
        self.session = session or requests.Session()
        self.session.headers["Authorization"] = f"Bearer {jeton}"
        self.instants = deque()   # E8 : heures des derniers appels, pour le limiteur
        self.nb_appels = 0        # nombre de requêtes réellement envoyées

    def _limiter(self):
        """E8 : attend juste ce qu'il faut pour ne jamais dépasser par_seconde requêtes sur une seconde glissante."""
        while True:
            maintenant = time.monotonic()
            while self.instants and maintenant - self.instants[0] >= 1.0:
                self.instants.popleft()
            if len(self.instants) < self.par_seconde:
                self.instants.append(maintenant)
                return
            time.sleep(1.0 - (maintenant - self.instants[0]) + 0.02)

    @staticmethod
    def attente_exponentielle(essai):
        """E2 : 1, 2, 4, 8... secondes, plus un petit hasard pour que les clients ne reviennent pas tous ensemble."""
        return 2 ** (essai - 1) + random.uniform(0, 0.5)

    def appel(self, methode, chemin, **kwargs):
        """Appelle l'API et renvoie le JSON. Réessaie sur 429, 503 et coupure réseau ; s'arrête net sur 401."""
        url = f"{self.base_url}{chemin}"
        for essai in range(1, self.essais + 1):
            self._limiter()
            self.nb_appels += 1
            try:
                r = self.session.request(methode, url, timeout=5, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as e:
                if essai == self.essais:
                    break
                attente = self.attente_exponentielle(essai)
                log_vigie.warning("essai %d/%d sur %s : Vigie injoignable (%s), attente %.1f s",
                            essai, self.essais, chemin, type(e).__name__, attente)
                time.sleep(attente)
                continue

            if r.status_code == 401:
                raise JetonRefuse("jeton refusé par Vigie (401) : vérifie /etc/mistral/vigie.env")
            if r.status_code in (429, 503):
                if essai == self.essais:
                    break
                if "Retry-After" in r.headers:
                    attente = float(r.headers["Retry-After"])
                else:
                    attente = self.attente_exponentielle(essai)
                log_vigie.warning("essai %d/%d sur %s : %d, attente %.1f s", essai, self.essais, chemin, r.status_code, attente)
                time.sleep(attente)
                continue

            r.raise_for_status()  # 400, 404... : erreur définitive, inutile de réessayer
            return r.json()
        raise VigieIndisponible(f"{chemin} : Vigie indisponible après {self.essais} essais")


# ---------------------------------------------------------------------------
# Enrichissement
# ---------------------------------------------------------------------------

CACHE = os.path.expanduser("~/.cache/mistral/reputation.json")
DUREE_CACHE = 3600          # E1 : une réponse de moins d'une heure est réutilisée
CODE_INCOMPLET = 4          # E10 : rapport partiel, des adresses restent à reprendre
FICHIER_MANQUEES = "manquees.txt"


def lire_adresses(chemin):
    """Lit le fichier d'entrée : le dernier mot de chaque ligne, sans doublon, dans l'ordre du fichier."""
    adresses = []
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            mots = ligne.split()
            if mots and mots[-1] not in adresses:
                adresses.append(mots[-1])
    return adresses


def configurer_journal(dossier):
    """Envoie les messages INFO et WARNING dans DOSSIER/enrichir.log."""
    logging.basicConfig(
        filename=os.path.join(dossier, "enrichir.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s : %(message)s",
    )


def lire_json(chemin, defaut):
    """Lit un fichier JSON, ou renvoie la valeur par défaut s'il est absent ou abîmé."""
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def ecrire_json(chemin, donnees):
    """Écrit un fichier JSON en passant par un fichier temporaire : jamais de fichier à moitié écrit."""
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2)
    os.replace(tmp, chemin)


def connues_de_la_reprise(dossier):
    """E10 : si le passage précédent était incomplet, reprend les adresses déjà obtenues dans son rapport."""
    if not os.path.exists(os.path.join(dossier, FICHIER_MANQUEES)):
        return {}
    precedent = lire_json(os.path.join(dossier, "rapport.json"), [])
    return {r["ip"]: r for r in precedent}


def ecrire_rapports(resultats, dossier):
    """Écrit rapport.json et rapport.csv dans DOSSIER."""
    ecrire_json(os.path.join(dossier, "rapport.json"), resultats)
    with open(os.path.join(dossier, "rapport.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["ip", "score", "categories"])
        for r in resultats:
            w.writerow([r["ip"], r["score"], ",".join(r["categories"])])


def ecrire_markdown(resultats, dossier, seuil):
    """E3 : tableau Markdown des adresses dangereuses, à coller dans le README."""
    lignes = [f"| Adresse | Score | Catégories |", "|---|---:|---|"]
    for r in resultats:
        if r["score"] >= seuil:
            lignes.append(f"| `{r['ip']}` | {r['score']} | {', '.join(r['categories']) or '-'} |")
    texte = "\n".join(lignes) + "\n"
    with open(os.path.join(dossier, "rapport.md"), "w", encoding="utf-8") as f:
        f.write(texte)
    return texte


def main():
    parser = ParseurArguments(description=__doc__)
    parser.add_argument("--entree", required=True, help="fichier d'adresses, ou sortie de top-attaquants.sh")
    parser.add_argument("--sortie", required=True, help="dossier où écrire rapport.json, rapport.csv et enrichir.log")
    parser.add_argument("--cache", action="store_true", help=f"réutilise les réponses de moins d'une heure ({CACHE})")
    parser.add_argument("--markdown", action="store_true", help="écrit aussi rapport.md, tableau des adresses dangereuses")
    parser.add_argument("--seuil", type=int, default=80, help="score à partir duquel une adresse est dangereuse (80)")
    args = parser.parse_args()

    try:
        jeton = lire_jeton()
    except JetonAbsent as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 3

    try:
        adresses = lire_adresses(args.entree)
    except OSError as e:
        print(f"Erreur : impossible de lire {args.entree} ({e.strerror})", file=sys.stderr)
        return 2

    os.makedirs(args.sortie, exist_ok=True)
    configurer_journal(args.sortie)
    log.info("%d adresses à enrichir depuis %s", len(adresses), args.entree)

    vigie = Vigie(jeton)
    cache = lire_json(CACHE, {}) if args.cache else {}
    connues = connues_de_la_reprise(args.sortie)
    resultats, manquees = [], []
    vigie_tombee = False

    for ip in adresses:
        if ip in connues:                                            # E10 : déjà obtenue au passage précédent
            resultats.append(connues[ip])
            log.info("%s : reprise du passage précédent", ip)
            continue
        entree_cache = cache.get(ip)
        if entree_cache and time.time() - entree_cache["t"] < DUREE_CACHE:   # E1
            resultats.append({"ip": ip, "score": entree_cache["score"], "categories": entree_cache["categories"]})
            log.info("%s : cache", ip)
            continue
        if vigie_tombee:                                             # E10 : inutile d'achever une API en panne
            manquees.append(ip)
            continue
        try:
            rep = vigie.appel("GET", f"/reputation/{ip}")
        except JetonRefuse as e:                                     # E7 : on s'arrête net
            log.error("%s", e)
            print(f"Erreur : {e}", file=sys.stderr)
            return 3
        except VigieIndisponible as e:
            log.error("%s : Vigie tombée, les adresses restantes seront reprises au passage suivant", e)
            vigie_tombee = True
            manquees.append(ip)
            continue
        except requests.HTTPError as e:
            log.error("%s : refusée par Vigie (%s), ignorée", ip, e.response.status_code)
            continue
        resultats.append({"ip": ip, "score": rep["score"], "categories": rep["categories"]})
        cache[ip] = {"t": time.time(), "score": rep["score"], "categories": rep["categories"]}
        log.info("%s : api, score %d %s", ip, rep["score"], rep["categories"])

    if args.cache:
        ecrire_json(CACHE, cache)

    # Du score le plus haut au plus bas, puis par ordre alphabétique des adresses
    resultats.sort(key=lambda r: (-r["score"], r["ip"]))
    ecrire_rapports(resultats, args.sortie)
    if args.markdown:
        print(ecrire_markdown(resultats, args.sortie, args.seuil))

    fichier_manquees = os.path.join(args.sortie, FICHIER_MANQUEES)
    log.info("%d requêtes envoyées à Vigie", vigie.nb_appels)
    if manquees:
        with open(fichier_manquees, "w", encoding="utf-8") as f:
            f.write("\n".join(manquees) + "\n")
        log.warning("rapport incomplet : %d adresses manquées (%s), relancer la même commande pour les reprendre",
                    len(manquees), ", ".join(manquees))
        print(f"Rapport incomplet : {len(resultats)} adresses enrichies, {len(manquees)} manquées "
              f"(liste dans {fichier_manquees}). Relance la même commande quand Vigie sera revenue.", file=sys.stderr)
        return CODE_INCOMPLET
    if os.path.exists(fichier_manquees):
        os.remove(fichier_manquees)

    dangereuses = sum(1 for r in resultats if r["score"] >= args.seuil)
    log.info("rapport écrit : %d adresses, %d avec un score de %d ou plus", len(resultats), dangereuses, args.seuil)
    print(f"{len(resultats)} adresses enrichies, {dangereuses} dangereuses (score >= {args.seuil}), rapport dans {args.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
