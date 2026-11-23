"""Nettoyage des données brutes Horizon (data/raw -> data/processed).

Lancer depuis la racine du projet :  python src/nettoyage.py
"""
import re
import unicodedata
from datetime import datetime
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


MOIS = {"janv": 1, "janvier": 1, "fevr": 2, "fevrier": 2, "mars": 3, "avr": 4,
        "avril": 4, "mai": 5, "juin": 6, "juil": 7, "juillet": 7, "aout": 8,
        "sept": 9, "oct": 10, "nov": 11, "dec": 12}
RENTREE = {"2024-2025": pd.Timestamp("2024-10-07"),
           "2025-2026": pd.Timestamp("2025-10-06")}


def parser_date(texte):
    """Convertit une date écrite de plusieurs façons en date unique.
    Formats rencontrés : 2025-10-06, 2025/10/06, 06/10/2025, 6 oct. 2025."""
    if pd.isna(texte):
        return pd.NaT
    texte = texte.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return pd.Timestamp(datetime.strptime(texte, fmt))
        except ValueError:
            pass
    m = re.match(r"^(\d{1,2})\s+([^\W\d_]+)\.?\s+(\d{4})$", texte)
    if m and normaliser_texte(m.group(2)) in MOIS:
        return pd.Timestamp(int(m.group(3)), MOIS[normaliser_texte(m.group(2))], int(m.group(1)))
    return pd.NaT


def nettoyer_inscriptions(ids_etudiants, chemin=RAW / "inscriptions.csv"):
    """Nettoie la table inscriptions. `ids_etudiants` : identifiants de la table etudiants propre."""
    log = {}
    df = pd.read_csv(chemin, sep=";", dtype=str, encoding="utf-8")   # séparateur « ; »
    log["lignes_avant"] = len(df)
    df.columns = [c.strip() for c in df.columns]
    df = df.apply(lambda col: col.str.strip())

    log["doublons_exacts"] = int(df.duplicated().sum())
    df = df.drop_duplicates()
    df["id_etudiant"] = nettoyer_id(df["id_etudiant"])

    # Identifiants qui n'existent pas dans etudiants : incohérence entre tables
    inconnus = ~df["id_etudiant"].isin(ids_etudiants)
    log["ids_hors_etudiants"] = int(inconnus.sum())
    df = df[~inconnus]

    # Dates : un seul format
    df["date_debut"] = df["date_debut"].map(parser_date)
    df["date_fin"] = df["date_fin"].map(parser_date)

    # Date de début : doit être la rentrée de l'année universitaire
    rentree = df["annee_universitaire"].map(RENTREE)
    hors_rentree = df["date_debut"] != rentree
    log["date_debut_hors_rentree"] = int(hors_rentree.sum())
    df["date_debut"] = rentree

    # Statut : 3 modalités
    df["statut_final"] = recoder(df["statut_final"], {
        "inscrit": "inscrit", "abandon": "abandon", "abandonne": "abandon",
        "transfert": "transfert", "transfere": "transfert"})
    # Statut manquant : sans date de fin, l'étudiant est considéré inscrit (à signaler)
    manquant = df["statut_final"].isna() & df["date_fin"].isna()
    log["statut_manquant_deduit_inscrit"] = int(manquant.sum())
    df["statut_deduit"] = manquant
    df.loc[manquant, "statut_final"] = "inscrit"
    log["statut_manquant_non_resolu"] = int(df["statut_final"].isna().sum())

    # Contrôles de cohérence (on compte, on ne modifie pas)
    log["date_fin_avant_debut"] = int((df["date_fin"] < df["date_debut"]).sum())
    # Date de fin au-delà de la semaine 30 (ex. en 2027) : impossible -> manquante.
    # La semaine de l'abandon sera alors retrouvée avec l'activité (règle des 4 semaines).
    trop_tard = df["date_fin"] > df["date_debut"] + pd.Timedelta(weeks=30)
    log["date_fin_apres_semaine_30"] = int(trop_tard.sum())
    df.loc[trop_tard, "date_fin"] = pd.NaT
    log["abandon_ou_transfert_sans_date_fin"] = int(
        (df["statut_final"].isin(["abandon", "transfert"]) & df["date_fin"].isna()).sum())
    log["inscrit_avec_date_fin"] = int(((df["statut_final"] == "inscrit") & df["date_fin"].notna()).sum())

    df = df.sort_values("id_etudiant").reset_index(drop=True)
    log["lignes_apres"] = len(df)
    return df, log


RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
RE_TEL = re.compile(r"(?<!\d)(?:\+?221[ .]?)?7\d[ .]?\d{3}[ .]?\d{2}[ .]?\d{2}(?!\d)")
# Un nom = au moins deux mots commençant par une majuscule, après « Je suis » ou « c'est »
MOT = r"[A-ZÀ-Ý][\w'-]+"
RE_NOM = re.compile(rf"(?<=Je suis ){MOT}(?: {MOT})+|(?<=c'est ){MOT}(?: {MOT})+")


