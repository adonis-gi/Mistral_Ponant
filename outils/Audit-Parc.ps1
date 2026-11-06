<#
.SYNOPSIS
    Audite le parc Windows : liste les postes non conformes et la raison de chacun.

.DESCRIPTION
    Lit l'inventaire JSON des postes et écrit, dans le dossier de sortie, non-conformes.csv
    (nom;site;raisons, raisons jointes par |) et non-conformes.json (raisons en liste), triés par nom.
    Si l'interrupteur -Html est spécifié, génère également un fichier non-conformes.html avec un tableau par site.
    Affiche un résumé par site du nombre de postes non conformes, trié du pire au meilleur.
    Raisons, dans cet ordre : build, defender, disque, maj.

.PARAMETER Fichier
    Inventaire JSON des postes (ex: /srv/mistral/parc/postes.json).
    Doit être un chemin de fichier valide et existant.

.PARAMETER Sortie
    Dossier où écrire les fichiers de rapport générés.

.PARAMETER Seuil
    Disque non conforme strictement au-dessus de ce pourcentage d'occupation (par défaut : 90, plage autorisée : 50 à 100).

.PARAMETER JoursMaj
    Dernière mise à jour il y a plus de ce nombre de jours (par défaut : 30).

.PARAMETER BuildMin
    Build Windows minimal requis (par défaut : 19045 pour Windows 10 22H2).

.PARAMETER Date
    Date de l'audit, pour rejouer l'évaluation à une date donnée (par défaut : date du jour).

.PARAMETER Html
    Si présent, génère un rapport HTML 'non-conformes.html' contenant un tableau par site.

.EXAMPLE
    pwsh -File outils/Audit-Parc.ps1 -Fichier /srv/mistral/parc/postes.json -Sortie /tmp/audit

.EXAMPLE
    pwsh -File outils/Audit-Parc.ps1 -Fichier /srv/mistral/parc/postes.json -Sortie /tmp/audit -Date 2026-11-05 -Seuil 80 -Html
#>
param(
    [Parameter(Mandatory)]
    [ValidateScript({ 
        if (-not (Test-Path $_)) { 
            throw "Le fichier spécifié '$($_)' est introuvable." 
        } 
        $true 
    })]
    [string] $Fichier,    # inventaire des postes (postes.json)

    [Parameter(Mandatory)]
    [string] $Sortie,     # dossier où écrire les rapports

    [ValidateRange(50, 100)]
    [ValidateScript({ 
        if ($_ -lt 50 -or $_ -gt 100) { 
            throw "Le seuil de disque doit être compris entre 50 et 100 % (valeur fournie : $_)." 
        } 
        $true 
    })]
    [int] $Seuil = 90,                           # disque non conforme strictement au-dessus de ce pourcentage

    [int] $JoursMaj = 30,                        # dernière mise à jour il y a plus de ce nombre de jours
    [int] $BuildMin = 19045,                     # build Windows minimal (Windows 10 22H2)
    [datetime] $Date = (Get-Date).Date,          # date de l'audit, pour le rejouer à une date donnée
    [switch] $Html                               # option pour générer non-conformes.html
)

$ErrorActionPreference = 'Stop'   # la première erreur arrête tout, comme set -e en Bash

$postes = Get-Content -Raw -Path $Fichier | ConvertFrom-Json

$nonConformes = foreach ($p in $postes) {
    # Les raisons sont ajoutées dans l'ordre imposé : build, defender, disque, maj
    $raisons = [System.Collections.Generic.List[string]]::new()
    if ([int]$p.build -lt $BuildMin)      { $raisons.Add('build') }
    if (-not $p.defender)                 { $raisons.Add('defender') }
    if ([int]$p.disque_pct -gt $Seuil)    { $raisons.Add('disque') }
    $jours = ($Date.Date - ([datetime]$p.derniere_maj).Date).Days
    if ($jours -gt $JoursMaj)             { $raisons.Add('maj') }

    if ($raisons.Count -gt 0) {
        [pscustomobject]@{
            nom     = [string]$p.nom
            site    = [string]$p.site
            raisons = [string[]]$raisons
        }
    }
}
$nonConformes = @($nonConformes | Sort-Object nom)

New-Item -ItemType Directory -Path $Sortie -Force | Out-Null
$csv         = Join-Path $Sortie 'non-conformes.csv'
$json        = Join-Path $Sortie 'non-conformes.json'
$fichierHtml = Join-Path $Sortie 'non-conformes.html'

# CSV : les raisons sont jointes par | dans une propriété calculée
$lignes = $nonConformes | Select-Object nom, site, @{ n = 'raisons'; e = { $_.raisons -join '|' } }
if ($lignes) {
    $lignes | Export-Csv -Path $csv -Delimiter ';' -NoTypeInformation -Encoding utf8
} else {
    Set-Content -Path $csv -Value '"nom";"site";"raisons"' -Encoding utf8
}

# JSON
ConvertTo-Json -InputObject @($nonConformes) -Depth 3 | Set-Content -Path $json -Encoding utf8

# HTML : génère un tableau par site si l'option -Html est activée
if ($Html) {
    $groupesHtml = $nonConformes | Group-Object site | Sort-Object Count -Descending
    $corpsHtml = foreach ($g in $groupesHtml) {
        $tableHtml = $g.Group | Select-Object nom, site, @{ n = 'raisons'; e = { $_.raisons -join '|' } } | ConvertTo-Html -Fragment
        "<h2>Site : $($g.Name) ($($g.Count) non conformes)</h2>`n$tableHtml"
    }

    $headCss = "<style>body{font-family:Arial,sans-serif;} table{border-collapse:collapse;width:100%;margin-bottom:20px;} th,td{border:1px solid #ddd;padding:8px;text-align:left;} th{background-color:#f2f2f2;}</style>"
    ConvertTo-Html -Title "Rapport de non-conformité par site" -Head $headCss -Body ($corpsHtml -join "`n") | Set-Content -Path $fichierHtml -Encoding utf8
}

# Résumé par site (du pire au meilleur)
$resumeParSite = $nonConformes | Group-Object site | Sort-Object Count -Descending | Select-Object @{ n = 'Site'; e = { $_.Name } }, @{ n = 'NonConformes'; e = { $_.Count } }
$resumeParSite | Format-Table -AutoSize

Write-Output ("{0} postes audités, {1} non conformes au {2:yyyy-MM-dd} : {3} et {4}" -f `
    @($postes).Count, $nonConformes.Count, $Date, $csv, $json)
