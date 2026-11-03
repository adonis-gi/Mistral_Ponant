import pytest
from comptes import (
    generer_login,
    normaliser_chaine,
    traiter_ligne,
    normaliser_date,
)


def test_normaliser_chaine():
    assert normaliser_chaine("Hélène") == "helene"
    assert normaliser_chaine("O'Neil") == "oneil"
    assert normaliser_chaine("Ben Salah") == "bensalah"
    assert normaliser_chaine("François") == "francois"
    assert normaliser_chaine("  Thierry  ") == "thierry"
    assert normaliser_chaine("Le-Marchand") == "lemarchand"


def test_normaliser_date_valide():
    assert normaliser_date("07/12/2026") == "2026-12-07"
    assert normaliser_date("2026-11-17") == "2026-11-17"
    assert normaliser_date("05-11-2026") == "2026-11-05"


def test_normaliser_date_invalide():
    # Date inexistante (31 février)
    with pytest.raises(ValueError, match="date invalide"):
        normaliser_date("31/02/2026")

    # Date vide
    with pytest.raises(ValueError, match="date invalide"):
        normaliser_date("  ")


def test_generer_login_doublons():
    compteur = {}

    # Premier passage -> mathis.girard
    l1 = generer_login("Mathis", "Girard", compteur)
    assert l1 == "mathis.girard"

    # Deuxième passage -> mathis.girard2
    l2 = generer_login("Mathis", "Girard", compteur)
    assert l2 == "mathis.girard2"

    # Troisième passage -> mathis.girard3
    l3 = generer_login("Mathis", "Girard", compteur)
    assert l3 == "mathis.girard3"


def test_traiter_ligne_valide():
    compteur = {}
    lignes_acceptees = set()
    row = {
        "nom": "  Guérin ",
        "prenom": "Hélène ",
        "date_arrivee": "13/11/2026",
        "site": "Nice",
        "email_perso": "helgue75@exemple.test",
    }
    compte, rejet = traiter_ligne(
        row,
        num_ligne=2,
        compteur_logins=compteur,
        lignes_acceptees=lignes_acceptees,
        domaine="mistral.test",
    )

    assert rejet is None
    assert compte["login"] == "helene.guerin"
    assert compte["email"] == "helene.guerin@mistral.test"
    assert compte["nom"] == "Guérin"
    assert compte["date_arrivee"] == "2026-11-13"


def test_traiter_ligne_rejets_dans_lordre():
    compteur = {}
    lignes_acceptees = set()

    # 1. Nom manquant
    row_nom_vide = {"nom": "", "prenom": "Théo", "date_arrivee": "07/12/2026"}
    compte, rejet = traiter_ligne(
        row_nom_vide, 2, compteur, lignes_acceptees, "mistral.test"
    )
    assert compte is None
    assert rejet == {"ligne": 2, "raison": "nom manquant"}

    # 2. Prénom manquant
    row_prenom_vide = {
        "nom": "Leroy",
        "prenom": "  ",
        "date_arrivee": "07/12/2026",
    }
    compte, rejet = traiter_ligne(
        row_prenom_vide, 3, compteur, lignes_acceptees, "mistral.test"
    )
    assert compte is None
    assert rejet == {"ligne": 3, "raison": "prenom manquant"}

    # 3. Date invalide
    row_date_inv = {
        "nom": "Rossi",
        "prenom": "Lucas",
        "date_arrivee": "31/02/2026",
    }
    compte, rejet = traiter_ligne(
        row_date_inv, 4, compteur, lignes_acceptees, "mistral.test"
    )
    assert compte is None
    assert rejet == {"ligne": 4, "raison": "date invalide"}


def test_traiter_ligne_rejet_doublon():
    compteur = {}
    lignes_acceptees = set()
    row1 = {
        "nom": "Girard",
        "prenom": "Rayan",
        "email_perso": "raygir14@exemple.test",
        "date_arrivee": "04/12/2026",
    }
    row2 = {
        "nom": "GIRARD",
        "prenom": "rayan",
        "email_perso": "RAYGIR14@exemple.test",
        "date_arrivee": "04/12/2026",
    }

    # Premier passage -> Valide
    compte1, rejet1 = traiter_ligne(
        row1, 2, compteur, lignes_acceptees, "mistral.test"
    )
    assert rejet1 is None
    assert compte1["login"] == "rayan.girard"

    # Deuxième passage identique (insensible à la casse) -> Rejet doublon
    compte2, rejet2 = traiter_ligne(
        row2, 10, compteur, lignes_acceptees, "mistral.test"
    )
    assert compte2 is None
    assert rejet2 == {"ligne": 10, "raison": "doublon"}