def reparer_encodage(texte):
    """Répare le texte mal décodé (« dÃ©couragÃ© » -> « découragé »)."""
    if "Ã" in texte or "Â" in texte:
        try:
            return texte.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            try:
                return texte.encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                return texte
    return texte


def nettoyer_messages(ids_etudiants, chemin=RAW / "messages.csv"):
    """Nettoie messages et masque les données personnelles (pseudonymisation)."""
    log = {}
    df = pd.read_csv(chemin, sep=",", dtype=str, encoding="utf-8")
    log["lignes_avant"] = len(df)
    df.columns = [c.strip() for c in df.columns]
    df = df.apply(lambda col: col.str.strip())

    log["doublons_exacts"] = int(df.duplicated().sum())
    df = df.drop_duplicates()
    df["id_etudiant"] = nettoyer_id(df["id_etudiant"])
    inconnus = ~df["id_etudiant"].isin(ids_etudiants)
    log["ids_hors_etudiants"] = int(inconnus.sum())
    df = df[~inconnus].copy()
    df["semaine"] = en_nombre(df["semaine"]).astype(int)
    log["semaine_hors_1_30"] = int((~df["semaine"].between(1, 30)).sum())

    # Encodage : textes mal décodés
    texte = df["texte"].fillna("")
    repare = texte.map(reparer_encodage)
    log["encodage_repare"] = int((repare != texte).sum())

    # Données personnelles masquées (on compte chaque type)
    log["emails_masques"] = int(repare.str.contains(RE_EMAIL).sum())
    log["telephones_masques"] = int(repare.str.contains(RE_TEL).sum())
    log["noms_masques"] = int(repare.str.contains(RE_NOM).sum())
    repare = (repare.str.replace(RE_EMAIL, "[EMAIL]", regex=True)
                    .str.replace(RE_TEL, "[TEL]", regex=True)
                    .str.replace(RE_NOM, "[NOM]", regex=True))
    df["texte"] = repare

    # Messages sans contenu (vides ou seulement un point) : supprimés
    vide = df["texte"].str.strip(" .").eq("")
    log["messages_sans_contenu"] = int(vide.sum())
    df = df[~vide].sort_values("id_message").reset_index(drop=True)

    log["lignes_apres"] = len(df)
    return df, log


def semaine_de_sortie(inscriptions):
    """Semaine (1 = rentrée) de la date de sortie déclarée ; manquante si pas de date de fin."""
    semaine = (inscriptions["date_fin"] - inscriptions["date_debut"]).dt.days // 7 + 1
    return inscriptions.assign(semaine_sortie=semaine)[["id_etudiant", "statut_final", "semaine_sortie"]]


def nettoyer_activite(ids_etudiants, inscriptions, chemin=RAW / "activite_hebdo.csv"):
    """Nettoie activite_hebdo (une ligne par étudiant et par semaine)."""
    log = {}
    df = pd.read_csv(chemin, sep=",", dtype=str, encoding="utf-8")
    log["lignes_avant"] = len(df)
    df.columns = [c.strip() for c in df.columns]
    df = df.apply(lambda col: col.str.strip())

    log["doublons_exacts"] = int(df.duplicated().sum())
    df = df.drop_duplicates()

    log["ids_mal_formates"] = int((df["id_etudiant"] != df["id_etudiant"].str.upper()).sum())
    df["id_etudiant"] = nettoyer_id(df["id_etudiant"])
    inconnus = ~df["id_etudiant"].isin(ids_etudiants)
    log["ids_hors_etudiants"] = int(inconnus.sum())
    df = df[~inconnus]

    # Nombres : virgule -> point
    for col in ["semaine", "nb_connexions_lms", "devoirs_rendus", "note_moyenne", "absences"]:
        df[col] = en_nombre(df[col])

    # Semaines hors [1 ; 30] : lignes supprimées
    hors = ~df["semaine"].between(1, 30)
    log["semaine_hors_1_30"] = int(hors.sum())
    df = df[~hors].copy()
    df["semaine"] = df["semaine"].astype(int)

    # Valeurs impossibles -> manquant (jamais remplacées par 0)
    mauvais = df["devoirs_rendus"].notna() & ~df["devoirs_rendus"].isin([0, 1, 2])
    log["devoirs_hors_0_2"] = int(mauvais.sum())
    df.loc[mauvais, "devoirs_rendus"] = np.nan

    mauvais = df["nb_connexions_lms"].notna() & ((df["nb_connexions_lms"] < 0) | (df["nb_connexions_lms"] > 100))
    log["connexions_impossibles"] = int(mauvais.sum())
    df.loc[mauvais, "nb_connexions_lms"] = np.nan

    mauvais = df["note_moyenne"].notna() & ~df["note_moyenne"].between(0, 20)
    log["note_hors_0_20"] = int(mauvais.sum())
    df.loc[mauvais, "note_moyenne"] = np.nan

    mauvais = df["absences"].notna() & ~df["absences"].between(0, 20)
    log["absences_hors_0_20"] = int(mauvais.sum())
    df.loc[mauvais, "absences"] = np.nan

    # Plusieurs lignes pour le même (étudiant, semaine) : on garde la plus complète
    df["_nb_manquants"] = df.isna().sum(axis=1)
    df = df.sort_values(["id_etudiant", "semaine", "_nb_manquants"], kind="stable")
    log["doublons_etudiant_semaine"] = int(df.duplicated(["id_etudiant", "semaine"]).sum())
    df = df.drop_duplicates(["id_etudiant", "semaine"]).drop(columns="_nb_manquants")

    # Activité après la sortie déclarée de l'étudiant : incohérence temporelle -> supprimée
    sortie = semaine_de_sortie(inscriptions)[["id_etudiant", "semaine_sortie"]]
    df = df.merge(sortie, on="id_etudiant", how="left")
    apres = df["semaine_sortie"].notna() & (df["semaine"] > df["semaine_sortie"])
    log["activite_apres_sortie_declaree"] = int(apres.sum())
    df = df[~apres].drop(columns="semaine_sortie").reset_index(drop=True)

    log["lignes_apres"] = len(df)
    return df, log


