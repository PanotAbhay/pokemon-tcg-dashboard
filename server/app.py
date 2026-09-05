"""
app.py
------
Flask API for the Pokemon TCG Card Explorer.

Endpoints:
    GET /api/cards            List/search/filter cards (paginated)
    GET /api/cards/<id>       Single card detail
    GET /api/filters          Distinct values for all filterable fields
    GET /api/stats/by-rarity  Card count + avg HP by rarity
    GET /api/stats/by-type    Card count by primary type
    GET /api/stats/by-set     Card count + avg HP by set (top N)
    GET /api/stats/by-artist  Card count by artist (top N)
    GET /api/stats/by-year    Card count by release year
    GET /api/stats/overview   Headline numbers for the dashboard
    GET /api/stats/rarity-by-year   Rarity-tier mix (% of that year's cards) per release year
    GET /api/stats/artist-rarity    Chase-card rate (share of non-base rarities) for top artists
"""

import os
import math
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "pokemon_cards_clean.csv")
CLIENT_DIR = os.path.join(os.path.dirname(__file__), "..", "client")
DATE_FMT = "%Y-%m-%d"

app = Flask(__name__, static_folder=CLIENT_DIR, static_url_path="")
CORS(app)  # enable CORS for all routes so the client can be served separately

# Load once at startup; the dataset is small enough (~17k rows) to keep in memory.
df = pd.read_csv(DATA_PATH, parse_dates=["release_date"])


def clean_records(records):
    """Replace NaN with None so json.dumps doesn't emit invalid NaN literals."""
    for r in records:
        for k, v in r.items():
            if isinstance(v, float) and math.isnan(v):
                r[k] = None
    return records


def error_response(message, status=400):
    return jsonify({"error": message}), status


def distinct_values(column):
    return sorted(df[column].dropna().unique().tolist())


def grouped_stats(source_df, by, avg_hp=True, extra_agg=None, sort_col="card_count", ascending=False):
    """Shared groupby -> count (+ optional avg HP / extra agg) -> sort recipe used by every /api/stats/* route."""
    agg = {"card_count": ("id", "count")}
    if avg_hp:
        agg["avg_hp"] = ("hp", "mean")
    if extra_agg:
        agg.update(extra_agg)
    grouped = source_df.groupby(by).agg(**agg).reset_index().sort_values(sort_col, ascending=ascending)
    if avg_hp:
        grouped["avg_hp"] = grouped["avg_hp"].round(1)
    return grouped


# ---------------------------------------------------------------------------
# Precomputed at startup: `df` never changes after load, so every /api/filters
# and /api/stats/* value below would otherwise be recomputed identically on
# every single request. Routes just serve these cached, already-JSON-safe
# results (sliced by `limit` where the route supports one).
# ---------------------------------------------------------------------------

FILTERS_CACHE = {
    "sets": distinct_values("set"),
    "series": distinct_values("series"),
    "generations": distinct_values("generation"),
    "rarities": distinct_values("rarity"),
    "supertypes": distinct_values("supertype"),
    "artists": distinct_values("artist"),
    "series_sets": (
        df.dropna(subset=["series", "set"])
        .groupby("series")["set"]
        .apply(lambda s: sorted(s.unique().tolist()))
        .to_dict()
    ),
    "year_min": int(df["release_year"].min()),
    "year_max": int(df["release_year"].max()),
}

STATS_OVERVIEW = {
    "total_cards": int(len(df)),
    "total_sets": int(df["set"].nunique()),
    "total_series": int(df["series"].nunique()),
    "total_artists": int(df["artist"].nunique()),
    "year_min": int(df["release_year"].min()),
    "year_max": int(df["release_year"].max()),
    "avg_hp": round(float(df["hp"].mean()), 1),
}

STATS_BY_RARITY = clean_records(grouped_stats(df, "rarity").to_dict(orient="records"))

STATS_BY_TYPE = clean_records(
    grouped_stats(df.dropna(subset=["primary_type"]), "primary_type").to_dict(orient="records")
)

_by_set = grouped_stats(
    df, ["set", "series"], extra_agg={"release_date": ("release_date", "min")}, sort_col="release_date", ascending=True
)
_by_set["release_date"] = _by_set["release_date"].dt.strftime(DATE_FMT)
STATS_BY_SET = clean_records(_by_set.to_dict(orient="records"))  # ascending; routes take the tail for "most recent N"

