#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage : $0 {reputation IP | tickets | ticket-ip IP}" >&2
    exit 2
}

if [[ $# -lt 1 ]]; then
    usage
fi

case "$1" in
    reputation|ticket-ip)
        if [[ $# -ne 2 ]]; then
            usage
        fi
        ACTION="$1"
        IP="$2"
        ;;
    tickets)
        if [[ $# -ne 1 ]]; then
            usage
        fi
        ACTION="$1"
        IP=""
        ;;
    *)
        usage
        ;;
esac

# Récupération du jeton Vigie
if [[ -z "${VIGIE_TOKEN:-}" && -r /etc/mistral/vigie.env ]]; then
    VIGIE_TOKEN="$(sed -n 's/^VIGIE_TOKEN=//p' /etc/mistral/vigie.env)"
fi

if [[ -z "${VIGIE_TOKEN:-}" ]]; then
    echo "Erreur : jeton Vigie absent" >&2
    exit 3
fi

# Adresse de base de l'API
API="http://vigie.mistral.test:8080/api/v1"

# Fonction commune pour effectuer les requêtes HTTP
# E8 : limiteur partagé, maximum 5 requêtes par seconde
limiter_debit() {
    local fichier="/var/lock/mistral-vigie-debit.lock"
    local dernier=0
    local maintenant
    local manque
    local delai

    (
        # Un seul processus peut contrôler le délai à la fois
        flock -x 9

        # Lire l'heure de la dernière requête
        if [[ -s "$fichier" ]]; then
            IFS= read -r dernier < "$fichier" || true
        fi

        if [[ ! "$dernier" =~ ^[0-9]+$ ]]; then
            dernier=0
        fi

        # Heure actuelle en nanosecondes
        maintenant=$(date +%s%N)

        # 201 millions de nanosecondes = 201 ms
        manque=$((201000000 - (maintenant - dernier)))

        if (( manque > 0 )); then
            printf -v delai '0.%09d' "$manque"
            sleep "$delai"
        fi

        # Enregistrer l'heure du nouvel appel
        date +%s%N > "$fichier"
    ) 9<>"$fichier"
}

appel() {
    local url="$1"
    local code_http
    local attente
    local tentative
    local delai

    for tentative in 1 2 3 4 5 6; do

        limiter_debit

        if code_http=$(curl -s -m 5 \
            -H "Authorization: Bearer $VIGIE_TOKEN" \
            -D "$ENTETES" \
            -o "$CORPS" \
            -w '%{http_code}' \
            "$url"); then

            # HTTP 401 : jeton invalide
            if [[ "$code_http" == "401" ]]; then
                echo "Erreur : jeton Vigie refusé (HTTP 401)" >&2
                return 3
            fi

            # HTTP 429 : trop de requêtes
            if [[ "$code_http" == "429" ]]; then

                if [[ "$tentative" -eq 6 ]]; then
                    echo "Erreur : trop de requêtes après 6 tentatives" >&2
                    return 1
                fi

                # Lecture de l'en-tête Retry-After
                attente=$(awk 'tolower($1) == "retry-after:" {gsub(/\r/, "", $2); print $2; exit}' "$ENTETES")

                if [[ "$attente" =~ ^[0-9]+$ ]]; then
                    # Respecter le délai indiqué par le serveur
                    delai="$attente"
                else
                    # Sans Retry-After : backoff exponentiel avec jitter
                    attente=$((2 ** (tentative - 1)))
                    printf -v delai '%d.%03d' "$attente" "$((RANDOM % 301))"
                fi

                echo "HTTP 429 : attente de $delai seconde(s) avant de réessayer" >&2
                sleep "$delai"
                continue
            fi

            # HTTP 503 : serveur temporairement indisponible
            if [[ "$code_http" == "503" ]]; then

                if [[ "$tentative" -eq 6 ]]; then
                    echo "Erreur : Vigie indisponible après 6 tentatives" >&2
                    return 1
                fi

                # E2 : attente exponentielle 1, 2, 4, 8, 16 secondes
                attente=$((2 ** (tentative - 1)))

                # E2 : ajout d'un jitter de 0 à 300 millisecondes
                printf -v delai '%d.%03d' "$attente" "$((RANDOM % 301))"

                echo "HTTP 503 : nouvelle tentative dans $delai seconde(s)" >&2

                sleep "$delai"
                continue
            fi

            # Retourner le code HTTP obtenu
            printf '%s\n' "$code_http"
            return 0

        else
            echo "Erreur : impossible de contacter Vigie" >&2
            return 1
        fi

    done
}

# Fichiers temporaires communs à toutes les commandes
CORPS=$(mktemp)
ENTETES=$(mktemp)

# Nettoyage automatique
nettoyer() {
    rm -f -- "$CORPS" "$ENTETES"
}

trap nettoyer EXIT

# Commande tickets
if [[ "$ACTION" == "tickets" ]]; then

    CODE_HTTP=$(appel "$API/tickets")
    echo "Code HTTP : $CODE_HTTP"

    if [[ "$CODE_HTTP" == "200" ]]; then
        echo "Nombre de tickets :"
        jq '.tickets | length' "$CORPS"
    else
        echo "Réponse HTTP à gérer : $CODE_HTTP" >&2
        exit 1
    fi
fi

# Commande reputation : consulter la réputation d'une IP
if [[ "$ACTION" == "reputation" ]]; then

    CODE_HTTP=$(appel "$API/reputation/$IP")

    if [[ "$CODE_HTTP" == "200" ]]; then
        echo "Réputation de l'adresse IP $IP :"
        jq '.' "$CORPS"
    else
        echo "Erreur : réponse HTTP $CODE_HTTP" >&2
        exit 1
    fi
fi

# Commande ticket-ip : rechercher les tickets associés à une IP
if [[ "$ACTION" == "ticket-ip" ]]; then

    CODE_HTTP=$(appel "$API/tickets?ip=$IP")

    if [[ "$CODE_HTTP" == "200" ]]; then
        echo "Tickets associés à l'adresse IP $IP :"
        jq '.tickets' "$CORPS"
    else
        echo "Erreur : réponse HTTP $CODE_HTTP" >&2
        exit 1
    fi
fi
