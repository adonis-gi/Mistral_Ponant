<#
.SYNOPSIS
    Identifie les comptes dormants de Mistral Logistique.

.DESCRIPTION
    Filtre les comptes humains actifs de l'annuaire et garde ceux dont la dernière connexion
    date de -Jours jours ou plus à la -Date. Écrit un CSV Login;Service;JoursInactif, du compte
    le plus ancien au plus récent, puis par ordre alphabétique de login.

.EXAMPLE
    pwsh -File outils/Get-ComptesDormants.ps1 -Fichier /srv/mistral/parc/utilisateurs.csv -Sortie /tmp/dormants.csv

.EXAMPLE
    pwsh -File outils/Get-ComptesDormants.ps1 -Fichier /srv/mistral/parc/utilisateurs.csv -Sortie /tmp/dormants.csv -Jours 60 -Date 2026-11-05
#>
param(
    [Parameter(Mandatory)][string]$Fichier,     # annuaire : Login;NomComplet;Service;DernierLogon;Type;Actif
    [Parameter(Mandatory)][string]$Sortie,      # fichier CSV à écrire
    [int]$Jours = 90,                           # dormant à partir de ce nombre de jours sans connexion
    [string]$Date = (Get-Date).ToString('yyyy-MM-dd')   # date de référence, pour rejouer l'audit
)
$ErrorActionPreference = 'Stop'
$refDate = [datetime]$Date
$utilisateurs = Import-Csv -Path $Fichier -Delimiter ';'
$liste = [System.Collections.Generic.List[PSCustomObject]]::new()

foreach ($u in $utilisateurs) {
    # Périmètre : comptes humains et actifs (ni svc-..., ni comptes désactivés)
    $actif = "$($u.Actif)" -match '^(true|1|oui)$'
    $isService = "$($u.Login)" -like 'svc-*' -or "$($u.Type)" -match 'service'

    if ($actif -and -not $isService -and $u.DernierLogon) {
        # La colonne de l'annuaire s'appelle DernierLogon
        $inactivite = ($refDate - [datetime]$u.DernierLogon).Days
        if ($inactivite -ge $Jours) {
            $liste.Add([pscustomobject]@{
                Login        = $u.Login
                Service      = $u.Service
                JoursInactif = $inactivite
            })
        }
    }
}

# Du plus ancien au plus récent, puis par ordre alphabétique de login
$tries = $liste | Sort-Object @{Expression = 'JoursInactif'; Descending = $true}, @{Expression = 'Login'; Ascending = $true}

# CSV écrit à la main : en-tête exact, séparateur ;, sans guillemets
$csvLines = @("Login;Service;JoursInactif")
foreach ($item in $tries) {
    $csvLines += "$($item.Login);$($item.Service);$($item.JoursInactif)"
}
$csvLines | Set-Content -Path $Sortie -Encoding utf8

Write-Output ("{0} comptes dormants ({1} jours ou plus au {2:yyyy-MM-dd}) écrits dans {3}" -f $liste.Count, $Jours, $refDate, $Sortie)
