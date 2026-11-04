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


---

## Jour 3 : Vigie, l'API de sécurité

### Le jeton

Le jeton de la guilde est dans `/etc/mistral/vigie.env`, **dans le serveur uniquement**. Il n'entre jamais dans le dépôt, ni dans un fichier suivi, ni dans un commit, ni dans la crontab. On le charge dans le terminal avant d'utiliser les outils :

```bash
set -a
. /etc/mistral/vigie.env
set +a
```

`set -a` exporte toutes les variables lues ensuite : les programmes lancés depuis ce terminal voient `VIGIE_TOKEN`. Le jeton s'envoie dans l'en-tête `Authorization: Bearer $VIGIE_TOKEN`.

### Découverte de l'API (quête 3.1)

| Route | Rôle |
|---|---|
| `GET /api/v1/` | accueil, liste des routes (sans jeton) |
| `GET /api/v1/reputation/<ip>` | score de réputation d'une adresse, ses catégories et son pays |
| `GET /api/v1/incidents?page=N&par_page=M` | incidents de sécurité, paginés (50 par page au plus) |
| `GET /api/v1/tickets?ip=<ip>` | tickets déjà ouverts pour une adresse |
| `POST /api/v1/tickets` | ouvrir un ticket |

Pour Ponant, la première page d'incidents (`par_page=20`) annonce **75 incidents répartis sur 4 pages** : un outil qui ne lit que la première page en manque 55.

### Codes HTTP observés et conduite de l'outil

| Code | Quand | Ce que l'outil doit faire |
|---|---|---|
| `200` | requête acceptée | lire le JSON et continuer |
| `401` | jeton absent ou invalide | s'arrêter tout de suite avec un message clair (« charger /etc/mistral/vigie.env ») : réessayer ne sert à rien |
| `429` | plus de 5 requêtes par seconde | attendre la durée de l'en-tête `Retry-After` (1 seconde), puis réessayer ; ralentir le rythme pour ne plus le provoquer |
| `503` | panne momentanée (environ une requête de réputation sur 7) | réessayer après une courte pause, en allongeant l'attente à chaque échec, avec un nombre maximal d'essais |
| `400` | paramètre invalide (adresse mal formée, page non numérique) | ne pas réessayer : signaler l'entrée fautive et passer à la suivante |
| `404` | route inconnue, ou page d'incidents au-delà de la dernière | pour la pagination, s'arrêter à la dernière page indiquée par `pages` |

Lors des 12 requêtes d'affilée, les 5 premières reçoivent `200`, les suivantes `429` : la limite est de 5 requêtes par seconde et par guilde.

### `outils/enrichir.py --entree FICHIER --sortie DOSSIER` (quête 3.2)

Interroge Vigie pour chaque adresse du fichier d'entrée (une adresse par ligne, ou la sortie `NOMBRE ADRESSE` de `top-attaquants.sh` : le dernier mot de chaque ligne, sans doublon) et écrit dans DOSSIER :

- `rapport.json` : une liste `{"ip", "score", "categories"}`, du score le plus haut au plus bas, puis par adresse ;
- `rapport.csv` : `ip;score;categories` (catégories séparées par des virgules) ;
- `enrichir.log` : le journal, avec des `INFO` pour chaque adresse et des `WARNING` pour chaque reprise.

```bash
outils/top-attaquants.sh -n 20 > /tmp/top.txt
python3 outils/enrichir.py --entree /tmp/top.txt --sortie /tmp/rapport
jq '.[:3]' /tmp/rapport/rapport.json
```

Le client Vigie est intégré au script (classe `Vigie`) : une `requests.Session` qui envoie le jeton à chaque appel, un limiteur à 5 requêtes par seconde, et des reprises sur 429, 503 et coupure réseau.

| Option | Rôle | Quête annexe |
|---|---|---|
| `--cache` | réutilise les réponses de moins d'une heure (`~/.cache/mistral/reputation.json`), journalise `cache` ou `api` pour chaque adresse | E1 |
| `--markdown` | écrit `rapport.md`, le tableau des adresses dangereuses, à coller dans le README | E3 |
| `--seuil N` | score à partir duquel une adresse est dangereuse (80 par défaut) | E3 |

Comportements ajoutés par les quêtes annexes :

- **E2** : sans `Retry-After`, attentes de 1, 2, 4, 8 et 16 secondes, avec un petit hasard pour que tous les clients ne reviennent pas en même temps.
- **E7** : sur un `401`, un seul appel, le message « jeton refusé » et le code 3.
- **E8** : le limiteur attend juste ce qu'il faut entre deux appels ; un enrichissement seul ne provoque aucun `429`.
- **E10** : si Vigie tombe, l'outil écrit ce qu'il a pu obtenir, liste les adresses manquées dans `manquees.txt` et sort avec le code 4. Relancé avec le même `--sortie`, il reprend les adresses déjà connues et n'interroge que les manquées.

