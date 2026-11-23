"""Tests de la construction de T, E et de base_survie (DA-07)."""
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(scope="session")
def base():
    os.chdir(ROOT)
    import nettoyage
    import survie
    nettoyage.main()
    tables = survie.charger()
    b = survie.construire_base_survie(4, tables)
    return {"base": b, "tables": tables, "survie": survie}


def test_une_ligne_par_etudiant(base):
    b = base["base"]
    assert len(b) == 5000
    assert b["id_etudiant"].is_unique


def test_duree_et_evenement_valides(base):
    b = base["base"]
    assert b["T"].between(1, 30).all()
    assert set(b["E"]) <= {0, 1}


def test_les_censures_ne_sont_pas_supprimes(base):
    b = base["base"]
    assert (b["E"] == 0).sum() > 0
    assert (b["cause"] == "transfert").sum() == 117
    assert (b.loc[b["cause"] == "inscrit_semaine_30", "T"] == 30).all()


def test_abandons_declares_sont_des_evenements(base):
    b = base["base"]
    assert (b.loc[b["statut_final"] == "abandon", "E"] == 1).all()
    assert (b.loc[b["cause"] == "transfert", "E"] == 0).all()


def test_regle_inactivite_plus_stricte_donne_moins_d_evenements(base):
    s = base["survie"].sensibilite_regle(tables=base["tables"])
    evenements = s.set_index("k")["evenements"]
    assert evenements[3] >= evenements[4] >= evenements[5]


def test_format_periode_personne_coherent(base):
    b = base["base"]
    pp = base["survie"].format_periode_personne(b)
    assert len(pp) == b["T"].sum()
    assert pp["evenement"].sum() == b["E"].sum()
    assert not pp.duplicated(["id_etudiant", "semaine"]).any()
