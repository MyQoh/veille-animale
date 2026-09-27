"""Régénère scripts/regles_themes.py à partir de la cellule 2 de la brique 1 (copie exacte, sans retouche)."""
import os

ICI = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(ICI, "brique1_questions_ecrites.py"), encoding="utf-8").read()
debut = src.index("# Cellule 2. Règles de classement")
fin = src.index("# ---------------------------------------------------------------------------\n# Cellule 3.")
entete = '''"""Règles de thèmes de la brique 1 (version 14), extraites automatiquement de scripts/brique1_questions_ecrites.py.

Ne pas modifier ici : ce fichier est une copie exacte de la cellule 2 de la brique 1, pour que les autres briques
classent avec exactement les mêmes règles. Pour le régénérer : python scripts/extraire_regles_themes.py
"""
import re, unicodedata

'''
with open(os.path.join(ICI, "regles_themes.py"), "w", encoding="utf-8") as f:
    f.write(entete + src[debut:fin])
print("regles_themes.py régénéré")
