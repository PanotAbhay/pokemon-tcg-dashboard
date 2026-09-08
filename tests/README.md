# Tests

Manual API test suite for `server/app.py`, run via Postman (not automated/CI — see note below).

## Contents

- `postman_collection.json` — Postman v2.1 collection covering every route in `server/app.py`: `/api/health`, `/api/filters`, `/api/cards` (list, search, filters, sorting, pagination, error cases), `/api/cards/<id>`, and all `/api/stats/*` endpoints.

## Running it

1. Start the server: `python server/app.py` (serves on `http://127.0.0.1:5000`).
2. In Postman: File > Import > select `tests/postman_collection.json`.
3. Set the collection variable `cardId` to a real card id from `data/processed/pokemon_cards_clean.csv` (e.g. `base1-1`).
4. Run requests individually, or use the collection's "Run" button to execute the whole folder tree in order.

## What to check per response

- Status code: `200` for all requests except the two deliberate error cases (`sort_by=not_a_column` → `400`, `cards/does-not-exist` → `404`).
- Trainer/Energy cards must have `hp`/`retreat_cost` as JSON `null`, never `0`.
- `/api/stats/by-set?limit=0` → `[]`; `limit=-1` → full list.
- Filtered `/api/cards` results actually match the filters applied.

## Automating this later

This is a manual suite — nothing here runs without a person clicking through Postman. To make it part of CI:

- **Newman** (Postman's CLI runner) can execute `postman_collection.json` headlessly and apply pass/fail assertions, but the collection currently has no test scripts (`pm.test(...)`) attached to requests — those would need to be added first.
- Alternatively, a Python suite (`pytest` + `requests`) against a running Flask instance would fit this repo's existing Python tooling more directly.
