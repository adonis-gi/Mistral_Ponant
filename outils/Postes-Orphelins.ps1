param(
    [string]$FichierPostes = "/srv/mistral/parc/postes.json",
    [string]$FichierUtilisateurs = "/srv/mistral/parc/utilisateurs.csv",
    [string]$Sortie = "/tmp/postes-orphelins.csv"
)

$ErrorActionPreference = 'Stop'

# Normaliser un nom : minuscules et suppression des accents
function Normaliser-Texte {
    param([string]$Texte)

    if ([string]::IsNullOrWhiteSpace($Texte)) {
        return ""
    }

    $decompose = $Texte.Normalize(
        [System.Text.NormalizationForm]::FormD
    )

    return ($decompose -replace "\p{Mn}", "").Trim().ToLowerInvariant()
}

# Charger les deux fichiers
$comptes = @(Import-Csv $FichierUtilisateurs -Delimiter ";")
$postes = @(Get-Content -Raw $FichierPostes | ConvertFrom-Json)

# Identifier les postes orphelins
$orphelins = foreach ($poste in $postes) {

    $clePoste = Normaliser-Texte $poste.utilisateur

    $trouves = @($comptes | Where-Object {
        $parties = $_.NomComplet.Trim() -split "\s+", 2

        if ($parties.Count -eq 2) {
            $cleCompte = Normaliser-Texte "$($parties[1]).$($parties[0])"
            $cleCompte -eq $clePoste
        }
    })

    if ($trouves.Count -eq 0) {
        $motif = "Inconnu"
    }
    elseif ($trouves.Count -gt 1) {
        Write-Warning "Correspondance ambiguë : $($poste.utilisateur)"
        continue
    }
    elseif ($trouves[0].Actif -ne "Oui") {
        $motif = "Inactif"
    }
    else {
        continue
    }

    [pscustomobject]@{
        Poste = $poste.nom
        Site = $poste.site
        Utilisateur = $poste.utilisateur
        Motif = $motif
    }
}

# Générer le rapport CSV
@($orphelins) |
    Sort-Object Poste |
    Export-Csv -Path $Sortie -Delimiter ";" -NoTypeInformation -Encoding utf8

Write-Host "Rapport créé : $Sortie"
Write-Host "Postes orphelins : $(@($orphelins).Count)"