Codes de sortie : `0` succès, `1` erreur de l'API, `2` fichier d'entrée absent, `3` jeton absent ou refusé, `4` rapport incomplet (Vigie indisponible).

**Résultat pour Ponant.** Sur les 17 adresses du journal SSH, **9 sont dangereuses** (score de 80 ou plus), toutes dans la plage `203.0.113.x`, classées `bruteforce-ssh` et souvent `botnet`. En tête : `203.0.113.213` (99), `203.0.113.183` (94) et `203.0.113.66` (93). L'adresse `192.0.2.163`, troisième du classement SSH de lundi, n'a qu'un score de 12 : elle frappe fort mais n'est pas connue comme malveillante. Le classement de lundi dit qui frappe, Vigie dit qui est dangereux.

### `outils/incidents.py --sortie FICHIER.csv` (quête 3.3)

Récupère **toutes les pages** d'incidents (lit `pages` dans la page 1, puis demande les suivantes), les compte par site et par gravité avec un `Counter` dont la clé est `(site, gravite)`, et écrit `site;haute;moyenne;basse;total`, une ligne par site dans l'ordre alphabétique. Chaque page est redemandée sur `429` ou `503` (6 essais au plus) : une page manquée fausserait les totaux, donc l'outil s'arrête en erreur plutôt que d'écrire un tableau faux.

```bash
python3 outils/incidents.py --sortie /tmp/incidents.csv
column -s ';' -t /tmp/incidents.csv
```

**Bilan des incidents pour Sabine** (75 incidents, 4 pages de 20) :

| Site | Haute | Moyenne | Basse | Total |
|---|---:|---:|---:|---:|
| Avignon | 2 | 5 | 11 | 18 |
| Fos | 2 | 3 | 7 | 12 |
| Nice | 2 | 4 | 6 | 12 |
| Toulon | 1 | 7 | 9 | 17 |
| Vitrolles | 3 | 5 | 8 | 16 |
| **Total** | **10** | **24** | **41** | **75** |

La somme des totaux (75) est égale au total annoncé par l'API. S'arrêter à la page 1 n'en aurait compté que 20.

### `outils/tickets.py --rapport rapport.json [--seuil 80] [--simulation]` (quête 3.4)

Ouvre un ticket Vigie pour chaque adresse dont le score atteint le seuil, **sauf si elle en a déjà un** :

1. `GET /tickets?ip=ADRESSE` : si la liste `tickets` de la réponse n'est pas vide, l'adresse est passée ;
2. sinon, `POST /tickets` avec `{"ip", "score", "titre": "Adresse malveillante ..."}`.

L'outil affiche un résumé : tickets créés et tickets déjà ouverts. C'est l'idempotence : relancé, il ne change rien quand tout est déjà fait. Vendredi, cron le lancera toutes les deux minutes sans créer de doublon.

```bash
python3 outils/tickets.py --rapport /tmp/rapport/rapport.json
python3 outils/tickets.py --rapport /tmp/rapport/rapport.json
```

Le premier passage crée 9 tickets, le second en crée 0 et en trouve 9 déjà ouverts.

- `--simulation` (annexe **E4**) : affiche les tickets qui seraient créés, sans rien créer ; le nombre de tickets dans Vigie ne bouge pas.

### `outils/vigie.sh` (quête 3.5)

<!-- À garder seulement si vigie.sh est fusionné ; adapter à la version de la guilde. -->

Interroge Vigie en Bash, avec `curl` et `jq`, sur un serveur sans Python :

```bash
outils/vigie.sh reputation 203.0.113.7
outils/vigie.sh tickets
outils/vigie.sh ticket-ip 203.0.113.7
```

Le jeton vient de `VIGIE_TOKEN`, ou à défaut de `/etc/mistral/vigie.env`, sans jamais être affiché. Le code HTTP est lu avec `curl -w '%{http_code}'` (et non `$?`, qui vaut 0 même sur une erreur 500) : `401` donne « jeton refusé » et le code 3, `429` attend `Retry-After`, `503` réessaie en attendant un peu plus à chaque fois.

---

## Jour 4 : le parc Windows
 
PowerShell 7 tourne dans le serveur du lab : on écrit les scripts `.ps1` dans `outils/` et on les lance dans le serveur.
 
```bash
python3 lab.py shell
pwsh
```
 
### Penser en objets (quête 4.1)
 
On charge l'inventaire une fois : `ConvertFrom-Json` transforme le JSON en objets, un par poste, avec leurs propriétés (`nom`, `site`, `os`, `build`, `defender`, `disque_pct`, `derniere_maj`, `utilisateur`).
 
```powershell
$p = Get-Content -Raw /srv/mistral/parc/postes.json | ConvertFrom-Json
```
 
**Question 2. Combien de postes compte le parc ?**
 
```powershell
$p.Count
```
 
`.Count` donne le nombre d'éléments de la liste : **60 postes**.
 