STATS_BY_ARTIST = clean_records(
    grouped_stats(df[df["artist"] != "Unknown"], "artist", avg_hp=False).to_dict(orient="records")
)

STATS_BY_YEAR = clean_records(
    grouped_stats(df, "release_year", avg_hp=False, sort_col="release_year", ascending=True).to_dict(orient="records")
)

# ---------------------------------------------------------------------------
# Rarity-tier mix over time: share of each year's cards taken up by each of
# the handful of most common rarities, everything else lumped into "Other".
# Powers a 100%-stacked-area chart showing "chase rarity" tiers crowding out
# the base tiers (Common/Uncommon/Rare) as the game has aged.
# ---------------------------------------------------------------------------
_TOP_RARITIES = df["rarity"].value_counts().head(7).index.tolist()

_year_rarity = df[["release_year", "rarity"]].copy()
_year_rarity["rarity_bucket"] = _year_rarity["rarity"].where(_year_rarity["rarity"].isin(_TOP_RARITIES), "Other")
_year_rarity_counts = (
    _year_rarity.groupby(["release_year", "rarity_bucket"]).size().unstack(fill_value=0).sort_index()
)
_year_rarity_pct = _year_rarity_counts.div(_year_rarity_counts.sum(axis=1), axis=0).mul(100).round(1)

STATS_RARITY_BY_YEAR = {
    "years": _year_rarity_pct.index.tolist(),
    "rarities": [*_TOP_RARITIES, "Other"],
    "series": {col: _year_rarity_pct[col].tolist() for col in [*_TOP_RARITIES, "Other"]},
}

# ---------------------------------------------------------------------------
# Chase-card rate per artist: a card is a "chase" print if its printed set
# number exceeds the set's printed total (e.g. "108/102") — the numbering
# scheme sets have used for secret rares, and (in newer sets) some
# Rainbow/Special Illustration Rares that also sit past the main total.
# `set_number` is a display string ("num/total", or a bare code like "H1"
# for promos/sub-numbering with no fixed total); only the "num/total" form
# can be evaluated, so anything else is excluded rather than assumed non-chase.
# Only considers artists with a meaningful body of work.
# ---------------------------------------------------------------------------
_MIN_ARTIST_CARDS = 40


def _is_chase_set_number(set_number):
    num, sep, total = str(set_number).partition("/")
    if not sep or not num.isdigit() or not total.isdigit():
        return None
    return int(num) > int(total)


_artist_df = df.loc[df["artist"] != "Unknown", ["id", "artist", "set_number"]].copy()
_artist_df["is_chase"] = _artist_df["set_number"].apply(_is_chase_set_number)
_artist_df = _artist_df.dropna(subset=["is_chase"])
_artist_df["is_chase"] = _artist_df["is_chase"].astype(bool)
_artist_agg = (
    _artist_df.groupby("artist")
    .agg(card_count=("id", "count"), chase_count=("is_chase", "sum"))
    .reset_index()
)
_artist_agg = _artist_agg[(_artist_agg["card_count"] >= _MIN_ARTIST_CARDS) & (_artist_agg["chase_count"] > 0)]
_artist_agg["chase_pct"] = (_artist_agg["chase_count"] / _artist_agg["card_count"] * 100).round(1)
_artist_agg["base_count"] = _artist_agg["card_count"] - _artist_agg["chase_count"]
_artist_agg = _artist_agg[_artist_agg["chase_pct"] > 5]
_artist_agg = _artist_agg.sort_values("chase_pct", ascending=False)

STATS_ARTIST_RARITY = clean_records(_artist_agg.to_dict(orient="records"))


