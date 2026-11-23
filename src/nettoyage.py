"""Nettoyage des données brutes Horizon (data/raw -> data/processed).

Lancer depuis la racine du projet :  python src/nettoyage.py
"""
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("data/raw")
PROCESSED = Path("data/processed")


def normaliser_texte(s):
    """Minuscules, sans accents, sans espaces en trop (pour comparer des modalités)."""
    if pd.isna(s):
        return np.nan
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.replace("-", " ")).strip().lower()


def recoder(serie, dictionnaire):
    """Recode une colonne avec un dictionnaire {ancienne écriture normalisée: valeur propre}.
    Une valeur absente du dictionnaire devient manquante (NaN)."""
    return serie.map(normaliser_texte).map(dictionnaire)


def nettoyer_id(serie):
    """Identifiant au format HZ00000 : sans espaces, en majuscules."""
    return serie.str.strip().str.upper()


def en_nombre(serie):
    """Convertit en nombre : virgule -> point, retire les unités (ex. « km »)."""
    propre = (serie.astype("string").str.replace(",", ".", regex=False)
              .str.extract(r"(-?\d+\.?\d*)")[0])
    return pd.to_numeric(propre, errors="coerce")


def nettoyer_etudiants(chemin=RAW / "etudiants.csv"):
    """Nettoie la table etudiants. Retourne (table propre, dictionnaire de comptages)."""
    log = {}
    df = pd.read_csv(chemin, sep=",", dtype=str, encoding="utf-8")
    log["lignes_avant"] = len(df)

    # 1. Noms de colonnes (espaces, majuscules, unités)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={"Distance campus (km)": "distance_campus_km"})

    # 2. Espaces parasites dans toutes les valeurs texte
    df = df.apply(lambda col: col.str.strip())

    # 3. Doublons exacts
    log["doublons_exacts"] = int(df.duplicated().sum())
    df = df.drop_duplicates()

    # 4. Identifiants, puis doublons restants (même étudiant écrit autrement)
    df["id_etudiant"] = nettoyer_id(df["id_etudiant"])
    df["_nb_manquants"] = df.isna().sum(axis=1)
    df = df.sort_values("_nb_manquants", kind="stable")  # la ligne la plus complète d'abord
    log["doublons_id"] = int(df["id_etudiant"].duplicated().sum())
    df = df.drop_duplicates(subset="id_etudiant").drop(columns="_nb_manquants")
    df = df.sort_values("id_etudiant").reset_index(drop=True)

    brut = df.copy()  # copie pour compter les valeurs modifiées

    # 5. Modalités harmonisées
    df["genre"] = recoder(df["genre"], {
        "f": "F", "femme": "F", "feminin": "F",
        "m": "M", "masculin": "M", "homme": "M", "h": "M"})
    df["boursier"] = recoder(df["boursier"], {
        "oui": "Oui", "o": "Oui", "1": "Oui", "yes": "Oui",
        "non": "Non", "n": "Non", "0": "Non", "no": "Non"})
    df["filiere"] = recoder(df["filiere"], {
        "informatique": "Informatique", "info": "Informatique",
        "gestion": "Gestion", "droit": "Droit",
        "communication": "Communication", "com": "Communication",
        "genie civil": "Génie civil", "gc": "Génie civil"})
    df["mention_bac"] = recoder(df["mention_bac"], {
        "passable": "Passable", "p": "Passable",
        "assez bien": "Assez bien", "ab": "Assez bien",
        "bien": "Bien", "b": "Bien",
        "tres bien": "Très bien", "tb": "Très bien"})
    df["region_origine"] = recoder(df["region_origine"], {
        "dakar": "Dakar", "thies": "Thiès", "diourbel": "Diourbel",
        "saint louis": "Saint-Louis", "st louis": "Saint-Louis",
        "ziguinchor": "Ziguinchor", "zig": "Ziguinchor",
        "kedougou": "Kédougou", "sedhiou": "Sédhiou", "fatick": "Fatick",
        "kaffrine": "Kaffrine", "kaolack": "Kaolack", "kolda": "Kolda",
        "louga": "Louga", "matam": "Matam", "tambacounda": "Tambacounda"})

    # 6. Variables numériques : conversion puis valeurs impossibles -> manquant
    df["cohorte"] = pd.to_numeric(df["cohorte"]).astype(int)
    age = en_nombre(df["age"])
    log["age_aberrant"] = int((age.notna() & ~age.between(17, 35)).sum())
    df["age"] = age.where(age.between(17, 35))

    note = en_nombre(df["note_bac"])
    log["note_bac_hors_0_20"] = int((note.notna() & ~note.between(0, 20)).sum())
    df["note_bac"] = note.where(note.between(0, 20))

    dist = en_nombre(df["distance_campus_km"])
    impossible = dist.notna() & ((dist <= 0) | (dist == 9999))
    log["distance_impossible"] = int(impossible.sum())
    df["distance_campus_km"] = dist.where(~impossible)

    # 7. Manquants des variables catégorielles : modalité explicite
    for col, libelle in [("mention_bac", "Inconnue"), ("region_origine", "Inconnue"),
                         ("emploi_parallele", "Inconnu")]:
        log[f"manquants_{col}"] = int(df[col].isna().sum())
        df[col] = df[col].fillna(libelle)

    # 8. Comptage des valeurs modifiées (pour le journal)
    for col in ["genre", "boursier", "filiere", "mention_bac", "region_origine"]:
        log[f"modifies_{col}"] = int((brut[col].fillna("?") != df[col].fillna("?")).sum())

    log["lignes_apres"] = len(df)
    return df, log


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df, log = nettoyer_etudiants()
    df.to_csv(PROCESSED / "etudiants.csv", index=False, encoding="utf-8")
    print("=== etudiants ===")
    for cle, valeur in log.items():
        print(f"{cle:28s} {valeur}")


if __name__ == "__main__":
    main()