**Question 3. Combien de postes par système d'exploitation, du plus fréquent au moins fréquent ?**
 
```powershell
$p | Group-Object os | Sort-Object Count -Descending | Select-Object Count, Name
```
 
`Group-Object` regroupe les objets par valeur de la propriété (l'équivalent de `sort | uniq -c`), chaque groupe porte un `Count` et un `Name`.
 
| Système | Postes |
|---|---:|
| Windows 10 22H2 | 24 |
| Windows 11 23H2 | 20 |
| Windows 11 22H2 | 9 |
| Windows 10 1909 | 4 |
| Windows 10 21H2 | 3 |
 
**Question 4. Quels postes n'ont pas d'antivirus actif ?**
 
```powershell
$p | Where-Object { -not $_.defender } | Select-Object nom, site, os
```
 
`$_` est le poste en cours dans le pipeline ; `defender` est un vrai booléen, `-not` garde ceux qui valent `False`. **8 postes** sans Defender : `PC-TOU-124`, `PC-AVI-133`, `PC-NIC-141`, `PC-VIT-119`, `PC-AVI-111`, `PC-FOS-106`, `PC-AVI-103` et `PC-AVI-150`, dont 4 à Avignon.
 
**Question 5. Quels postes ont un disque rempli à plus de 90 %, du plus plein au moins plein ?**
 
```powershell
$p | Where-Object { $_.disque_pct -gt 90 } | Sort-Object disque_pct -Descending | Select-Object nom, site, disque_pct
```
 
`-gt` veut dire « plus grand que » ; `disque_pct` est un nombre, la comparaison est numérique. **14 postes**, de `PC-NIC-141` (99 %) à `PC-NIC-100` (91 %), dont 5 à Nice.
 
**Question 6. Quels sont les 5 postes dont la dernière mise à jour est la plus ancienne au 5 novembre 2026 ?**
 
```powershell
$p | Select-Object nom, site, derniere_maj, @{n='jours'; e={ ([datetime]'2026-11-05' - [datetime]$_.derniere_maj).Days }} | Sort-Object jours -Descending | Select-Object -First 5
```
 
`@{n='jours'; e={ ... }}` ajoute une propriété calculée ; la soustraction de deux `[datetime]` donne une durée, `.Days` son nombre de jours. Les dates se calculent, elles ne se comparent pas comme du texte.
 
| Poste | Site | Dernière mise à jour | Jours |
|---|---|---|---:|
| PC-TOU-140 | Toulon | 2026-07-17 | 111 |
| PC-NIC-105 | Nice | 2026-07-19 | 109 |
| PC-VIT-157 | Vitrolles | 2026-07-26 | 102 |
| PC-AVI-127 | Avignon | 2026-08-01 | 96 |
| PC-NIC-118 | Nice | 2026-08-10 | 87 |
 
**À retenir.** Trois postes cumulent les problèmes : `PC-NIC-141` (sans antivirus, disque à 99 %), `PC-TOU-124` (sans antivirus, disque à 97 %) et `PC-AVI-150` (sans antivirus, disque à 92 %). Ce sont les premiers à traiter.

### Les comptes dormants (quête 4.3)

`outils/Get-ComptesDormants.ps1 -Fichier utilisateurs.csv -Sortie dormants.csv [-Jours 90] [-Date AAAA-MM-JJ]`

Garde les comptes **humains et actifs** de l'annuaire (ni comptes de service `svc-...`, ni comptes désactivés) dont la dernière connexion (`DernierLogon`) date de `-Jours` jours ou plus à la `-Date`. Écrit `Login;Service;JoursInactif`, du compte le plus ancien au plus récent, puis par ordre alphabétique de login.

```bash
pwsh -File outils/Get-ComptesDormants.ps1 -Fichier /srv/mistral/parc/utilisateurs.csv -Sortie /tmp/dormants.csv -Date 2026-11-05
```

**Liste pour Jeanne, au 5 novembre 2026 : 17 comptes dormants depuis 90 jours ou plus.**

| Login | Service | Jours sans connexion |
|---|---|---:|
| u1053 | Direction | 368 |
| u1074 | Exploitation | 362 |
| u1014 | Transport | 329 |
| u1024 | Compta | 311 |
| u1075 | Direction | 307 |
| u1008 | Exploitation | 300 |
| u1060 | DSI | 295 |
| u1054 | Direction | 293 |
| u1003 | RH | 272 |
| u1059 | Transport | 222 |
| u1049 | Exploitation | 202 |
| u1056 | Direction | 199 |
| u1048 | Transport | 174 |
| u1020 | Compta | 154 |
| u1038 | Exploitation | 120 |
| u1028 | DSI | 116 |
| u1061 | Exploitation | 116 |

Onze comptes n'ont pas servi depuis plus de 200 jours, et `u1053` depuis plus d'un an. Les plus sensibles sont les 4 comptes de la Direction et les 2 de la DSI : ce sont les premiers à désactiver, après vérification auprès des services.
