"""Tableau « avant / après » du nettoyage (lignes, valeurs manquantes, doublons).

Lancer depuis la racine du projet :  python src/avant_apres.py
Écrit docs/tableau_avant_apres.md
"""
from pathlib import Path

import pandas as pd

RAW = Path("data/raw")
PROCESSED = Path("data/processed")
FICHIERS = {  # nom de table : (fichier brut, séparateur brut, fichier propre)
    "etudiants": ("etudiants.csv", ",", "etudiants.csv"),
    "inscriptions": ("inscriptions.csv", ";", "inscriptions.csv"),
    "activite_hebdo": ("activite_hebdo.csv", ",", "activite_hebdo.csv"),
    "tutorat": ("tutorat.csv", ",", "tutorat.csv"),
    "messages": ("messages.csv", ",", "messages.csv"),
}


def compter(df):
    """Lignes, valeurs manquantes et doublons exacts d'une table."""
    return len(df), int(df.isna().sum().sum()), int(df.duplicated().sum())


def main():
    lignes = ["| Table | Lignes avant | Lignes après | Manquants avant | Manquants après "
              "| Doublons avant | Doublons après |", "|---|---|---|---|---|---|---|"]
    for nom, (brut, sep, propre) in FICHIERS.items():
        avant = compter(pd.read_csv(RAW / brut, sep=sep, dtype=str))
        apres = compter(pd.read_csv(PROCESSED / propre))
        lignes.append(f"| {nom} | {avant[0]:,} | {apres[0]:,} | {avant[1]:,} | {apres[1]:,} "
                      f"| {avant[2]:,} | {apres[2]:,} |".replace(",", " "))
    texte = "\n".join(lignes)
    Path("docs").mkdir(exist_ok=True)
    Path("docs/tableau_avant_apres.md").write_text(texte + "\n", encoding="utf-8")
    print(texte)


if __name__ == "__main__":
    main()
