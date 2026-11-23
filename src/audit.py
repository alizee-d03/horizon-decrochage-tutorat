import pandas as pd
from pathlib import Path

RAW = Path("data/raw")
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
def lire(fichier):
    """Lit un CSV en détectant le séparateur et l'encodage, tout en texte."""
    for enc in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(fichier, sep=None, engine="python",
                             dtype=str, encoding=enc)
            return df, enc
        except UnicodeDecodeError:
            continue
    raise ValueError("Encodage non reconnu")

for f in sorted(RAW.glob("*.csv")):
    df, enc = lire(f)
    print("=" * 60)
    print(f.name, "| encodage :", enc)
    print("Lignes :", len(df), "| Colonnes :", len(df.columns))
    print("\nValeurs manquantes par colonne :")
    print(df.isna().sum())
    print("\nDoublons exacts :", df.duplicated().sum())
    print("Doublons sur la 1re colonne :", df.iloc[:, 0].duplicated().sum())
    print("\nAperçu :")
    print(df.head())