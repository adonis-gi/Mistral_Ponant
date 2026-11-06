<#
.SYNOPSIS
    Identifie les postes informatiques orphelins et génère un rapport CSV.[cite: 2]

.DESCRIPTION
    Le script croise l'inventaire des postes informatiques (au format JSON) avec le référentiel des comptes utilisateurs (au format CSV).
    Il identifie les machines rattachées à un utilisateur inconnu ou dont le compte est inactif, puis exporte le résultat trié dans un fichier CSV.[cite: 2]

.PARAMETER FichierPostes
    Chemin vers le fichier JSON contenant la liste des postes du parc informatique.[cite: 2]
    Valeur par défaut : "/srv/mistral/parc/postes.json".[cite: 2]

.PARAMETER FichierUtilisateurs
    Chemin vers le fichier CSV contenant les comptes utilisateurs et leur statut (séparateur ';').[cite: 2]
    Valeur par défaut : "/srv/mistral/parc/utilisateurs.csv".[cite: 2]

.PARAMETER Sortie
    Chemin du fichier CSV de sortie contenant la liste des postes orphelins identifiés.[cite: 2]
    Valeur par défaut : "/tmp/postes-orphelins.csv".[cite: 2]

.EXAMPLE
    PS> .\Detecter-Orphelins.ps1
    Exécute le script en utilisant les fichiers et le chemin de sortie par défaut.[cite: 2]

.EXAMPLE
    PS> .\Detecter-Orphelins.ps1 -FichierPostes "./audit/postes.json" -Sortie "./rapport_orphelins.csv"
    Exécute le script en spécifiant un fichier JSON personnalisé et un fichier de sortie spécifique.[cite: 2]
#>

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