def nettoyer_tutorat(ids_etudiants, inscriptions, chemin=RAW / "tutorat.csv"):
    """Nettoie tutorat (une ligne par prise en charge)."""
    log = {}
    df = pd.read_csv(chemin, sep=",", dtype=str, encoding="utf-8")
    log["lignes_avant"] = len(df)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={"ID Etudiant": "id_etudiant"})
    df = df.apply(lambda col: col.str.strip())

    log["doublons_exacts"] = int(df.duplicated().sum())
    df = df.drop_duplicates()

    df["id_etudiant"] = nettoyer_id(df["id_etudiant"])
    inconnus = ~df["id_etudiant"].isin(ids_etudiants)
    log["ids_hors_etudiants"] = int(inconnus.sum())
    df = df[~inconnus]

    df["type_tuteur"] = recoder(df["type_tuteur"], {
        "pair": "pair", "pair (etudiant avance)": "pair", "etudiant": "pair",
        "enseignant": "enseignant", "prof": "enseignant"})

    df["semaine_debut"] = en_nombre(df["semaine_debut"])
    mauvais = df["semaine_debut"].notna() & ~df["semaine_debut"].between(1, 30)
    log["semaine_debut_hors_1_30"] = int(mauvais.sum())
    df.loc[mauvais, "semaine_debut"] = np.nan

    df["nb_seances"] = en_nombre(df["nb_seances"])
    log["nb_seances_manquant"] = int(df["nb_seances"].isna().sum())
    mauvais = df["nb_seances"].notna() & ~df["nb_seances"].between(0, 30)
    log["nb_seances_hors_0_30"] = int(mauvais.sum())
    df.loc[mauvais, "nb_seances"] = np.nan

    # Tutorat qui commence après la sortie déclarée : on signale (décision dans CA-01)
    sortie = semaine_de_sortie(inscriptions)[["id_etudiant", "semaine_sortie"]]
    df = df.merge(sortie, on="id_etudiant", how="left")
    df["tutorat_apres_sortie"] = df["semaine_sortie"].notna() & (df["semaine_debut"] > df["semaine_sortie"])
    log["tutorat_apres_sortie_signale"] = int(df["tutorat_apres_sortie"].sum())
    df = df.drop(columns="semaine_sortie").sort_values("id_etudiant").reset_index(drop=True)

    log["lignes_apres"] = len(df)
    return df, log


def afficher(titre, log):
    print(f"=== {titre} ===")
    for cle, valeur in log.items():
        print(f"{cle:36s} {valeur}")


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)

    etudiants, log = nettoyer_etudiants()
    etudiants.to_csv(PROCESSED / "etudiants.csv", index=False, encoding="utf-8")
    afficher("etudiants", log)

    inscriptions, log = nettoyer_inscriptions(set(etudiants["id_etudiant"]))
    inscriptions.to_csv(PROCESSED / "inscriptions.csv", index=False, encoding="utf-8")
    afficher("inscriptions", log)

    ids = set(etudiants["id_etudiant"])
    activite, log = nettoyer_activite(ids, inscriptions)
    activite.to_csv(PROCESSED / "activite_hebdo.csv", index=False, encoding="utf-8")
    afficher("activite_hebdo", log)

    tutorat, log = nettoyer_tutorat(ids, inscriptions)
    tutorat.to_csv(PROCESSED / "tutorat.csv", index=False, encoding="utf-8")
    afficher("tutorat", log)

    messages, log = nettoyer_messages(ids)
    messages.to_csv(PROCESSED / "messages.csv", index=False, encoding="utf-8")
    afficher("messages", log)


if __name__ == "__main__":
    main()
