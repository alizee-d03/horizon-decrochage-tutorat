"""Construction des durées T et des événements E (DA-07).

Définitions imposées par le cahier des charges :
  * origine du temps : semaine 1 = semaine de la rentrée ;
  * événement (décrochage) : abandon déclaré à la scolarité, OU `k` semaines
    consécutives sans aucune connexion ni devoir rendu (k = 4 par défaut) ;
    la semaine de l'événement est la première des k semaines d'inactivité ;
  * censure : transfert vers un autre établissement, ou toujours inscrit à la
    semaine 30. Les étudiants censurés ne sont jamais supprimés.

Lancer depuis la racine du projet :  python src/survie.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

PROCESSED = Path("data/processed")
N_SEMAINES = 30
COVARIABLES = ["cohorte", "genre", "age", "boursier", "filiere", "mention_bac",
               "note_bac", "region_origine", "distance_campus_km", "emploi_parallele"]


def charger(dossier=PROCESSED):
    """Charge les tables nettoyées."""
    return {
        "etudiants": pd.read_csv(dossier / "etudiants.csv"),
        "inscriptions": pd.read_csv(dossier / "inscriptions.csv",
                                    parse_dates=["date_debut", "date_fin"]),
        "activite": pd.read_csv(dossier / "activite_hebdo.csv"),
        "tutorat": pd.read_csv(dossier / "tutorat.csv"),
    }


def premiere_fenetre_inactive(activite, ids, k=4):
    """Pour chaque étudiant, première semaine d'une série de `k` semaines inactives
    (aucune connexion ET aucun devoir rendu). NaN si aucune série.

    Une semaine est « inactive » seulement si connexions = 0 ET devoirs = 0 sont
    connus. Une valeur manquante n'est jamais comptée comme de l'inactivité."""
    inactif = (activite["nb_connexions_lms"] == 0) & (activite["devoirs_rendus"] == 0)
    grille = (activite.assign(inactif=inactif)
              .pivot(index="id_etudiant", columns="semaine", values="inactif")
              .reindex(index=ids, columns=range(1, N_SEMAINES + 1))
              .fillna(False).astype(int).to_numpy())
    # somme glissante sur k semaines : égale à k si les k semaines sont inactives
    somme = np.stack([grille[:, i:N_SEMAINES - k + 1 + i] for i in range(k)]).sum(axis=0)
    trouve = somme == k
    debut = np.where(trouve.any(axis=1), trouve.argmax(axis=1) + 1, np.nan)
    return pd.Series(debut, index=ids, name="semaine_inactivite")


def construire_base_survie(k=4, tables=None):
    """Une ligne par étudiant : T, E, covariables, tutorat, semaine de début du tutorat."""
    t = tables or charger()
    et, ins, act, tut = t["etudiants"], t["inscriptions"], t["activite"], t["tutorat"]
    ids = et["id_etudiant"]

    base = et[["id_etudiant"] + COVARIABLES].copy().set_index("id_etudiant")

    # Statut administratif et semaine de sortie déclarée
    ins = ins.set_index("id_etudiant")
    semaine_fin = (ins["date_fin"] - ins["date_debut"]).dt.days // 7 + 1
    derniere_obs = act.groupby("id_etudiant")["semaine"].max()
    base["statut_final"] = ins["statut_final"].reindex(base.index)
    base["sans_inscription"] = base["statut_final"].isna()
    base["statut_final"] = base["statut_final"].fillna("inscrit")
    sortie = semaine_fin.reindex(base.index)
    # Abandon ou transfert sans date de fin : la dernière semaine d'activité observée
    manque = sortie.isna() & base["statut_final"].isin(["abandon", "transfert"])
    sortie[manque] = derniere_obs.reindex(base.index)[manque]
    base["semaine_sortie"] = sortie

    # Inactivité
    base["semaine_inactivite"] = premiere_fenetre_inactive(act, base.index, k)

    # Événement et durée
    abandon_declare = sortie.where(base["statut_final"] == "abandon")
    candidats = pd.concat([abandon_declare, base["semaine_inactivite"]], axis=1)
    t_evenement = candidats.min(axis=1)
    base["E"] = t_evenement.notna().astype(int)
    censure = np.where(base["statut_final"] == "transfert", sortie, N_SEMAINES)
    base["T"] = np.where(base["E"] == 1, t_evenement, censure).astype(int)
    base["cause"] = np.select(
        [base["E"].eq(1) & abandon_declare.notna() & base["semaine_inactivite"].isna(),
         base["E"].eq(1) & abandon_declare.isna(),
         base["E"].eq(1),
         base["statut_final"] == "transfert"],
        ["abandon_declare", "inactivite_non_declaree", "les_deux", "transfert"],
        default="inscrit_semaine_30")

    # Tutorat
    tut = tut.set_index("id_etudiant")
    base["tutorat"] = base.index.isin(tut.index).astype(int)
    for col in ["semaine_debut", "type_tuteur", "motif_orientation", "nb_seances",
                "tutorat_apres_sortie"]:
        base[col if col != "semaine_debut" else "semaine_debut_tutorat"] = tut[col].reindex(base.index)
    base["tutorat_apres_sortie"] = base["tutorat_apres_sortie"].fillna(False).astype(bool)
    base["tutorat_apres_fin_suivi"] = (base["tutorat"].eq(1)
                                       & (base["semaine_debut_tutorat"] > base["T"]))

    colonnes = (["T", "E", "cause", "statut_final", "tutorat", "semaine_debut_tutorat",
                 "type_tuteur", "motif_orientation", "nb_seances", "tutorat_apres_sortie",
                 "tutorat_apres_fin_suivi", "sans_inscription", "semaine_sortie",
                 "semaine_inactivite"] + COVARIABLES)
    return base[colonnes].reset_index()


def format_periode_personne(base):
    """Une ligne par étudiant et par semaine jusqu'à T (inclus).
    `evenement` vaut 1 sur la dernière ligne des étudiants décrochés ;
    `tutorat_en_cours` vaut 1 à partir de la semaine de début du tutorat."""
    lignes = base.loc[base.index.repeat(base["T"]), ["id_etudiant", "T", "E",
                                                     "tutorat", "semaine_debut_tutorat"]].copy()
    lignes["semaine"] = lignes.groupby("id_etudiant").cumcount() + 1
    lignes["evenement"] = ((lignes["semaine"] == lignes["T"]) & (lignes["E"] == 1)).astype(int)
    lignes["tutorat_en_cours"] = ((lignes["tutorat"] == 1)
                                  & (lignes["semaine"] >= lignes["semaine_debut_tutorat"])).astype(int)
    return lignes[["id_etudiant", "semaine", "evenement", "tutorat_en_cours"]].reset_index(drop=True)


def sensibilite_regle(ks=(3, 4, 5), tables=None):
    """Compare la règle d'inactivité (3, 4 ou 5 semaines) : nombre d'événements, T médian."""
    t = tables or charger()
    resultats = []
    for k in ks:
        b = construire_base_survie(k, t)
        resultats.append({"k": k, "evenements": int(b["E"].sum()),
                          "taux_decrochage_%": round(100 * b["E"].mean(), 1),
                          "T_median_des_decroches": float(b.loc[b["E"] == 1, "T"].median()),
                          "inactivite_non_declaree": int((b["cause"] == "inactivite_non_declaree").sum())})
    return pd.DataFrame(resultats)


def main():
    tables = charger()
    base = construire_base_survie(4, tables)
    base.to_csv(PROCESSED / "base_survie.csv", index=False, encoding="utf-8")
    format_periode_personne(base).to_csv(PROCESSED / "periode_personne.csv",
                                         index=False, encoding="utf-8")
    print("=== base_survie (règle de 4 semaines) ===")
    print("étudiants          :", len(base))
    print("événements (E=1)   :", int(base["E"].sum()), f"({100 * base['E'].mean():.1f} %)")
    print("censurés (E=0)     :", int((base["E"] == 0).sum()), f"({100 * (1 - base['E'].mean()):.1f} %)")
    print(base["cause"].value_counts().to_string())
    print("tutorat            :", int(base["tutorat"].sum()), "étudiants")
    print("tutorat après la fin du suivi :", int(base["tutorat_apres_fin_suivi"].sum()))
    print("\n=== sensibilité à la règle d'inactivité ===")
    print(sensibilite_regle(tables=tables).to_string(index=False))


if __name__ == "__main__":
    main()
