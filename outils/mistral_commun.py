"""Fonctions partagées par les outils Python de la guilde Ponant."""
import argparse
import datetime
import os
import re
import sys
import unicodedata

# Dossier racine du dépôt (celui qui contient outils/ et rapports/)
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ParseurArguments(argparse.ArgumentParser):
    """Parseur argparse qui affiche l'aide complète sur stderr en cas d'erreur d'arguments (code 2)."""

    def error(self, message):
        sys.stderr.write(f"Erreur d'utilisation : {message}\n\n")
        self.print_help(sys.stderr)
        sys.exit(2)


def normaliser(texte):
    """Minuscules, sans accents, en ne gardant que les lettres de a à z et le tiret."""
    if not texte:
        return ""
    texte_nfkd = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in texte_nfkd if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z-]", "", sans_accents.lower().strip())


def classer(compteur):
    """Transforme un Counter en liste [cle, nombre], du plus grand au plus petit, puis par ordre alphabétique."""
    return [[cle, nombre] for cle, nombre in sorted(compteur.items(), key=lambda kv: (-kv[1], kv[0]))]


def ecrire_rapport(prefixe, contenu, extension="txt"):
    """Enregistre le contenu dans rapports/PREFIXE-AAAA-MM-JJ-HH-MM-SS.EXT et renvoie le chemin du fichier."""
    dossier = os.path.join(RACINE, "rapports")
    os.makedirs(dossier, exist_ok=True)
    horodatage = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    chemin = os.path.join(dossier, f"{prefixe}-{horodatage}.{extension}")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu + "\n")
    return chemin
