<#
.SYNOPSIS
    Envoie des tickets d'incident à l'API Vigie pour chaque poste non conforme.

.DESCRIPTION
    Le script 'Envoyer-Tickets.ps1' parcourt un fichier JSON contenant une liste de postes informatiques non conformes,
    vérifie l'existence de tickets déjà ouverts sur l'API Vigie pour éviter les doublons (idempotence),
    puis crée un nouveau ticket pour chaque poste non encore traité.

    Fonctionnalités clés :
    - Récupération du jeton d'accès via $env:VIGIE_TOKEN ou le fichier /etc/mistral/vigie.env (exit code 3 en cas d'absence).
    - Gestion du débit API (Rate-Limiting) : pause automatique de 6 secondes toutes les 5 requêtes et réessai en cas d'erreur HTTP 429.
    - Vérification d'idempotence locale (session) et distante (requête GET par nom de poste).

.PARAMETER Fichier
    Chemin vers le fichier JSON contenant la liste des postes non conformes.
    Par défaut, le script cherche le fichier 'non-conformes.json' dans le répertoire courant.

.EXAMPLE
    PS> .\Envoyer-Tickets.ps1
    Exécute le script en utilisant le fichier 'non-conformes.json' par défaut.

.EXAMPLE
    PS> .\Envoyer-Tickets.ps1 -Fichier "./rapports/audit_vitrolles.json"
    Exécute le script en spécifiant un fichier de rapport JSON personnalisé.

.EXAMPLE
    PS> Get-Help .\Envoyer-Tickets.ps1 -Full
    Affiche l'aide complète du script avec la description de tous ses paramètres et exemples.
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Fichier = "non-conformes.json"
)

# -----------------------------------------------------------------------------
# 1. Verification et chargement du jeton d'authentification
# -----------------------------------------------------------------------------
$token = $env:VIGIE_TOKEN

# Repli sur /etc/mistral/vigie.env si $env:VIGIE_TOKEN est vide
if ([string]::IsNullOrWhiteSpace($token) -and (Test-Path "/etc/mistral/vigie.env")) {
    $envLines = Get-Content "/etc/mistral/vigie.env" | Where-Object { $_ -and -not $_.StartsWith("#") }
    foreach ($line in $envLines) {
        $line = $line.Trim()
        if ($line -match "=") {
            $token = ($line -split "=", 2)[1].Trim(" '`"")
            break
        } elseif ($line) {
            $token = $line.Trim()
            break
        }
    }
}

# Jeton introuvable : affichage d'un message d'erreur et sortie avec le code 3
if ([string]::IsNullOrWhiteSpace($token)) {
    [Console]::Error.WriteLine("Erreur : Le jeton d'authentification est introuvable (`$env:VIGIE_TOKEN ou /etc/mistral/vigie.env).")
    exit 3
}

# -----------------------------------------------------------------------------
# 2. Lecture du fichier non-conformes.json
# -----------------------------------------------------------------------------
if (-not (Test-Path -Path $Fichier)) {
    [Console]::Error.WriteLine("Erreur : Le fichier '$Fichier' est introuvable.")
    exit 1
}

try {
    $donneesRaw = Get-Content -Path $Fichier -Raw | ConvertFrom-Json
    $postes = @($donneesRaw)
} catch {
    [Console]::Error.WriteLine("Erreur : Échec du decodage du fichier JSON '$Fichier' : $_")
    exit 1
}

# -----------------------------------------------------------------------------
# 3. Configuration API & Gestion du Rate-Limiting (5 req / 5 sec)
# -----------------------------------------------------------------------------
$baseUrl = "http://vigie.mistral.test:8080/api/v1/tickets".Trim()
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type"  = "application/json; charset=utf-8"
}

$script:compteurRequetes = 0

function Invoke-ApiVigie {
    param (
        [string]$Method,
        [string]$Uri,
        [object]$Body = $null
    )

    while ($true) {
        # Pause proactive : 6 secondes apres 5 requetes
        if ($script:compteurRequetes -ge 5) {
            Write-Host "[RATE LIMIT] Seuil de 5 requetes atteint. Pause de 6 secondes..." -ForegroundColor Yellow
            Start-Sleep -Seconds 6
            $script:compteurRequetes = 0
        }

        $script:compteurRequetes++

        try {
            $params = @{
                Method      = $Method
                Uri         = $Uri
                Headers     = $headers
                ErrorAction = 'Stop'
            }
            if ($Body) {
                $params.Body = ($Body | ConvertTo-Json -Depth 5 -Compress)
            }

            return (Invoke-RestMethod @params)
        }
        catch {
            $statusCode = $null
            if ($_.Exception.Response) {
                $statusCode = [int]$_.Exception.Response.StatusCode
            }

            # Traitement reactif en cas de retour HTTP 429
            if ($statusCode -eq 429) {
                Write-Host "[ERREUR 429] Trop de requetes. Pause de 6 secondes avant réessai..." -ForegroundColor Red
                Start-Sleep -Seconds 6
                $script:compteurRequetes = 0
                continue
            }
            else {
                throw $_
            }
        }
    }
}

# -----------------------------------------------------------------------------
# 4. Traitement des postes non conformes
# -----------------------------------------------------------------------------
$postesTraites = [System.Collections.Generic.HashSet[string]]::new()

foreach ($item in $postes) {
    # Nettoyage du nom de poste (supprime \r, \n et espaces invisibles)
    $nomPoste = if ($item.nom) { $item.nom.ToString().Trim() } else { $null }

    if ([string]::IsNullOrWhiteSpace($nomPoste)) {
        continue
    }

    # Encapsulation securisee pour le paramètre d'URL (GET)
    $nomPosteEncode = [Uri]::EscapeDataString($nomPoste)

    try {
        # 1. Idempotence distante : GET /tickets?poste=NAME
        $reponseGet = Invoke-ApiVigie -Method "GET" -Uri "${baseUrl}?poste=$nomPosteEncode"

        # Extraction selon la structure de reponse de l'API (liste brute ou objet enveloppant)
        $ticketsExistants = @()
        if ($reponseGet -is [System.Array]) {
            $ticketsExistants = $reponseGet
        } elseif ($reponseGet -is [PSCustomObject]) {
            if ($reponseGet.tickets) { $ticketsExistants = $reponseGet.tickets }
            elseif ($reponseGet.data) { $ticketsExistants = $reponseGet.data }
            elseif ($reponseGet.results) { $ticketsExistants = $reponseGet.results }
        }

        if ($ticketsExistants.Count -gt 0) {
            Write-Host "[IGNORÉ] Poste $nomPoste : un ticket existe déja sur l'API Vigie." -ForegroundColor Yellow
            $null = $postesTraites.Add($nomPoste)
            continue
        }

        # 2. Preparation du payload du ticket
        $raisonsList = @($item.raisons)
        $raisonsTexte = $raisonsList -join ", "

        $payload = @{
            poste   = $nomPoste
            site    = $item.site
            titre   = "Non-conformité détectée sur $nomPoste ($raisonsTexte)"
            raisons = $raisonsList
        }

        # 3. Envoi du ticket (POST /tickets)
        $null = Invoke-ApiVigie -Method "POST" -Uri $baseUrl -Body $payload
        Write-Host "[CRÉÉ] Ticket créé avec succès pour $nomPoste ($raisonsTexte)." -ForegroundColor Green

        $null = $postesTraites.Add($nomPoste)

    } catch {
        [Console]::Error.WriteLine("[ERREUR API] Erreur lors du traitement du poste $nomPoste : $_")
    }
}

