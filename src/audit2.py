import pandas as pd
from pathlib import Path

RAW = Path("data/raw")
sortie = []

def log(*args):
    sortie.append(" ".join(str(a) for a in args))

def lire(fichier):
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            df = pd.read_csv(fichier, sep=None, engine="python",
                             dtype=str, encoding=enc)
            return df, enc
        except UnicodeDecodeError:
            continue

for f in sorted(RAW.glob("*.csv")):
    df, enc = lire(f)
    log("=" * 60)
    log(f.name, "| encodage :", enc)
    for col in df.columns:
        s = df[col].dropna()
        n = s.nunique()
        log(f"\n-- {col} ({n} valeurs distinctes)")
        if n <= 25:
            log(df[col].value_counts(dropna=False).to_string())
        else:
            log("Exemples :", s.sample(min(8, len(s)), random_state=0).tolist())
            num = pd.to_numeric(s.str.replace(",", ".", regex=False),
                                errors="coerce")
            if num.notna().sum() > 0.5 * len(s):
                log("min / max :", num.min(), "/", num.max())
                log("non convertibles en nombre :", len(s) - num.notna().sum())
    for col in df.columns:
        if "id" in col.lower() and "etudiant" in col.lower():
            mauvais = ~df[col].fillna("").str.match(r"^HZ\d{5}$")
            log(f"\nIdentifiants mal formatés dans {col} :", mauvais.sum())
            log(df.loc[mauvais, col].head(10).tolist())
    if "texte" in df.columns:
        t = df["texte"].fillna("")
        log("\nMessages avec '@' (emails ?) :", t.str.contains("@").sum())
        log("Messages avec suite de chiffres (téléphone ?) :",
            t.str.contains(r"\d{7,}|\d{2}[ .]\d{2}[ .]\d{2}[ .]\d{2}").sum())

Path("docs/audit_valeurs.txt").write_text("\n".join(sortie), encoding="utf-8")
print("Rapport écrit dans docs/audit_valeurs.txt")