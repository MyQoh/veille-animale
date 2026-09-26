"""Compare une sortie de script à une sortie de référence (par exemple celle de Colab), ligne par ligne.

Usage :
    python scripts/comparer.py REFERENCE.csv NOUVEAU.csv --cle uid [--filtre legislature=17]

Affiche : lignes présentes d'un seul côté, puis pour chaque colonne le nombre de valeurs
différentes, avec quelques exemples. Les valeurs sont comparées telles qu'écrites dans les CSV.
"""
import argparse

import pandas as pd

from commun import console_utf8

console_utf8()
p = argparse.ArgumentParser()
p.add_argument("reference")
p.add_argument("nouveau")
p.add_argument("--cle", nargs="+", required=True, help="colonne(s) identifiant une ligne")
p.add_argument("--filtre", nargs="*", default=[], help="colonne=valeur, appliqué aux deux fichiers")
p.add_argument("--exemples", type=int, default=5)
a = p.parse_args()


def lire(chemin):
    t = pd.read_csv(chemin, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    for f in a.filtre:
        col, val = f.split("=", 1)
        t = t[t[col] == val]
    return t


ref, nouv = lire(a.reference), lire(a.nouveau)
print(f"Référence : {len(ref)} lignes ; nouveau : {len(nouv)} lignes")
for nom, t in (("référence", ref), ("nouveau", nouv)):
    d = t.duplicated(a.cle).sum()
    if d:
        print(f"  attention : {d} clés en double dans {nom}")

cles_ref = set(map(tuple, ref[a.cle].values))
cles_nouv = set(map(tuple, nouv[a.cle].values))
seul_ref, seul_nouv = sorted(cles_ref - cles_nouv), sorted(cles_nouv - cles_ref)
print(f"Lignes seulement dans la référence : {len(seul_ref)}  {seul_ref[:a.exemples]}")
print(f"Lignes seulement dans le nouveau : {len(seul_nouv)}  {seul_nouv[:a.exemples]}")

colonnes_ref, colonnes_nouv = list(ref.columns), list(nouv.columns)
if colonnes_ref != colonnes_nouv:
    print("Colonnes différentes :", set(colonnes_ref) ^ set(colonnes_nouv) or "même ensemble, ordre différent")

m = ref.merge(nouv, on=a.cle, suffixes=("__ref", "__nouv"))
print(f"Lignes communes comparées : {len(m)}\n")
ecarts = 0
for c in colonnes_ref:
    if c in a.cle or c not in colonnes_nouv:
        continue
    diff = m[m[c + "__ref"] != m[c + "__nouv"]]
    if len(diff):
        ecarts += 1
        print(f"- {c} : {len(diff)} valeurs différentes")
        for _, l in diff.head(a.exemples).iterrows():
            cle = " / ".join(l[k] for k in a.cle)
            print(f"    {cle} : référence « {l[c + '__ref'][:120]} » ; nouveau « {l[c + '__nouv'][:120]} »")
print("Aucune différence sur les lignes communes." if not ecarts else f"\n{ecarts} colonnes avec des différences.")
