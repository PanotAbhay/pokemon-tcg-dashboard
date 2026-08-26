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
    GET /api/stats/by-year    Card count by release year
    GET /api/stats/overview   Headline numbers for the dashboard
"""

import os
import math
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "pokemon_cards_clean.csv")
CLIENT_DIR = os.path.join(os.path.dirname(__file__), "..", "client")

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

@app.route("/")
def serve_client():
    return send_from_directory(CLIENT_DIR, "index.html")
@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "rows_loaded": len(df)})


@app.route("/api/filters")
def filters():
    """Distinct values for building filter dropdowns on the client."""
    return jsonify(
        {
            "sets": sorted(df["set"].dropna().unique().tolist()),
            "series": sorted(df["series"].dropna().unique().tolist()),
            "generations": sorted(df["generation"].dropna().unique().tolist()),
            "rarities": sorted(df["rarity"].dropna().unique().tolist()),
            "types": sorted(df["primary_type"].dropna().unique().tolist()),
            "supertypes": sorted(df["supertype"].dropna().unique().tolist()),
            "year_min": int(df["release_year"].min()),
            "year_max": int(df["release_year"].max()),
        }
    )


@app.route("/api/cards")
def cards():
    """
    List cards with optional filtering, search, sorting and pagination.

    Query params:
        q          substring search on card name (case-insensitive)
        set        exact match on set name
        series     exact match on series name
        rarity     exact match on rarity
        type       exact match on primary_type
        supertype  exact match on supertype (Pokémon/Trainer/Energy)
        year_from  release_year >=
        year_to    release_year <=
        hp_min     hp >=
        hp_max     hp <=
        sort_by    column to sort by (default: name)
        order      asc|desc (default: asc)
        page       1-indexed page number (default: 1)
        page_size  results per page (default: 25, max: 200)
    """
    result = df.copy()

    q = request.args.get("q")
    if q:
        result = result[result["name"].str.contains(q, case=False, na=False)]

    for field, param in [
        ("set", "set"),
        ("series", "series"),
        ("rarity", "rarity"),
        ("primary_type", "type"),
        ("supertype", "supertype"),
        ("generation", "generation"),
    ]:
        val = request.args.get(param)
        if val:
            result = result[result[field] == val]

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
    page_df["release_date"] = page_df["release_date"].dt.strftime("%Y-%m-%d")

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
    record["release_date"] = record["release_date"].dt.strftime("%Y-%m-%d")
    return jsonify(clean_records(record.to_dict(orient="records"))[0])


@app.route("/api/stats/overview")
def stats_overview():
    return jsonify(
        {
            "total_cards": int(len(df)),
            "total_sets": int(df["set"].nunique()),
            "total_series": int(df["series"].nunique()),
            "total_artists": int(df["artist"].nunique()),
            "year_min": int(df["release_year"].min()),
            "year_max": int(df["release_year"].max()),
            "avg_hp": round(float(df["hp"].mean()), 1),
        }
    )


@app.route("/api/stats/by-rarity")
def stats_by_rarity():
    grouped = (
        df.groupby("rarity")
        .agg(card_count=("id", "count"), avg_hp=("hp", "mean"))
        .reset_index()
        .sort_values("card_count", ascending=False)
    )
    grouped["avg_hp"] = grouped["avg_hp"].round(1)
    return jsonify(clean_records(grouped.to_dict(orient="records")))


@app.route("/api/stats/by-type")
def stats_by_type():
    grouped = (
        df.dropna(subset=["primary_type"])
        .groupby("primary_type")
        .agg(card_count=("id", "count"), avg_hp=("hp", "mean"))
        .reset_index()
        .sort_values("card_count", ascending=False)
    )
    grouped["avg_hp"] = grouped["avg_hp"].round(1)
    return jsonify(clean_records(grouped.to_dict(orient="records")))


@app.route("/api/stats/by-set")
def stats_by_set():
    limit = request.args.get("limit", default=20, type=int)
    grouped = (
        df.groupby(["set", "series"])
        .agg(card_count=("id", "count"), avg_hp=("hp", "mean"), release_date=("release_date", "min"))
        .reset_index()
        .sort_values("release_date")
    )
    grouped["avg_hp"] = grouped["avg_hp"].round(1)
    grouped["release_date"] = grouped["release_date"].dt.strftime("%Y-%m-%d")
    if limit:
        grouped = grouped.tail(limit)  # most recent N sets by default
    return jsonify(clean_records(grouped.to_dict(orient="records")))


@app.route("/api/stats/by-year")
def stats_by_year():
    grouped = (
        df.groupby("release_year")
        .agg(card_count=("id", "count"))
        .reset_index()
        .sort_values("release_year")
    )
    return jsonify(clean_records(grouped.to_dict(orient="records")))


if __name__ == "__main__":
    app.run(debug=False, port=5000)
