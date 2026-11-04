<#
.SYNOPSIS
    Audite le parc Windows : liste les postes non conformes et la raison de chacun.

.DESCRIPTION
    Lit l'inventaire JSON des postes et écrit, dans le dossier de sortie, non-conformes.csv
    (nom;site;raisons, raisons jointes par |) et non-conformes.json (raisons en liste), triés par nom.
    Raisons, dans cet ordre : build, defender, disque, maj.

.EXAMPLE
    pwsh -File outils/Audit-Parc.ps1 -Fichier /srv/mistral/parc/postes.json -Sortie /tmp/audit

.EXAMPLE
    pwsh -File outils/Audit-Parc.ps1 -Fichier /srv/mistral/parc/postes.json -Sortie /tmp/audit -Date 2026-11-05 -Seuil 80
#>
param(
    [Parameter(Mandatory)] [string] $Fichier,    # inventaire des postes (postes.json)
    [Parameter(Mandatory)] [string] $Sortie,     # dossier où écrire les rapports
    [int] $Seuil = 90,                           # disque non conforme strictement au-dessus de ce pourcentage
    [int] $JoursMaj = 30,                        # dernière mise à jour il y a plus de ce nombre de jours
    [int] $BuildMin = 19045,                     # build Windows minimal (Windows 10 22H2)
    [datetime] $Date = (Get-Date).Date           # date de l'audit, pour le rejouer à une date donnée
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
$csv  = Join-Path $Sortie 'non-conformes.csv'
$json = Join-Path $Sortie 'non-conformes.json'

# CSV : une liste ne s'écrit pas telle quelle (Export-Csv écrirait « System.String[] »),
# on joint donc les raisons par | dans une propriété calculée
$lignes = $nonConformes | Select-Object nom, site, @{ n = 'raisons'; e = { $_.raisons -join '|' } }
if ($lignes) {
    $lignes | Export-Csv -Path $csv -Delimiter ';' -NoTypeInformation -Encoding utf8
} else {
    Set-Content -Path $csv -Value '"nom";"site";"raisons"' -Encoding utf8
}

# JSON : -InputObject @(...) garde les crochets même avec un seul poste, raisons reste une liste
ConvertTo-Json -InputObject @($nonConformes) -Depth 3 | Set-Content -Path $json -Encoding utf8

Write-Output ("{0} postes audités, {1} non conformes au {2:yyyy-MM-dd} : {3} et {4}" -f `
    @($postes).Count, $nonConformes.Count, $Date, $csv, $json)
