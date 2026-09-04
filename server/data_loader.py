"""
data_loader.py
----------------
Loads and cleans the raw Pokemon TCG dataset (1999-2023) and produces a
processed CSV used by the Flask API.

Source: Kaggle "Pokemon TCG All Cards 1999-2023"
        (adampq/pokemon-tcg-all-cards-1999-2023)
        Built from the official Pokemon TCG API.

Run directly to (re)generate data/processed/pokemon_cards_clean.csv:
    python data_loader.py
"""

import ast
import os
import pandas as pd

RAW_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "pokemon_cards_raw.csv")
PROCESSED_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "pokemon_cards_clean.csv")

# Columns we actually need for the dashboard. The raw dataset has 29 columns,
# many of which (abilities, attacks, legalities, ancientTrait, etc.) are deeply
# nested and not relevant to the browsing/analytics use case here, so they are
# dropped to keep the processed file lean.
KEEP_COLUMNS = [
    "id",
    "name",
    "set",
    "series",
    "generation",
    "publisher",
    "release_date",
    "artist",
    "supertype",
    "rarity",
    "types",
    "subtypes",
    "hp",
    "convertedRetreatCost",
]


def _parse_stringified_list(value):
    """
    Several columns (types, subtypes) are stored as strings that look like
    Python lists, e.g. "['Fire', 'Flying']". Convert these to an actual list,
    or [] / None on failure.
    """
    if pd.isna(value):
        return None
    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return parsed
    except (ValueError, SyntaxError):
        pass
    return None


def load_and_clean(raw_path: str = RAW_PATH) -> pd.DataFrame:
    df = pd.read_csv(raw_path, low_memory=False)

    # --- 1. Trim to the columns we use -----------------------------------
    df = df[KEEP_COLUMNS].copy()

    # --- 2. Drop rows missing essential identifying fields -----------------
    before = len(df)
    df = df.dropna(subset=["name", "set", "release_date"])
    dropped_missing_essentials = before - len(df)

    # --- 3. Parse list-like string columns ---------------------------------
    df["types"] = df["types"].apply(_parse_stringified_list)
    df["subtypes"] = df["subtypes"].apply(_parse_stringified_list)

    # For filtering/display, also keep a flattened "primary_type" (first type)
    # and a comma-joined "types_display" string, since most Pokemon TCG cards
    # have 1-2 types and the API/UI wants simple scalar values.
    df["primary_type"] = df["types"].apply(lambda t: t[0] if isinstance(t, list) and t else None)
    df["types_display"] = df["types"].apply(lambda t: ", ".join(t) if isinstance(t, list) and t else None)

    # --- 4. Parse dates ------------------------------------------------------
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    before = len(df)
    df = df.dropna(subset=["release_date"])
    dropped_bad_dates = before - len(df)
    df["release_year"] = df["release_date"].dt.year

    # --- 5. Clean numeric fields ---------------------------------------------
    df["hp"] = pd.to_numeric(df["hp"], errors="coerce")
    df["convertedRetreatCost"] = pd.to_numeric(df["convertedRetreatCost"], errors="coerce")
    df = df.rename(columns={"convertedRetreatCost": "retreat_cost"})

    # Non-Pokemon cards (Trainer, Energy) legitimately have no HP/retreat cost.
    # We keep these rows (they're valid cards) but leave hp/retreat_cost as NaN
    # rather than imputing a fake value, since 0 would misleadingly suggest a
    # 0-HP Pokemon. The API/client treat null hp as "not applicable".

    # --- 6. Normalize text fields ---------------------------------------------
    for col in ["name", "set", "series", "generation", "publisher", "artist", "rarity", "supertype"]:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": None, "None": None})

    df["rarity"] = df["rarity"].fillna("Unknown")
    # "Rare Ultra" and "Ultra Rare" are the same tier under two different name orders.
    df["rarity"] = df["rarity"].replace({"Rare Ultra": "Ultra Rare"})
    df["artist"] = df["artist"].fillna("Unknown")

    # --- 7. Deduplicate -------------------------------------------------------
    before = len(df)
    df = df.drop_duplicates(subset=["id"])
    dropped_duplicates = before - len(df)

    # --- 8. Final column order --------------------------------------------------
    df = df[
        [
            "id",
            "name",
            "set",
            "series",
            "generation",
            "publisher",
            "release_date",
            "release_year",
            "artist",
            "supertype",
            "rarity",
            "primary_type",
            "types_display",
            "hp",
            "retreat_cost",
        ]
    ].reset_index(drop=True)

    print("--- Cleaning summary ---")
    print(f"Rows dropped (missing name/set/date): {dropped_missing_essentials}")
    print(f"Rows dropped (unparseable date):       {dropped_bad_dates}")
    print(f"Rows dropped (duplicate id):            {dropped_duplicates}")
    print(f"Final row count:                        {len(df)}")
    print(f"Final column count:                     {df.shape[1]}")

    return df


def main():
    df = load_and_clean()
    os.makedirs(os.path.dirname(PROCESSED_PATH), exist_ok=True)
    df.to_csv(PROCESSED_PATH, index=False)
    print(f"Saved cleaned data to {PROCESSED_PATH}")


if __name__ == "__main__":
    main()
