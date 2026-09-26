"""Outils communs aux scripts : dossiers de sortie, date de référence, affichage.

Rien ici ne touche à la logique des carnets de référence. Ce fichier ne sert qu'à
ranger les fichiers et à rendre une exécution reproductible.
"""
import os
import sys
from datetime import date

import pandas as pd

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DONNEES_BRUTES = os.path.join(RACINE, "donnees_brutes")
SORTIES = os.path.join(RACINE, "sorties")


def console_utf8():
    """La console Windows n'affiche pas les accents sans cela."""
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


def dossier_sortie(brique, jour=None):
    """Nouveau dossier sorties/AAAA-MM-JJ/<brique>/ ; jamais d'écrasement :
    si le dossier existe déjà, on crée AAAA-MM-JJ_2, _3..."""
    jour = jour or date.today().isoformat()
    n = 1
    while True:
        nom = jour if n == 1 else f"{jour}_{n}"
        chemin = os.path.join(SORTIES, nom, brique)
        if not os.path.exists(chemin):
            os.makedirs(chemin)
            return chemin
        n += 1


def date_reference(texte):
    """« Aujourd'hui » des carnets. Par défaut la date du jour ; on peut la fixer
    (par exemple 2026-09-25) pour comparer avec une exécution passée."""
    return pd.Timestamp(texte).normalize() if texte else pd.Timestamp.today().normalize()
