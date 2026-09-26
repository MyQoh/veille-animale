"""Outils communs aux scripts : dossiers de sortie, date de référence, affichage.

Rien ici ne touche à la logique des carnets de référence. Ce fichier ne sert qu'à
ranger les fichiers et à rendre une exécution reproductible.
"""
import os
import sys
from datetime import datetime

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


def dossier_sortie(brique):
    """Nouveau dossier sorties/AAAA-MM-JJ_HHhMM_<brique>/, un par exécution ; jamais d'écrasement :
    si le dossier existe déjà (deux exécutions dans la même minute), on ajoute _2, _3..."""
    base = f"{datetime.now():%Y-%m-%d_%Hh%M}_{brique}"
    n = 1
    while True:
        chemin = os.path.join(SORTIES, base if n == 1 else f"{base}_{n}")
        if not os.path.exists(chemin):
            os.makedirs(chemin)
            return chemin
        n += 1


def date_reference(texte):
    """« Aujourd'hui » des carnets. Par défaut la date du jour ; on peut la fixer
    (par exemple 2026-09-25) pour comparer avec une exécution passée."""
    return pd.Timestamp(texte).normalize() if texte else pd.Timestamp.today().normalize()
