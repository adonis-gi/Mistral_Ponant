#!/usr/bin/env python3
import argparse
import json
import os
import sys
import requests

API_BASE_URL = "http://vigie.mistral.test:8080/api/v1/tickets"
ENV_FILE_PATH = "/etc/mistral/vigie.env"


class CustomArgumentParser(argparse.ArgumentParser):
    """Affiche automatiquement l'aide complète en cas d'erreur d'argument."""
    def error(self, message):
        sys.stderr.write(f"Erreur de syntaxe : {message}\n\n")
        self.print_help(sys.stderr)
        sys.exit(2)


def charger_jeton(chemin_env: str = ENV_FILE_PATH) -> str:
    """Charge le jeton d'authentification depuis le fichier de configuration."""
    if not os.path.exists(chemin_env):
        print(f"Erreur : Le fichier de configuration '{chemin_env}' est introuvable.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(chemin_env, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Extrait la valeur si le fichier est sous la forme CLE=VALEUR ou valeur brute
                    if "=" in line:
                        _, val = line.split("=", 1)
                        return val.strip("'\"")
                    return line
    except Exception as e:
        print(f"Erreur lors de la lecture de '{chemin_env}' : {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Erreur : Aucun jeton valide trouvé dans '{chemin_env}'.", file=sys.stderr)
    sys.exit(1)


def gerer_erreur_http(e: requests.exceptions.HTTPError, ip: str) -> None:
    """Interprète et affiche les erreurs HTTP spécifiques renvoyées par l'API."""
    status_code = e.response.status_code if e.response is not None else None

    if status_code == 401:
        print(f"[ERREUR 401] Authentification échouée pour l'IP {ip} : Jeton invalide ou expiré.", file=sys.stderr)
    elif status_code == 403:
        print(f"[ERREUR 403] Accès interdit pour l'IP {ip} : Droits insuffisants.", file=sys.stderr)
    elif status_code == 404:
        print(f"[ERREUR 404] Ressource API introuvable pour l'IP {ip}.", file=sys.stderr)
    elif status_code == 503:
        print(f"[ERREUR 503] Service indisponible pour l'IP {ip} : L'API Vigie est temporairement inaccessible.", file=sys.stderr)
    else:
        print(f"[ERREUR HTTP {status_code}] Échec pour l'IP {ip} : {e}", file=sys.stderr)


def traiter_rapport(fichier_rapport: str, seuil: int, jeton: str) -> bool:
    """Parcourt le rapport, vérifie l'idempotence et crée les tickets."""
    try:
        with open(fichier_rapport, "r", encoding="utf-8") as f:
            donnees = json.load(f)
    except FileNotFoundError:
        print(f"Erreur : Le fichier '{fichier_rapport}' est introuvable.", file=sys.stderr)
        return False
    except json.JSONDecodeError as e:
        print(f"Erreur : Le fichier '{fichier_rapport}' n'est pas un JSON valide ({e}).", file=sys.stderr)
        return False

    headers = {
        "Authorization": f"Bearer {jeton}",
        "Content-Type": "application/json"
    }

    ips_traitees = set()
    succes_global = True

    for item in donnees:
        ip = item.get("ip")
        score = item.get("score", 0)

        # Filtrage : IP absente ou score inférieur au seuil
        if not ip or score < seuil:
            continue

        # Idempotence locale durant la même exécution
        if ip in ips_traitees:
            print(f"[IGNORÉ] IP {ip} : déjà traitée dans cette session.")
            continue

        try:
            # 1. Idempotence distante : GET /tickets?ip=ADRESSE
            response_get = requests.get(API_BASE_URL, params={"ip": ip}, headers=headers, timeout=10)
            response_get.raise_for_status()
            tickets_existants = response_get.json()

            if tickets_existants:
                print(f"[IGNORÉ] IP {ip} (score: {score}) : un ticket existe déjà sur l'API.")
                ips_traitees.add(ip)
                continue

            # 2. Création du ticket : POST /tickets
            payload = {
                "ip": ip,
                "score": score,
                "titre": f"Adresse malveillante {ip}"
            }

            response_post = requests.post(API_BASE_URL, json=payload, headers=headers, timeout=10)
            response_post.raise_for_status()
            print(f"[CRÉÉ] Ticket créé pour l'IP {ip} (score: {score}).")

            ips_traitees.add(ip)

        except requests.exceptions.HTTPError as e:
            gerer_erreur_http(e, ip)
            succes_global = False
        except requests.exceptions.ConnectionError:
            print(f"[ERREUR RÉSEAU] Impossible de contacter l'API Vigie pour l'IP {ip}.", file=sys.stderr)
            succes_global = False
        except requests.exceptions.Timeout:
            print(f"[ERREUR TIMEOUT] L'API Vigie n'a pas répondu dans le délai imparti pour l'IP {ip}.", file=sys.stderr)
            succes_global = False
        except requests.RequestException as e:
            print(f"[ERREUR API] Erreur imprévue pour l'IP {ip} : {e}", file=sys.stderr)
            succes_global = False

    return succes_global


def main() -> int:
    parser = CustomArgumentParser(
        description="Générateur de tickets Vigie à partir d'un rapport de sécurité JSON.",
        epilog="Exemple d'utilisation :\n  python3 tickets.py --rapport rapport.json --seuil 80",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-r", "--rapport",
        required=True,
        help="Chemin obligatoire vers le fichier JSON de rapport (ex: rapport.json)"
    )
    parser.add_argument(
        "-s", "--seuil",
        type=int,
        default=80,
        help="Seuil de score minimal pour déclencher la création d'un ticket (défaut : 80)"
    )

    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    args = parser.parse_args()

    # Chargement du jeton d'authentification
    jeton = charger_jeton(ENV_FILE_PATH)

    # Traitement du fichier
    succes = traiter_rapport(args.rapport, args.seuil, jeton)

    # Renvoie 0 si tout s'est bien passé, 1 si une erreur est survenue
    return 0 if succes else 1


if __name__ == "__main__":
    sys.exit(main())

