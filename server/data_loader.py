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
    "set_num",
]

# Printed total (the denominator shown on a card, e.g. the "102" in "1/102") for
# each set. This is a per-set fact rather than a per-card one, so unlike rarity
# it doesn't need one override per row: it's sourced wholesale from the
# TCGdex API's `cardCount.official` field (https://api.tcgdex.net/v2/en/sets),
# matched to this dataset's set names, and confirmed against known values
# (Base Set 102, Jungle 64, Fossil 62, ...). Secret/hidden rares in a set
# legitimately have a raw `set_num` greater than this total (e.g. "108/102")
# — that's how those cards are actually printed, not a data error.
SET_TOTALS = {
    '151': 165,
    'Ancient Origins': 98,
    'Aquapolis': 147,
    'Arceus': 99,
    'Astral Radiance': 189,
    'Astral Radiance Trainer Gallery': 30,
    'BREAKpoint': 122,
    'BREAKthrough': 162,
    'BW Black Star Promos': 101,
    'Base': 102,
    'Base Set 2': 130,
    'Battle Styles': 163,
    'Best of Game': 9,
    'Black & White': 114,
    'Boundaries Crossed': 149,
    'Brilliant Stars': 172,
    'Brilliant Stars Trainer Gallery': 30,
    'Burning Shadows': 147,
    'Call of Legends': 95,
    'Celebrations': 25,
    'Celebrations: Classic Collection': 25,
    'Celestial Storm': 168,
    "Champion's Path": 73,
    'Chilling Reign': 198,
    'Cosmic Eclipse': 236,
    'Crimson Invasion': 111,
    'Crown Zenith': 159,
    'Crown Zenith Galarian Gallery': 70,
    'Crystal Guardians': 100,
    'DP Black Star Promos': 56,
    'Dark Explorers': 108,
    'Darkness Ablaze': 189,
    'Delta Species': 113,
    'Deoxys': 107,
    'Detective Pikachu': 18,
    'Diamond & Pearl': 130,
    'Double Crisis': 34,
    'Dragon': 97,
    'Dragon Frontiers': 101,
    'Dragon Majesty': 70,
    'Dragon Vault': 20,
    'Dragons Exalted': 124,
    'EX Trainer Kit 2 Minun': 12,
    'EX Trainer Kit 2 Plusle': 12,
    'EX Trainer Kit Latias': 10,
    'EX Trainer Kit Latios': 10,
    'Emerald': 106,
    'Emerging Powers': 98,
    'Evolutions': 108,
    'Evolving Skies': 203,
    'Expedition Base Set': 165,
    'Fates Collide': 124,
    'FireRed & LeafGreen': 112,
    'Flashfire': 106,
    'Forbidden Light': 131,
    'Fossil': 62,
    'Furious Fists': 111,
    'Fusion Strike': 264,
    'Generations': 83,
    'Great Encounters': 106,
    'Guardians Rising': 145,
    'Gym Challenge': 132,
    'Gym Heroes': 132,
    'HGSS Black Star Promos': 25,
    'HeartGold & SoulSilver': 123,
    'Hidden Fates': 68,
    'Hidden Legends': 101,
    'Holon Phantoms': 110,
    'Jungle': 64,
    'Kalos Starter Set': 39,
    'Legend Maker': 92,
    'Legendary Collection': 110,
    'Legendary Treasures': 113,
    'Legends Awakened': 146,
    'Lost Origin': 196,
    'Lost Origin Trainer Gallery': 30,
    'Lost Thunder': 214,
    'Majestic Dawn': 100,
    "McDonald's Collection 2011": 12,
    "McDonald's Collection 2012": 12,
    "McDonald's Collection 2014": 12,
    "McDonald's Collection 2015": 12,
    "McDonald's Collection 2016": 12,
    "McDonald's Collection 2017": 12,
    "McDonald's Collection 2018": 12,
    "McDonald's Collection 2019": 12,
    "McDonald's Collection 2021": 25,
    "McDonald's Collection 2022": 15,
    'Mysterious Treasures': 123,
    'Neo Destiny': 105,
    'Neo Discovery': 75,
    'Neo Genesis': 111,
    'Neo Revelation': 64,
    'Next Destinies': 99,
    'Nintendo Black Star Promos': 40,
    'Noble Victories': 101,
    'Obsidian Flames': 197,
    'POP Series 1': 17,
    'POP Series 2': 17,
    'POP Series 3': 17,
    'POP Series 4': 17,
    'POP Series 5': 17,
    'POP Series 6': 17,
    'POP Series 7': 17,
    'POP Series 8': 17,
    'POP Series 9': 17,
    'Paldea Evolved': 193,
    'Paradox Rift': 182,
    'Phantom Forces': 119,
    'Plasma Blast': 101,
    'Plasma Freeze': 116,
    'Plasma Storm': 135,
    'Platinum': 127,
    'Pokémon Futsal Collection': 5,
    'Pokémon GO': 78,
    'Pokémon Rumble': 16,
    'Power Keepers': 108,
    'Primal Clash': 160,
    'Rebel Clash': 192,
    'Rising Rivals': 111,
    'Roaring Skies': 108,
    'Ruby & Sapphire': 109,
    'SM Black Star Promos': 248,
    'SWSH Black Star Promos': 307,
    'Sandstorm': 100,
    'Scarlet & Violet': 198,
    'Scarlet & Violet Black Star Promos': 225,
    'Scarlet & Violet Energies': 24,
    'Secret Wonders': 132,
    'Shining Fates': 72,
    'Shining Legends': 73,
    'Silver Tempest': 195,
    'Silver Tempest Trainer Gallery': 30,
    'Skyridge': 144,
    'Southern Islands': 18,
    'Steam Siege': 114,
    'Stormfront': 100,
    'Sun & Moon': 149,
    'Supreme Victors': 147,
    'Sword & Shield': 202,
    'Team Magma vs Team Aqua': 95,
    'Team Rocket': 82,
    'Team Rocket Returns': 109,
    'Team Up': 181,
    'Triumphant': 102,
    'Ultra Prism': 156,
    'Unbroken Bonds': 214,
    'Undaunted': 90,
    'Unified Minds': 236,
    'Unleashed': 95,
    'Unseen Forces': 115,
    'Vivid Voltage': 185,
    'Wizards Black Star Promos': 53,
    'XY': 146,
    'XY Black Star Promos': 211,
}

