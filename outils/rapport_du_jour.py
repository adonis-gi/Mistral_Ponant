"""Rapport du jour pour Sabine, en Markdown : adresses dangereuses, tickets, sauvegarde, postes non conformes."""
import csv
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

import requests

from enrichir import JetonAbsent, JetonRefuse, Vigie, VigieIndisponible, lire_jeton
from mistral_commun import RACINE, ParseurArguments

FICHIER_JETON = "/etc/mistral/vigie.env"


def charger_jeton():
    """Jeton depuis VIGIE_TOKEN, sinon depuis /etc/mistral/vigie.env (comme la veille lancée par cron)."""
    try:
        return lire_jeton()
    except JetonAbsent:
        try:
            with open(FICHIER_JETON, encoding="utf-8") as f:
                for ligne in f:
                    if ligne.startswith("VIGIE_TOKEN="):
                        return ligne.split("=", 1)[1].strip().strip("'\"")
        except OSError:
            pass
    return ""


def section_adresses(rapport_veille, seuil):
    """Les adresses dangereuses vues par la dernière veille."""
    lignes = ["## Adresses dangereuses", ""]
    try:
        with open(rapport_veille, encoding="utf-8") as f:
            adresses = json.load(f)
        maj = datetime.datetime.fromtimestamp(os.path.getmtime(rapport_veille))
    except (OSError, ValueError):
        return lignes + [f"Aucun rapport de veille lisible ({rapport_veille}) : la veille a-t-elle tourné ?", ""]

    dangereuses = [a for a in adresses if a["score"] >= seuil]
    lignes.append(f"Dernière veille : {maj:%d/%m/%Y %H:%M}. **{len(dangereuses)} adresses dangereuses** "
                  f"(score de {seuil} ou plus) sur {len(adresses)} adresses en échec dans le journal SSH.")
    lignes.append("")
    if dangereuses:
        lignes += ["| Adresse | Score | Catégories |", "|---|---:|---|"]
        for a in dangereuses:
            lignes.append(f"| `{a['ip']}` | {a['score']} | {', '.join(a['categories']) or '-'} |")
        lignes.append("")
    return lignes


def section_tickets(jeton):
    """Les tickets ouverts dans Vigie, pour des adresses et pour des postes."""
    lignes = ["## Tickets ouverts dans Vigie", ""]
    if not jeton:
        return lignes + [f"Jeton introuvable ({FICHIER_JETON}) : tickets non consultés.", ""]
    try:
        tickets = Vigie(jeton, essais=3).appel("GET", "/tickets").get("tickets", [])
    except (JetonRefuse, VigieIndisponible, requests.RequestException) as e:
        return lignes + [f"Vigie injoignable ({e}) : tickets non consultés.", ""]

    par_ip = [t for t in tickets if t.get("ip")]
    par_poste = [t for t in tickets if t.get("poste")]
    aujourdhui = datetime.date.today().isoformat()
    du_jour = [t for t in tickets if str(t.get("cree", "")).startswith(aujourdhui)]
    lignes.append(f"**{len(tickets)} tickets** : {len(par_ip)} pour des adresses, {len(par_poste)} pour des postes, "
                  f"dont {len(du_jour)} ouverts aujourd'hui.")
    lignes.append("")
    if tickets:
        lignes += ["| N° | Ouvert le | Objet | Titre |", "|---:|---|---|---|"]
        for t in sorted(tickets, key=lambda t: t.get("id", 0), reverse=True)[:15]:
            objet = t.get("ip") or t.get("poste") or "-"
            lignes.append(f"| {t.get('id', '-')} | {str(t.get('cree', '-')).replace('T', ' ')} | `{objet}` | {t.get('titre', '')} |")
        if len(tickets) > 15:
            lignes.append(f"| … | | | {len(tickets) - 15} tickets plus anciens |")
        lignes.append("")
    return lignes


def section_sauvegarde(dossier):
    """La dernière archive de sauvegarde, et son âge."""
    lignes = ["## Dernière sauvegarde", ""]
    archives = glob.glob(os.path.join(dossier, "*.tar.gz"))
    if not archives:
        return lignes + [f"⚠️ **Aucune sauvegarde** dans `{dossier}`.", ""]
    derniere = max(archives, key=os.path.getmtime)
    date = datetime.datetime.fromtimestamp(os.path.getmtime(derniere))
    age_h = (datetime.datetime.now() - date).total_seconds() / 3600
    taille = os.path.getsize(derniere) / 1024
    alerte = " ⚠️ **plus de 24 heures**" if age_h > 24 else ""
    lignes.append(f"`{os.path.basename(derniere)}`, le {date:%d/%m/%Y à %H:%M} (il y a {age_h:.0f} h){alerte}, "
                  f"{taille:.0f} Ko. {len(archives)} archive(s) conservée(s).")
    return lignes + [""]