@app.route("/")
def serve_client():
    return send_from_directory(CLIENT_DIR, "index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "rows_loaded": len(df)})


@app.route("/api/filters")
def filters():
    """Distinct values for building filter dropdowns on the client."""
    return jsonify(FILTERS_CACHE)


@app.route("/api/cards")
def cards():
    """
    List cards with optional filtering, search, sorting and pagination.

    Query params:
        q          substring search on card name (case-insensitive)
        set        exact match on set name (repeatable for multiple sets)
        series     exact match on series name (repeatable)
        rarity     exact match on rarity (repeatable)
        artist     exact match on artist (repeatable)
        supertype  exact match on supertype (Pokémon/Trainer/Energy) (repeatable)
        year_from  release_year >=
        year_to    release_year <=
        hp_min     hp >=
        hp_max     hp <=
        sort_by    column to sort by (default: name)
        order      asc|desc (default: asc)
        page       1-indexed page number (default: 1)
        page_size  results per page (default: 25, max: 200)
    """
    result = df

    q = request.args.get("q")
    if q:
        result = result[result["name"].str.contains(q, case=False, na=False)]

    for field, param in [
        ("set", "set"),
        ("series", "series"),
        ("rarity", "rarity"),
        ("artist", "artist"),
        ("supertype", "supertype"),
        ("generation", "generation"),
    ]:
        values = request.args.getlist(param)
        if values:
            result = result[result[field].isin(values)]

    year_from = request.args.get("year_from", type=int)
    if year_from is not None:
        result = result[result["release_year"] >= year_from]

    year_to = request.args.get("year_to", type=int)
    if year_to is not None:
        result = result[result["release_year"] <= year_to]

    hp_min = request.args.get("hp_min", type=float)
    if hp_min is not None:
        result = result[result["hp"] >= hp_min]

    hp_max = request.args.get("hp_max", type=float)
    if hp_max is not None:
        result = result[result["hp"] <= hp_max]

    sort_by = request.args.get("sort_by", default="name")
    order = request.args.get("order", default="asc")
    if sort_by not in result.columns:
        return error_response(f"Invalid sort_by field: {sort_by}")
    result = result.sort_values(by=sort_by, ascending=(order != "desc"), na_position="last")

    total = len(result)

    page = request.args.get("page", default=1, type=int)
    page_size = request.args.get("page_size", default=25, type=int)
    if page < 1:
        return error_response("page must be >= 1")
    page_size = max(1, min(page_size, 200))

    start = (page - 1) * page_size
    end = start + page_size
    page_df = result.iloc[start:end].copy()
    page_df["release_date"] = page_df["release_date"].dt.strftime(DATE_FMT)

    return jsonify(
        {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, math.ceil(total / page_size)),
            "results": clean_records(page_df.to_dict(orient="records")),
        }
    )


@app.route("/api/cards/<card_id>")
def card_detail(card_id):
    row = df[df["id"] == card_id]
    if row.empty:
        return error_response("Card not found", status=404)
    record = row.copy()
    record["release_date"] = record["release_date"].dt.strftime(DATE_FMT)
    return jsonify(clean_records(record.to_dict(orient="records"))[0])


@app.route("/api/stats/overview")
def stats_overview():
    return jsonify(STATS_OVERVIEW)


@app.route("/api/stats/by-rarity")
def stats_by_rarity():
    return jsonify(STATS_BY_RARITY)


@app.route("/api/stats/by-type")
def stats_by_type():
    return jsonify(STATS_BY_TYPE)


@app.route("/api/stats/by-set")
def stats_by_set():
    limit = request.args.get("limit", default=20, type=int)
    # limit=0 must mean "zero rows", not "no limit" — `if limit:` would treat 0 as falsy.
    records = STATS_BY_SET if limit < 0 else STATS_BY_SET[-limit:] if limit else []
    return jsonify(records)


@app.route("/api/stats/by-artist")
def stats_by_artist():
    limit = request.args.get("limit", default=12, type=int)
    records = STATS_BY_ARTIST if limit < 0 else STATS_BY_ARTIST[:limit]
    return jsonify(records)


@app.route("/api/stats/by-year")
def stats_by_year():
    return jsonify(STATS_BY_YEAR)


@app.route("/api/stats/rarity-by-year")
def stats_rarity_by_year():
    return jsonify(STATS_RARITY_BY_YEAR)


@app.route("/api/stats/artist-rarity")
def stats_artist_rarity():
    limit = request.args.get("limit", default=12, type=int)
    records = STATS_ARTIST_RARITY if limit < 0 else STATS_ARTIST_RARITY[:limit]
    return jsonify(records)


if __name__ == "__main__":
    app.run(debug=False, port=5000)
