# P10 — Défi : les postes orphelins

## 1. Objectif

Identifier les postes Windows dont l'utilisateur est absent
de l'annuaire ou dont le compte est inactif.

## 2. Sources analysées

- `/srv/mistral/parc/postes.json` : inventaire de 60 postes.
- `/srv/mistral/parc/utilisateurs.csv` : annuaire des utilisateurs.

## 3. Méthode de rapprochement

Les deux fichiers utilisent des formats différents :

- Inventaire : `prenom.nom`
- Annuaire : `Nom Prénom`

Nous normalisons les noms :
1. Conversion en minuscules.
2. Suppression des accents.
3. Transformation de `Nom Prénom` en `prenom.nom`.
4. Comparaison exacte des noms normalisés.

Exemple :
`Lefèvre Anaïs` devient `anais.lefevre`.

Un poste est signalé si :
- Aucun compte ne correspond : `Inconnu`.
- Le compte correspondant est désactivé : `Inactif`.

Les correspondances multiples sont signalées comme ambiguës
et doivent être vérifiées manuellement.

## 4. Résultats

| État | Nombre |
|---|---:|
| Propriétaire inconnu | 55 |
| Propriétaire inactif | 3 |
| Propriétaire actif | 2 |
| Total | 60 |

58 postes sur 60 sont potentiellement orphelins.

## 5. Livrables

- `outils/Postes-Orphelins.ps1`
- `postes-orphelins.csv`

## 6. Limites et conclusion

La méthode dépend de la cohérence des noms entre les deux
sources. Les noms composés, homonymes ou changements de nom
peuvent produire des faux positifs.

Les 58 postes signalés nécessitent donc une vérification
avant toute désactivation ou intervention.

Ce défi montre l'intérêt de croiser un inventaire informatique
avec un annuaire pour détecter des risques de sécurité.