def lire_audit(audit, fichier_parc):
    """Lit non-conformes.csv ; s'il n'est pas fourni, lance Audit-Parc.ps1 dans un dossier temporaire."""
    if audit:
        with open(audit, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f, delimiter=";"))
    pwsh = shutil.which("pwsh")
    script = os.path.join(RACINE, "outils", "Audit-Parc.ps1")
    if not pwsh or not os.path.exists(fichier_parc):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([pwsh, "-NoProfile", "-File", script, "-Fichier", fichier_parc, "-Sortie", tmp],
                       check=True, capture_output=True, timeout=120)
        with open(os.path.join(tmp, "non-conformes.csv"), encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f, delimiter=";"))


def section_postes(audit, fichier_parc):
    """Les postes non conformes, par raison et par site."""
    lignes = ["## Postes non conformes", ""]
    try:
        postes = lire_audit(audit, fichier_parc)
    except (OSError, subprocess.SubprocessError) as e:
        return lignes + [f"Audit du parc impossible ({e}).", ""]
    if postes is None:
        return lignes + [f"Audit du parc non disponible (pwsh ou {fichier_parc} absent).", ""]

    raisons = {"build": 0, "defender": 0, "disque": 0, "maj": 0}
    for p in postes:
        for r in p["raisons"].split("|"):
            raisons[r] = raisons.get(r, 0) + 1
    lignes.append(f"**{len(postes)} postes non conformes** : {raisons['defender']} sans antivirus, "
                  f"{raisons['disque']} disques presque pleins, {raisons['maj']} sans mise à jour récente, "
                  f"{raisons['build']} sur une version de Windows trop ancienne.")
    lignes.append("")
    graves = [p for p in postes if "defender" in p["raisons"] or p["raisons"].count("|") >= 1]
    if graves:
        lignes += ["À traiter en premier (sans antivirus, ou plusieurs problèmes) :", "",
                   "| Poste | Site | Problèmes |", "|---|---|---|"]
        for p in graves:
            lignes.append(f"| {p['nom']} | {p['site']} | {p['raisons'].replace('|', ', ')} |")
        lignes.append("")
    return lignes


def main():
    parser = ParseurArguments(description=__doc__)
    parser.add_argument("--rapport-veille", default="/var/lib/mistral/veille/rapport.json",
                        help="rapport.json de la dernière veille")
    parser.add_argument("--sauvegardes", default="/srv/sauvegardes", help="dossier des archives de sauvegarde")
    parser.add_argument("--parc", default="/srv/mistral/parc/postes.json", help="inventaire des postes")
    parser.add_argument("--audit", help="non-conformes.csv déjà produit (sinon Audit-Parc.ps1 est lancé)")
    parser.add_argument("--seuil", type=int, default=80, help="score d'une adresse dangereuse (80)")
    parser.add_argument("--sortie", help="fichier Markdown à écrire (sinon rapports/rapport-du-jour-AAAA-MM-JJ.md)")
    args = parser.parse_args()

    maintenant = datetime.datetime.now()
    lignes = [f"# Rapport du jour, Mistral Logistique, {maintenant:%d/%m/%Y à %H:%M}", "",
              "Produit automatiquement par le kit de veille de la guilde Ponant.", ""]
    lignes += section_adresses(args.rapport_veille, args.seuil)
    lignes += section_tickets(charger_jeton())
    lignes += section_sauvegarde(args.sauvegardes)
    lignes += section_postes(args.audit, args.parc)
    texte = "\n".join(lignes)

    sortie = args.sortie or os.path.join(RACINE, "rapports", f"rapport-du-jour-{maintenant:%Y-%m-%d}.md")
    os.makedirs(os.path.dirname(os.path.abspath(sortie)), exist_ok=True)
    with open(sortie, "w", encoding="utf-8") as f:
        f.write(texte + "\n")
    print(texte)
    print(f"\nRapport enregistré dans {sortie}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
