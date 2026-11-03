# Mistral_Ponant

Bootcamp 3 Cybersup - Scripting & Automatisation

Dépôt de la guilde **Ponant** (site d'Avignon) pour l'Opération Mistral : les outils qui automatisent le travail de Malik sur `srv-fichiers`, le serveur de fichiers de Mistral Logistique.

## Attribution des rôles

| Rôle | Membre | Il veille à |
|---|---|---|
| Chef d'équipe | Adonis | le dépôt Git, le planning du jour, les fusions, la soutenance |
| Artisan Bash | Anthony | les scripts Bash et la planification |
| Mage Python | Arnaud | les outils Python et PowerShell |
| Gardien | Marc | la qualité : shellcheck, tests, revue des pull requests, aucun secret dans Git |

## Organisation du dépôt

```
outils/          les outils de la guilde (Bash et Python)
rapports/        les rapports produits par les outils (top-attaquants, analyse-web)
resultats-jN/    les notes du vérificateur, une par journée
requirements.txt les dépendances Python du venv
```

### Branches

- `main` : la production. Le vérificateur du soir tourne sur cette branche. On n'y pousse jamais directement : tout arrive par une pull request relue.
- `preprod` : l'intégration. Les outils du jour y sont réunis et testés ensemble avant la PR `preprod → main` du soir.
- une branche par outil (`analyse-web`, `comptes`…), créée depuis `preprod` et fusionnée par une PR relue par un autre membre.

### Règles

- Git (commit, push, pull) se fait sur sa machine ; le serveur du lab ne sert qu'à exécuter et tester.
- Le venv `.venv/` se crée dans le serveur et n'entre jamais dans Git (voir `.gitignore`).
- Le jeton de l'API Vigie n'entre jamais dans le dépôt.
- Fins de ligne LF imposées par `.gitattributes`.

## Installation

```bash
python3 lab.py installer
git clone git@github.com:adonis-gi/Mistral_Ponant.git depot
python3 lab.py demarrer
python3 lab.py up jN --guilde ponant
python3 lab.py shell
```

Dans le serveur, l'environnement Python de la guilde :

```bash
cd /guilde
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Si le serveur n'a pas accès à Internet, `python3 -m venv --system-site-packages .venv` réutilise le `requests` déjà installé dans le lab.

---

## Jour 1 : le serveur qui étouffe

Trois scripts Bash robustes (`set -euo pipefail`, `getopts`, messages d'erreur sur stderr, codes de sortie), vérifiés par `shellcheck -S warning`.

### `outils/sauvegarde.sh [-k N] SOURCE [DESTINATION]`

Archive horodatée `NOM-AAAAMMJJ-HHMMSS.tar.gz` du dossier SOURCE dans DESTINATION (`/srv/sauvegardes` par défaut), en ne gardant que les N archives les plus récentes de cette source (7 par défaut). L'archive est d'abord écrite en `.part`, puis renommée : une archive interrompue est effacée par `trap`. Chaque action est journalisée dans `/var/log/mistral/sauvegarde.log`.

```bash
outils/sauvegarde.sh /srv/mistral/partage
outils/sauvegarde.sh -k 3 /srv/mistral/partage /tmp/essai
```

Codes de sortie : `0` succès, `1` mauvaise utilisation, `2` dossier source absent.

### `outils/top-attaquants.sh [-n N] [FICHIER]`

Les N adresses (5 par défaut) qui ont le plus d'échecs `Failed password` dans FICHIER (`/var/log/mistral/auth.log` par défaut), au format `NOMBRE ADRESSE`. Le résultat s'affiche à l'écran et est enregistré dans `rapports/top-attaquants-AAAA-MM-JJ-HH-MM-SS.txt`.

```bash
outils/top-attaquants.sh
outils/top-attaquants.sh -n 3 /var/log/mistral/auth.log
```

Code de sortie `2` si le fichier est illisible.

### `outils/menage-logs.sh [-n] [-j JOURS] DOSSIER`

Compresse avec gzip les `.log` de DOSSIER modifiés il y a JOURS jours ou plus (2 par défaut). Avec `-n`, affiche ce qui serait fait sans rien toucher. Relancé, il ne fait rien et sort avec le code 0.

```bash
outils/menage-logs.sh -n /var/log/mistral/archives
outils/menage-logs.sh /var/log/mistral/archives
```

### Analyse pour Jeanne : qui frappe à la porte ?

- Le journal SSH de la semaine compte **3 237 échecs de connexion** venant de 17 adresses. Les cinq plus acharnées : `203.0.113.213` (413), `203.0.113.207` (366), `192.0.2.163` (358), `203.0.113.97` (347) et `203.0.113.13` (321).
- Quatre des cinq viennent de la même plage `203.0.113.0/24` et visent surtout `root` et des comptes inexistants : c'est une attaque par force brute automatisée, pas des salariés qui se trompent de mot de passe.
- Les échecs internes (`10.42.x.x`) ne sont que 6, sur trois postes : ce sont des fautes de frappe de salariés.

---

## Jour 2 : quarante saisonniers et un site de suivi

Les outils Python suivent les règles de la guilde : une docstring d'une ligne, `argparse`, une fonction `main()` qui renvoie le code de sortie, et `sys.exit(main())` à la fin.

### `outils/comptes.py --csv FICHIER --sortie DOSSIER [--domaine mistral.test]`

Transforme l'export RH des saisonniers en comptes propres :

- `DOSSIER/comptes.csv` : `login;email;nom;prenom;site;date_arrivee`, trié par login. Le login est `prenom.nom` en minuscules, sans accents, espaces ni apostrophes (`jean-baptiste.ndiaye`, `emma.oneil`) ; un homonyme reçoit `2`, puis `3`. Les dates passent au format ISO.
- `DOSSIER/rejets.csv` : `ligne;raison` pour chaque ligne refusée (`nom manquant`, `prenom manquant`, `date invalide`, `doublon`).

```bash
python3 outils/comptes.py --csv /srv/mistral/rh/saisonniers.csv --sortie /tmp/rh
```

Code de sortie `2` si le fichier CSV est absent.

### `outils/comptes.sh FICHIER_CSV DOSSIER`

Lanceur Bash de `comptes.py` : vérifie ses arguments, convertit l'export en UTF-8 s'il arrive en Latin-1, lance `comptes.py` avec le Python du venv (ou `python3`), propage son code de sortie et journalise le résultat dans `/var/log/mistral/comptes.log`.

```bash
outils/comptes.sh /srv/mistral/rh/saisonniers.csv /tmp/essai
```

### `outils/analyse_web.py FICHIER [--top N] [--format texte|json] [--par-heure] [--agents]`

Résume le journal d'accès du site de suivi de colis : nombre de lignes, statuts HTTP, les N adresses (10 par défaut) qui ont le plus de 404, et les demandes de chemins sensibles (`/.env`, `/.git/config`, `/wp-login.php`, `/wp-admin/`, `/phpmyadmin/`, `/backup.zip`, `/admin/`). Le résultat s'affiche à l'écran et est enregistré dans `rapports/analyse-web-AAAA-MM-JJ-HH-MM-SS.txt` (ou `.json`).

- `--par-heure` (annexe M3) : histogramme des 404 par heure, un `#` par tranche de 10 requêtes.
- `--agents` (annexe M7) : les 5 User-Agent les plus fréquents et la part des requêtes faites par des outils (`curl`, `python-requests`).

```bash
python3 outils/analyse_web.py /srv/mistral/web/access.log
python3 outils/analyse_web.py /srv/mistral/web/access.log --top 3 --format json | jq .
python3 outils/analyse_web.py /srv/mistral/web/access.log --par-heure --agents
```

Code de sortie `2` si le journal est absent.

### Bilan des saisonniers pour Nicolas

L'export RH de Ponant donne **42 comptes créés et 4 lignes rejetées** : deux dates impossibles (lignes 14 et 29), un nom manquant (ligne 20) et un prénom manquant (ligne 24). Les lignes rejetées sont dans `rejets.csv`, à corriger par la RH.

### Analyse pour Jeanne : qui visite le site de suivi ?

- Les adresses qui récoltent le plus de 404 viennent toutes des plages `203.0.113.x` et `198.51.100.x` (ADRESSE_1 : N, ADRESSE_2 : N, ADRESSE_3 : N) : ce ne sont pas des clients.
- Elles demandent `/.git/config`, `/.env`, `/backup.zip` ou `/phpmyadmin/`, des fichiers qui contiennent des mots de passe ou le code du site : ce sont des robots qui cherchent des secrets oubliés.
- Environ la moitié des requêtes vient d'outils automatiques (`curl`, `python-requests`), et les 404 tombent à toute heure, sans pause la nuit : rien de tout cela n'est humain. Il faut vérifier qu'aucun de ces fichiers n'est réellement exposé sur le serveur.
