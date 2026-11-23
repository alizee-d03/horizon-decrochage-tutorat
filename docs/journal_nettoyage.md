# Journal de nettoyage — Horizon

Brouillon issu de l'audit DA-01 (fichiers bruts). Les colonnes « Lignes » marquées *à compter* seront remplies par le script de nettoyage. Les traitements sont à valider et à ajuster pendant DA-02 à DA-05.

## Anomalies de structure (toutes tables)

| # | Table | Anomalie constatée | Lignes | Traitement appliqué | Justification |
|---|---|---|---|---|---|
| 1 | inscriptions | Séparateur `;` au lieu de `,` | fichier | Lecture avec `sep=";"` | Indiqué dans LISEZMOI ; une lecture avec `,` produit une seule colonne |
| 2 | etudiants | Nom de colonne `id_etudiant ` avec espace final | 1 col. | Renommer en `id_etudiant` | Permet la jointure entre tables |
| 3 | etudiants | Nom de colonne `Distance campus (km)` | 1 col. | Renommer en `distance_campus_km` | Nom du dictionnaire, sans espace ni parenthèses |
| 4 | tutorat | Nom de colonne `ID Etudiant` | 1 col. | Renommer en `id_etudiant` | Permet la jointure entre tables |
| 5 | tous | Encodage : aucun problème (UTF-8 correct) | 0 | Aucun | Les caractères « Ú » vus dans PowerShell venaient de l'affichage de la console |

## etudiants (5 085 lignes brutes, 5 000 attendues)

| # | Table | Anomalie constatée | Lignes | Traitement appliqué | Justification |
|---|---|---|---|---|---|
| 6 | etudiants | Doublons exacts | 60 | Supprimer, garder 1 ligne | Un étudiant ne doit apparaître qu'une fois |
| 7 | etudiants | Identifiants mal formatés (minuscules, espaces) | 25 | `strip()` + majuscules | Format attendu `HZ` + 5 chiffres ; après correction on obtient bien 5 000 identifiants |
| 8 | etudiants | `genre` : 10 modalités (Femme, FEMININ, f, Homme, Masculin, m, H…) | à compter | Recoder en F / M | Modalités attendues : F, M |
| 9 | etudiants | `boursier` : 12 modalités (N, non, 0, no, O, 1, yes…) | à compter | Recoder en Oui / Non | Modalités attendues : Oui, Non |
| 10 | etudiants | `filiere` : 22 modalités (INFO, Info, GC, Com, genie civil…) | à compter | Recoder en 5 filières | Dictionnaire : 5 filières |
| 11 | etudiants | `mention_bac` : 15 modalités (P, AB, B, TB, minuscules…) | à compter | Recoder en 4 mentions | Dictionnaire : 4 mentions |
| 12 | etudiants | `region_origine` : 28 écritures (Zig, ST LOUIS, thies, Kedougou, Dakar avec espace…) | à compter | Recoder en 14 régions | Dictionnaire : 14 régions du Sénégal |
| 13 | etudiants | `age` écrit avec du texte (« 19 ans ») | 46 | Extraire le nombre | Variable numérique |
| 14 | etudiants | `age` aberrant (0, 3, 99, 150, 210) | 14 | Mettre à manquant | Valeurs attendues : 17 à 35 |
| 15 | etudiants | `age` manquant | 72 | Imputer par la médiane (à documenter) | Conserver l'étudiant dans l'analyse |
| 16 | etudiants | `note_bac` avec virgule décimale (« 13,45 ») | à compter | Remplacer la virgule par un point | Conversion en nombre |
| 17 | etudiants | `note_bac` hors [0 ; 20] (de −2 à 135) | à compter | Mettre à manquant (tester si ÷10 est cohérent avec la mention) | Moyenne sur 20 |
| 18 | etudiants | `Distance campus` avec unité (« 9.1 km ») | 41 | Retirer « km » | Variable numérique |
| 19 | etudiants | `Distance campus` : valeur sentinelle 9999 et valeurs négatives | à compter | Mettre à manquant | Distance attendue > 0 |
| 20 | etudiants | Manquants : `mention_bac` | 154 | Catégorie « Inconnue » ou déduction depuis `note_bac` | À décider et justifier |
| 21 | etudiants | Manquants : `region_origine` | 91 | Catégorie « Inconnue » | Ne pas inventer une région |
| 22 | etudiants | Manquants : `emploi_parallele` | 205 | Catégorie « Inconnu » | Ne pas inventer une valeur |

## inscriptions (5 024 lignes brutes)

| # | Table | Anomalie constatée | Lignes | Traitement appliqué | Justification |
|---|---|---|---|---|---|
| 23 | inscriptions | Doublons exacts | 20 | Supprimer | Une inscription par étudiant |
| 24 | inscriptions | `date_debut` : 4 formats (`2025-10-06`, `06/10/2025`, `2025/10/06`, `6 oct. 2025`) | à compter | Convertir en AAAA-MM-JJ | Calcul des semaines |
| 25 | inscriptions | `date_fin` : formats mélangés, mois en français (« 12 avr. 2025 ») | à compter | Convertir en AAAA-MM-JJ | Idem |
| 26 | inscriptions | `date_debut` hors rentrée (ex. 2026-04-16, 16/01/2026) | 12 | Remplacer par la date de rentrée de l'année universitaire (07/10/2024 ou 06/10/2025) | Semaine 1 = semaine de la rentrée |
| 27 | inscriptions | `statut_final` : 13 modalités (INSCRIT, abandonné, transfere, transféré…) | à compter | Recoder en abandon / transfert / inscrit | Dictionnaire : 3 statuts |
| 28 | inscriptions | `statut_final` manquant | 41 | Déduire de `date_fin` et de l'activité (à vérifier) | Le statut détermine E et la censure |
| 29 | inscriptions | Identifiants absents de `etudiants` | 14 | Exclure (ou chercher une faute de frappe) | Incohérence entre tables |
| 30 | etudiants | Étudiants sans inscription | 10 | Conserver, rentrée = date standard de la cohorte | Éviter de perdre des étudiants |