# "Shiny Vault" in the source data merges two distinct real-world subsets that
# both happen to use an "SV" number prefix: Hidden Fates' Shiny Vault (94
# cards, id prefix "sma-") and Shining Fates' Shiny Vault (122 cards, id
# prefix "swsh45sv-"). They need to be split by id prefix to get the right
# printed total for each half.
SHINY_VAULT_TOTALS = {
    "sma-": 94,
    "swsh45sv-": 122,
}


def _set_total(row):
    """
    Printed total for a card's set, for building the "num/total" set_number
    display. Returns None for sets with no fixed printed total (Black Star
    Promos and similar) or non-numeric set_num values (H1, SV1, ...), which
    follow their own sub-numbering rather than the main set's.
    """
    if row["set"] == "Shiny Vault":
        for prefix, total in SHINY_VAULT_TOTALS.items():
            if row["id"].startswith(prefix):
                return total
        return None
    return SET_TOTALS.get(row["set"])


def _reorder_rare_label(rarity):
    """
    Rarities of the form "Rare X" (e.g. "Rare Rainbow", "Rare Secret", "Rare Holo")
    read backwards — move "Rare" to the end so it reads "X Rare" ("Rainbow Rare",
    "Secret Rare", "Holo Rare", ...). Rarities that already end in "Rare" (plain
    "Rare", "Ultra Rare") are left untouched.
    """
    words = rarity.split(" ")
    if len(words) > 1 and "Rare" in words and words[-1] != "Rare":
        return " ".join([w for w in words if w != "Rare"] + ["Rare"])
    return rarity


def _capitalize_first_letters(name):
    """
    Uppercase just the first letter of each space-separated word in a name
    (e.g. "james turner" -> "James Turner"), leaving the rest of each word
    untouched so mixed-case pseudonyms/studio names (e.g. "aky CG Works")
    aren't mangled by a full title-case pass.
    """
    return " ".join(w[:1].upper() + w[1:] if w else w for w in name.split(" "))


