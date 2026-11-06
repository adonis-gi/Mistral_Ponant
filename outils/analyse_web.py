"""Résume un journal d'accès web : statuts, adresses en 404 et chemins sensibles."""
import json
import re
import sys
from collections import Counter

from mistral_commun import ParseurArguments, classer, ecrire_rapport

# Une ligne du journal ressemble à :
# 10.42.3.17 - - [02/Nov/2026:08:15:02 +0100] "GET /suivi HTTP/1.1" 200 5120 "-" "Mozilla/5.0"
# Les 4 groupes entre parenthèses capturent : adresse, méthode, chemin, statut.
LIGNE = re.compile(r'^(\S+) \S+ \S+ \[[^\]]+\] "(\S+) (\S+) [^"]*" (\d{3}) ')

# Quêtes annexes : l'heure de la requête (après "[jj/Mmm/aaaa:") et le User-Agent (dernier champ entre guillemets).
HEURE = re.compile(r'\[[^:\]]+:(\d{2}):')
AGENT = re.compile(r'"([^"]*)"\s*$')

# Outils automatiques reconnus dans le User-Agent (M7).
OUTILS_AUTO = ["curl", "python-requests"]

# Les chemins que cherchent les robots en quête de secrets.
SENSIBLES = ["/.env", "/.git/config", "/wp-login.php", "/wp-admin/", "/phpmyadmin/", "/backup.zip", "/admin/"]


def analyser(chemin_fichier, top):
    """Lit le journal et renvoie le résumé sous forme de dictionnaire."""
    lignes = 0
    statuts = Counter()      # statut -> nombre de requêtes
    ip_404 = Counter()       # adresse -> nombre de 404
    sensibles = Counter()    # chemin sensible -> nombre de demandes
    heures_404 = Counter()   # M3 : heure (00 à 23) -> nombre de 404
    agents = Counter()       # M7 : User-Agent -> nombre de requêtes

    with open(chemin_fichier, encoding="utf-8", errors="replace") as f:
        for ligne in f:
            m = LIGNE.match(ligne)
            if not m:
                continue  # ligne qui ne ressemble pas à un accès web : on l'ignore
            ip, _methode, chemin, statut = m.groups()
            lignes += 1
            statuts[statut] += 1
            if statut == "404":
                ip_404[ip] += 1
                h = HEURE.search(ligne)
                if h:
                    heures_404[h.group(1)] += 1
            a = AGENT.search(ligne)
            agents[a.group(1) if a else "(inconnu)"] += 1
            if chemin in SENSIBLES:
                sensibles[chemin] += 1

    return {
        "lignes": lignes,
        "statuts": dict(statuts),
        "top_ip_404": classer(ip_404)[:top],
        "chemins_sensibles": classer(sensibles),
    }, heures_404, agents


def histogramme_heures(heures_404):
    """M3 : les 404 par heure, une barre de # par tranche de 10 requêtes."""
    lignes = ["Les 404 par heure (# = 10 requêtes) :"]
    for heure in range(24):
        nombre = heures_404.get(f"{heure:02d}", 0)
        lignes.append(f"  {heure:02d}h  {'#' * (nombre // 10):<12} {nombre}")
    return "\n".join(lignes)


def resume_agents(agents, total):
    """M7 : les 5 User-Agent les plus fréquents et la part des requêtes faites par des outils."""
    lignes = ["Les 5 User-Agent les plus fréquents :"]
    for agent, nombre in classer(agents)[:5]:
        lignes.append(f"  {nombre:5d}  {agent}")
    auto = sum(n for agent, n in agents.items() if any(o in agent for o in OUTILS_AUTO))
    part = 100 * auto / total if total else 0
    lignes.append(f"Requêtes automatiques ({', '.join(OUTILS_AUTO)}) : {auto} sur {total}, soit {part:.1f} %")
    return "\n".join(lignes)


def texte(res):
    """Construit le résumé lisible pour Jeanne, sous forme d'une chaîne."""
    lignes = [f"Lignes analysées : {res['lignes']}", "", "Statuts HTTP :"]
    for statut, nombre in sorted(res["statuts"].items()):
        lignes.append(f"  {statut} : {nombre}")
    lignes += ["", f"Top {len(res['top_ip_404'])} des adresses en 404 :"]
    for ip, nombre in res["top_ip_404"]:
        lignes.append(f"  {nombre:5d}  {ip}")
    lignes += ["", "Chemins sensibles demandés :"]
    for chemin, nombre in res["chemins_sensibles"]:
        lignes.append(f"  {nombre:5d}  {chemin}")
    return "\n".join(lignes)


def main():
    parser = ParseurArguments(description=__doc__)
    parser.add_argument("fichier", help="journal d'accès à analyser")
    parser.add_argument("--top", type=int, default=10, help="nombre d'adresses en 404 à afficher (10 par défaut)")
    parser.add_argument("--format", choices=["texte", "json"], default="texte", help="format de sortie (texte par défaut)")
    parser.add_argument("--par-heure", action="store_true", help="ajoute l'histogramme des 404 par heure (texte)")
    parser.add_argument("--agents", action="store_true", help="ajoute les User-Agent et la part de requêtes automatiques (texte)")
    args = parser.parse_args()

    try:
        res, heures_404, agents = analyser(args.fichier, args.top)
    except OSError as e:
        print(f"Erreur : impossible de lire {args.fichier} ({e.strerror})", file=sys.stderr)
        return 2

    if args.format == "json":
        contenu, extension = json.dumps(res, ensure_ascii=False), "json"
    else:
        parties = [texte(res)]
        if args.par_heure:
            parties.append(histogramme_heures(heures_404))
        if args.agents:
            parties.append(resume_agents(agents, res["lignes"]))
        contenu, extension = "\n\n".join(parties), "txt"
    print(contenu)  # affichage à l'écran, inchangé

    try:
        rapport = ecrire_rapport("analyse-web", contenu, extension)
        print(f"Rapport enregistré dans {rapport}", file=sys.stderr)
    except OSError as e:
        print(f"Attention : rapport non enregistré ({e.strerror})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
