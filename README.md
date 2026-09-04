# Pokémon TCG Card Explorer

A dashboard for browsing and analysing the Pokémon Trading Card Game catalog from 1999–2023.

---

## 1. Data overview

**Source:** [Pokémon TCG All Cards 1999–2023](https://www.kaggle.com/datasets/adampq/pokemon-tcg-all-cards-1999-2023) (Kaggle) — 17,172 rows, 29 raw columns, 156 sets, 16 series.

The dataset holds card *attributes* only (name, set, series, rarity, type, HP, artist, release date) — no pricing data. The product is a two-tab dashboard:
- **Search** (filterable/searchable/sortable card catalog with pagination)
- **Statistics** (default tab) — a headline stat strip (total cards, sets, series, artists, avg HP) plus four charts: top 10 card rarities, cards by energy type, cards printed per year, and top artists by card count.

**Processing (`server/data_loader.py`):**
- Dropped 14 deeply-nested columns not needed here (`abilities`, `attacks`, `legalities`, etc.), keeping 15 processed columns.
- `types`/`subtypes` arrive as stringified Python lists (e.g. `"['Fire', 'Flying']"`) — parsed with `ast.literal_eval` into scalar `primary_type` and `types_display` columns for filtering/charting.
- `hp` and `retreat_cost` are legitimately null for Trainer/Energy cards — left as `null` (not imputed to 0, which would misread as "0 HP"). The API converts `NaN` to JSON `null`.
- Rows missing `name`, `set`, or an unparseable `release_date` are dropped (0 rows affected — source was already clean). Deduplicated on `id` (0 duplicates found).
- `"Rare Ultra"` is merged into `"Ultra Rare"` — the same rarity tier appeared under two name orders in the source data.

## 2. Architecture

```
Browser (client/) ──fetch──▶ Flask app (server/app.py) ──pandas──▶ processed CSV (in-memory)
     HTML/CSS/JS                 /api/* REST endpoints              data/processed/pokemon_cards_clean.csv
```

Flask serves the client's static files directly (`GET /` → `client/index.html`) and exposes the JSON API under `/api`, so one server process handles both. `server/data_loader.py` is a one-off pandas pipeline that turns the raw CSV into the cleaned CSV loaded into memory at Flask startup.

**API groups** (`server/app.py`):

| Group | Endpoints | Function |
|---|---|---|
| Cards | `GET /api/cards`, `GET /api/cards/<id>` | Paginated, filtered, sorted card list (see query params below) and single-card lookup |
| Filters | `GET /api/filters` | Distinct values per filterable field (plus a `series_sets` map of series → its sets), for populating dropdowns |
| Stats | `GET /api/stats/overview`, `by-rarity`, `by-type`, `by-set`, `by-year`, `by-artist` | Aggregated counts/averages powering the stat strip and charts |

Plus `GET /api/health` for a liveness check.

**`/api/cards` query params:** `q` (name substring), `set`, `series`, `rarity`, `type`, `supertype`, `generation` (exact match; repeat the param for multiple values, e.g. `type=Fire&type=Water`), `year_from`/`year_to`, `hp_min`/`hp_max`, `sort_by`, `order` (`asc`/`desc`), `page`, `page_size` (max 200). Errors return `{"error": "..."}` with `400`/`404`.

**Languages/frameworks:**
- Data pipeline & server: **Python** (pandas, Flask, Flask-CORS)
- Client: **HTML, CSS, vanilla JavaScript**, with Chart.js for charts

## 3. Running the product

```bash
pip install -r requirements.txt
cd server
python data_loader.py   # generate the cleaned CSV (once, or after changing data_loader.py)
python app.py            # starts Flask on http://127.0.0.1:5000
```

Open **http://127.0.0.1:5000** in a browser — Flask serves the client and API together, so no second server is needed. The page opens on the **Statistics** tab by default; click **Search** to switch to the card catalog.

**Filters:** on the Search tab, use the search box, the multi-select dropdowns (card type, series, set, rarity, energy type — each lets you check multiple values), and the year range; they combine and re-query `/api/cards` automatically. Selecting one or more series narrows the Set dropdown to only the sets belonging to those series (e.g. selecting "Black & White" narrows Set to sets like "Legendary Treasures"). Clear all with the "clear filters" action shown in the empty state.

**Exposing it publicly with ngrok:** with `python app.py` still running locally on port 5000, in a separate terminal run:
```bash
ngrok http 5000
```
ngrok prints a public `https://*.ngrok-free.app` URL — open that URL in a browser to reach the same Flask app (client + API) from anywhere. Since Flask serves the client itself, no separate tunnel or client redeploy is needed.

**Pushing code to Git:**
```bash
git add <files>
git commit -m "your message"
git push
```

## 4. Libraries

| Library | Version | Layer |
|---|---|---|
| Flask | 3.0.3 | Server |
| flask-cors | 4.0.1 | Server |
| pandas | 2.2.2 | Data / Server |
| Chart.js | 4.4.4 (via jsDelivr CDN) | Client |
