"""Tests automatiques de qualité des données nettoyées (DA-06).

Lancer depuis la racine du projet :  python -m pytest
"""
import os
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

FORMAT_ID = r"^HZ\d{5}$"


@pytest.fixture(scope="session")
def tables():
    """Relance le nettoyage puis charge les tables propres."""
    os.chdir(ROOT)
    import nettoyage
    nettoyage.main()
    dossier = ROOT / "data" / "processed"
    return {
        "etudiants": pd.read_csv(dossier / "etudiants.csv"),
        "inscriptions": pd.read_csv(dossier / "inscriptions.csv",
                                    parse_dates=["date_debut", "date_fin"]),
        "activite": pd.read_csv(dossier / "activite_hebdo.csv"),
        "tutorat": pd.read_csv(dossier / "tutorat.csv"),
        "messages": pd.read_csv(dossier / "messages.csv"),
    }


def test_identifiants_etudiants_uniques_et_bien_formes(tables):
    ids = tables["etudiants"]["id_etudiant"]
    assert ids.is_unique
    assert ids.str.match(FORMAT_ID).all()
    assert len(ids) == 5000


def test_identifiants_des_autres_tables_existent_dans_etudiants(tables):
    ids = set(tables["etudiants"]["id_etudiant"])
    for nom in ["inscriptions", "activite", "tutorat", "messages"]:
        col = tables[nom]["id_etudiant"]
        assert col.str.match(FORMAT_ID).all(), nom
        assert col.isin(ids).all(), nom


def test_semaines_entre_1_et_30(tables):
    assert tables["activite"]["semaine"].between(1, 30).all()
    assert tables["messages"]["semaine"].between(1, 30).all()
    debut = tables["tutorat"]["semaine_debut"].dropna()
    assert debut.between(1, 30).all()


def test_une_ligne_par_etudiant_et_semaine(tables):
    assert not tables["activite"].duplicated(["id_etudiant", "semaine"]).any()


def test_notes_entre_0_et_20(tables):
    assert tables["activite"]["note_moyenne"].dropna().between(0, 20).all()
    assert tables["etudiants"]["note_bac"].dropna().between(0, 20).all()


def test_valeurs_numeriques_plausibles(tables):
    act = tables["activite"]
    assert act["devoirs_rendus"].dropna().isin([0, 1, 2]).all()
    assert (act["nb_connexions_lms"].dropna() >= 0).all()
    assert act["absences"].dropna().between(0, 20).all()
    assert tables["etudiants"]["age"].dropna().between(17, 35).all()
    assert (tables["etudiants"]["distance_campus_km"].dropna() > 0).all()


def test_modalites_harmonisees(tables):
    et = tables["etudiants"]
    assert set(et["genre"].dropna()) <= {"F", "M"}
    assert set(et["boursier"].dropna()) <= {"Oui", "Non"}
    assert set(et["filiere"].dropna()) == {"Informatique", "Gestion", "Droit",
                                           "Génie civil", "Communication"}
    assert set(et["mention_bac"]) <= {"Passable", "Assez bien", "Bien", "Très bien", "Inconnue"}
    assert len(set(et["region_origine"]) - {"Inconnue"}) == 14
    assert set(tables["inscriptions"]["statut_final"]) == {"inscrit", "abandon", "transfert"}
    assert set(tables["tutorat"]["type_tuteur"]) == {"pair", "enseignant"}


def test_inscriptions_dates_coherentes(tables):
    ins = tables["inscriptions"]
    assert ins["id_etudiant"].is_unique
    assert ins["date_debut"].isin(pd.to_datetime(["2024-10-07", "2025-10-06"])).all()
    fin = ins.dropna(subset=["date_fin"])
    assert (fin["date_fin"] >= fin["date_debut"]).all()


def test_pas_de_donnees_personnelles_dans_messages(tables):
    texte = tables["messages"]["texte"].fillna("")
    assert not texte.str.contains("@").any()
    assert not texte.str.contains(r"\d{2}[ .]?\d{3}[ .]?\d{2}[ .]?\d{2}").any()
    assert not texte.str.contains("Ã").any()


def test_tutorat_un_seul_enregistrement_par_etudiant(tables):
    assert tables["tutorat"]["id_etudiant"].is_unique