# Rarity is null in the source data for every card belonging to these Trainer
# Kits, promotional sets, and basic-Energy checklists (they were printed without
# a rarity symbol). Verified individually against TCGplayer / Serebii / Bulbapedia
# / official pokemon.com card pages rather than left as "Unknown" (no such rarity
# exists in the actual card game): basic Energy reprints in early sets are
# "Common", Southern Islands / EX Trainer Kits / Pokemon Rumble / McDonald's
# Collection / Pokemon Futsal Collection cards are "Promo", the Kalos Starter
# Set is "Common", and Dragon Vault's Exp. Share / First Ticket / Kyurem are
# "Rare Holo" / "Rare Holo" / "Secret Rare" respectively.
RARITY_OVERRIDES = {
    "base1-97": "Common", "base1-98": "Common", "base1-99": "Common",
    "base1-100": "Common", "base1-101": "Common", "base1-102": "Common",
    "base4-125": "Common", "base4-126": "Common", "base4-127": "Common",
    "base4-128": "Common", "base4-129": "Common", "base4-130": "Common",
    "gym1-127": "Common", "gym1-128": "Common", "gym1-129": "Common",
    "gym1-130": "Common", "gym1-131": "Common", "gym1-132": "Common",
    "gym2-127": "Common", "gym2-128": "Common", "gym2-129": "Common",
    "gym2-130": "Common", "gym2-131": "Common", "gym2-132": "Common",
    "neo1-106": "Common", "neo1-107": "Common", "neo1-108": "Common",
    "neo1-109": "Common", "neo1-110": "Common", "neo1-111": "Common",
    "ecard1-160": "Common", "ecard1-161": "Common", "ecard1-162": "Common",
    "ecard1-163": "Common", "ecard1-164": "Common", "ecard1-165": "Common",
    "si1-1": "Promo", "si1-2": "Promo", "si1-3": "Promo", "si1-4": "Promo",
    "si1-5": "Promo", "si1-6": "Promo", "si1-7": "Promo", "si1-8": "Promo",
    "si1-9": "Promo", "si1-10": "Promo", "si1-11": "Promo", "si1-12": "Promo",
    "si1-13": "Promo", "si1-14": "Promo", "si1-15": "Promo", "si1-16": "Promo",
    "si1-17": "Promo", "si1-18": "Promo",
    "tk1a-1": "Promo", "tk1b-1": "Promo", "tk1a-2": "Promo", "tk1b-2": "Promo",
    "tk1a-3": "Promo", "tk1b-3": "Promo", "tk1a-4": "Promo", "tk1b-4": "Promo",
    "tk1a-5": "Promo", "tk1b-5": "Promo", "tk1a-6": "Promo", "tk1b-6": "Promo",
    "tk1a-7": "Promo", "tk1b-7": "Promo", "tk1a-8": "Promo", "tk1b-8": "Promo",
    "tk1a-9": "Promo", "tk1b-9": "Promo", "tk1a-10": "Promo", "tk1b-10": "Promo",
    "tk2a-1": "Promo", "tk2b-1": "Promo", "tk2a-2": "Promo", "tk2b-2": "Promo",
    "tk2a-3": "Promo", "tk2a-4": "Promo", "tk2b-4": "Promo", "tk2a-5": "Promo",
    "tk2b-5": "Promo", "tk2a-6": "Promo", "tk2b-6": "Promo", "tk2a-7": "Promo",
    "tk2b-7": "Promo", "tk2a-8": "Promo", "tk2b-8": "Promo", "tk2a-9": "Promo",
    "tk2b-9": "Promo", "tk2a-10": "Promo", "tk2b-10": "Promo", "tk2a-11": "Promo",
    "tk2b-11": "Promo", "tk2a-12": "Promo", "tk2b-12": "Promo",
    "ru1-1": "Promo", "ru1-2": "Promo", "ru1-3": "Promo", "ru1-4": "Promo",
    "ru1-5": "Promo", "ru1-6": "Promo", "ru1-7": "Promo", "ru1-8": "Promo",
    "ru1-9": "Promo", "ru1-10": "Promo", "ru1-11": "Promo", "ru1-12": "Promo",
    "ru1-13": "Promo", "ru1-14": "Promo", "ru1-15": "Promo", "ru1-16": "Promo",
    "mcd11-1": "Promo", "mcd11-2": "Promo", "mcd11-3": "Promo", "mcd11-4": "Promo",
    "mcd11-5": "Promo", "mcd11-6": "Promo", "mcd11-7": "Promo", "mcd11-8": "Promo",
    "mcd11-9": "Promo", "mcd11-10": "Promo", "mcd11-11": "Promo", "mcd11-12": "Promo",
    "mcd12-1": "Promo", "mcd12-2": "Promo", "mcd12-3": "Promo", "mcd12-4": "Promo",
    "mcd12-5": "Promo", "mcd12-6": "Promo", "mcd12-7": "Promo", "mcd12-8": "Promo",
    "mcd12-9": "Promo", "mcd12-10": "Promo", "mcd12-11": "Promo", "mcd12-12": "Promo",
    "dv1-18": "Rare Holo", "dv1-19": "Rare Holo", "dv1-21": "Secret Rare",
    "xy0-1": "Common", "xy0-2": "Common", "xy0-3": "Common", "xy0-4": "Common",
    "xy0-5": "Common", "xy0-6": "Common", "xy0-7": "Common", "xy0-8": "Common",
    "xy0-9": "Common", "xy0-10": "Common", "xy0-11": "Common", "xy0-12": "Common",
    "xy0-13": "Common", "xy0-14": "Common", "xy0-15": "Common", "xy0-16": "Common",
    "xy0-17": "Common", "xy0-18": "Common", "xy0-19": "Common", "xy0-20": "Common",
    "xy0-21": "Common", "xy0-22": "Common", "xy0-23": "Common", "xy0-24": "Common",
    "xy0-25": "Common", "xy0-26": "Common", "xy0-27": "Common", "xy0-28": "Common",
    "xy0-29": "Common", "xy0-30": "Common", "xy0-31": "Common", "xy0-32": "Common",
    "xy0-33": "Common", "xy0-34": "Common", "xy0-35": "Common", "xy0-36": "Common",
    "xy0-37": "Common", "xy0-38": "Common", "xy0-39": "Common",
    "mcd14-1": "Promo", "mcd14-2": "Promo", "mcd14-3": "Promo", "mcd14-4": "Promo",
    "mcd14-5": "Promo", "mcd14-6": "Promo", "mcd14-7": "Promo", "mcd14-8": "Promo",
    "mcd14-9": "Promo", "mcd14-10": "Promo", "mcd14-11": "Promo", "mcd14-12": "Promo",
    "mcd15-1": "Promo", "mcd15-2": "Promo", "mcd15-3": "Promo", "mcd15-4": "Promo",
    "mcd15-5": "Promo", "mcd15-6": "Promo", "mcd15-7": "Promo", "mcd15-9": "Promo",
    "mcd15-10": "Promo", "mcd15-11": "Promo", "mcd15-12": "Promo",
    "mcd16-1": "Promo", "mcd16-2": "Promo", "mcd16-3": "Promo", "mcd16-4": "Promo",
    "mcd16-5": "Promo", "mcd16-6": "Promo", "mcd16-7": "Promo", "mcd16-8": "Promo",
    "mcd16-9": "Promo", "mcd16-10": "Promo", "mcd16-11": "Promo", "mcd16-12": "Promo",
    "mcd17-1": "Promo", "mcd17-2": "Promo", "mcd17-3": "Promo", "mcd17-4": "Promo",
    "mcd17-5": "Promo", "mcd17-6": "Promo", "mcd17-7": "Promo", "mcd17-8": "Promo",
    "mcd17-9": "Promo", "mcd17-10": "Promo", "mcd17-11": "Promo", "mcd17-12": "Promo",
    "mcd18-1": "Promo", "mcd18-2": "Promo", "mcd18-3": "Promo", "mcd18-4": "Promo",
    "mcd18-5": "Promo", "mcd18-6": "Promo", "mcd18-7": "Promo", "mcd18-8": "Promo",
    "mcd18-9": "Promo", "mcd18-10": "Promo", "mcd18-11": "Promo", "mcd18-12": "Promo",
    "mcd19-1": "Promo", "mcd19-2": "Promo", "mcd19-3": "Promo", "mcd19-4": "Promo",
    "mcd19-5": "Promo", "mcd19-6": "Promo", "mcd19-7": "Promo", "mcd19-8": "Promo",
    "mcd19-9": "Promo", "mcd19-10": "Promo", "mcd19-11": "Promo", "mcd19-12": "Promo",
    "fut20-1": "Promo", "fut20-2": "Promo", "fut20-3": "Promo", "fut20-4": "Promo",
    "fut20-5": "Promo",
    "mcd21-1": "Promo", "mcd21-2": "Promo", "mcd21-3": "Promo", "mcd21-4": "Promo",
    "mcd21-5": "Promo", "mcd21-6": "Promo", "mcd21-7": "Promo", "mcd21-8": "Promo",
    "mcd21-9": "Promo", "mcd21-10": "Promo", "mcd21-11": "Promo", "mcd21-12": "Promo",
    "mcd21-13": "Promo", "mcd21-14": "Promo", "mcd21-15": "Promo", "mcd21-16": "Promo",
    "mcd21-17": "Promo", "mcd21-18": "Promo", "mcd21-19": "Promo", "mcd21-20": "Promo",
    "mcd21-21": "Promo", "mcd21-22": "Promo", "mcd21-23": "Promo", "mcd21-24": "Promo",
    "mcd21-25": "Promo",
    "mcd22-1": "Promo", "mcd22-2": "Promo", "mcd22-3": "Promo", "mcd22-4": "Promo",
    "mcd22-5": "Promo", "mcd22-6": "Promo", "mcd22-7": "Promo", "mcd22-8": "Promo",
    "mcd22-9": "Promo", "mcd22-10": "Promo", "mcd22-11": "Promo", "mcd22-12": "Promo",
    "mcd22-13": "Promo", "mcd22-14": "Promo", "mcd22-15": "Promo",
}


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
    # Strip/clean only the non-null values, so a real NaN never gets cast to the
    # literal string "nan" first (which a later string-replace would then have to
    # detect and undo — fragile if a genuine value were ever literally "nan").
    for col in ["name", "set", "series", "generation", "publisher", "artist", "rarity", "supertype"]:
        mask = df[col].notna()
        df.loc[mask, col] = df.loc[mask, col].astype(str).str.strip()
        df[col] = df[col].replace({"None": None})

    # Apply manually-verified rarities for cards the source data left null
    # (see RARITY_OVERRIDES above) before falling back to "Unknown" for anything
    # still missing.
    df["rarity"] = df.apply(
        lambda row: RARITY_OVERRIDES.get(row["id"], row["rarity"]), axis=1
    )
    df["rarity"] = df["rarity"].fillna("Unknown")
    # "Rare Ultra" and "Ultra Rare" are the same tier under two different name orders.
    df["rarity"] = df["rarity"].replace({"Rare Ultra": "Ultra Rare"})
    # Canonicalize every other "Rare X" rarity to "X Rare" (e.g. "Rare Holo" -> "Holo Rare").
    df["rarity"] = df["rarity"].apply(_reorder_rare_label)
    df["artist"] = df["artist"].fillna("Unknown")
    df["artist"] = df["artist"].apply(_capitalize_first_letters)

    # Build the "num/total" display set number. set_num (the numerator) comes
    # straight from the source data; the total (denominator) is looked up per
    # set via SET_TOTALS. Only purely-numeric set_num values get a "/total"
    # suffix — promo codes and lettered sub-numbering (H1, SV1, DP01, ...)
    # are shown as-is, since they don't share the main set's total.
    df["set_num"] = df["set_num"].astype(str).str.strip()
    df["_set_total"] = df.apply(_set_total, axis=1)
    df["set_number"] = df.apply(
        lambda row: f"{row['set_num']}/{int(row['_set_total'])}"
        if row["set_num"].isdigit() and pd.notna(row["_set_total"])
        else row["set_num"],
        axis=1,
    )
    df = df.drop(columns=["_set_total"])

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
            "set_number",
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