## activite_hebdo (130 967 lignes brutes)

| # | Table | Anomalie constatée | Lignes | Traitement appliqué | Justification |
|---|---|---|---|---|---|
| 31 | activite_hebdo | Doublons exacts | 870 | Supprimer | Une ligne par étudiant et par semaine |
| 32 | activite_hebdo | Identifiants en minuscules | 1 310 | Majuscules | Après correction : 5 000 identifiants |
| 33 | activite_hebdo | `semaine` hors [1 ; 30] (valeurs −1, 0, 31, 32, 99) | 70 | Supprimer | Hors période de suivi |
| 34 | activite_hebdo | Plusieurs lignes pour le même couple (étudiant, semaine) après dédoublonnage | 190 | Garder la ligne la plus complète (à documenter) | Une seule valeur par semaine |
| 35 | activite_hebdo | `devoirs_rendus` hors [0 ; 2] (3, 4, 7) | 30 | Mettre à manquant | Valeurs attendues : 0 à 2 |
| 36 | activite_hebdo | `nb_connexions_lms` manquant | 1 298 | Laisser manquant, **ne pas compter comme 0** | Un 0 fausserait la règle des 4 semaines d'inactivité (E) |
| 37 | activite_hebdo | `nb_connexions_lms` négatif ou énorme (−12, 8 636) | à compter (45 négatifs) | Mettre à manquant | Valeurs impossibles |
| 38 | activite_hebdo | `note_moyenne` avec virgule | 1 703 | Remplacer par un point | Conversion en nombre |
| 39 | activite_hebdo | `note_moyenne` hors [0 ; 20] (−1, jusqu'à 163,6) | environ 135 | Mettre à manquant | Notes sur 20 |
| 40 | activite_hebdo | `note_moyenne` manquante (56 %) | 73 574 | Laisser manquant | Normal : semaines sans évaluation (LISEZMOI) |
| 41 | activite_hebdo | Pic d'`absences` = 20 (8 435 lignes, avec 0 connexion et 0 devoir) | 8 435 | **Ne pas supprimer** ; à analyser | Probablement des semaines après un abandon : utile pour la règle des 4 semaines |

## tutorat (1 291 lignes brutes, 1 300 attendues)

| # | Table | Anomalie constatée | Lignes | Traitement appliqué | Justification |
|---|---|---|---|---|---|
| 42 | tutorat | Doublons exacts | 30 | Supprimer | Une prise en charge par étudiant (1 261 restants) |
| 43 | tutorat | `type_tuteur` : 9 modalités (Pair, PAIR, étudiant, Prof, enseignant avec espace…) | à compter | Recoder en pair / enseignant | Dictionnaire : 2 types |
| 44 | tutorat | `semaine_debut` hors [1 ; 30] (0, 45, 52) | 10 | Mettre à manquant ; décision dans CA-01 | Le moment de début sert à traiter le temps immortel |
| 45 | tutorat | `nb_seances` manquant | 8 | Laisser manquant | Variable secondaire |
| 46 | tutorat | `nb_seances` négatif ou > 30 (de −2 à 38) | à compter | Mettre à manquant | Impossible sur 30 semaines |
| 47 | tutorat | Identifiants absents de `etudiants` | 6 | Exclure | Incohérence entre tables |
| 48 | tutorat | Tutorat commencé après l'abandon de l'étudiant | à compter | À vérifier en DA-04 | Incohérence temporelle |

## messages (3 200 lignes)

| # | Table | Anomalie constatée | Lignes | Traitement appliqué | Justification |
|---|---|---|---|---|---|
| 49 | messages | Adresses email dans le texte (« Mon mail : prenom.nom@exemple.sn ») | 33 | Remplacer par `[EMAIL]` | Données personnelles (loi 2008-12, RGPD) |
| 50 | messages | Téléphones dans le texte (« appelez-moi au 77 000 54 83 ») | à compter | Remplacer par `[TEL]` | Données personnelles |
| 51 | messages | Noms dans le texte (« Je suis Moussa Ndiaye, … ») | à compter | Remplacer par `[NOM]` | Données personnelles |
| 52 | messages | `texte` manquant | 7 | Supprimer ces messages | Aucun contenu exploitable |

## Tableau avant / après (à remplir après le nettoyage)

| Table | Lignes avant | Lignes après | Manquants avant | Manquants après | Doublons avant | Doublons après |
|---|---|---|---|---|---|---|
| etudiants | 5 085 | | | | 60 | |
| inscriptions | 5 024 | | | | 20 | |
| activite_hebdo | 130 967 | | | | 870 | |
| tutorat | 1 291 | | | | 30 | |
| messages | 3 200 | | | | 0 | |
