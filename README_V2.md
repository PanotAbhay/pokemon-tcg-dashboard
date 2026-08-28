# Pokémon TCG Card Explorer

## Data Overview

The Pokémon TCG Card Explorer uses the **Pokémon TCG All Cards 1999–2023** dataset from Kaggle. The dataset contains **17,172 cards**, covering **156 sets** and **16 series**, with card information from 1999 to 2023.

The product displays:
- Card name
- Set and series
- Rarity
- Pokémon type
- Supertype
- HP
- Artist
- Release date
- Card counts and average HP
- Rarity, type, set, and yearly distribution statistics

The data requires basic processing before use. The raw CSV contains 29 columns, including nested fields that are not required by the dashboard. The processing pipeline removes unnecessary nested columns, converts stringified type lists into usable type fields, converts release dates into a consistent format, handles legitimate missing HP values for Trainer and Energy cards, removes invalid rows, and checks for duplicate card IDs. The processed dataset contains 15 columns used by the product.

The dataset contains card attributes only. It does **not** contain card pricing information.

## Product Architecture

### Architecture Diagram

```text
                    ┌──────────────────────────┐
                    │      Raw CSV Dataset     │
                    │    Pokémon TCG 1999–2023 │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │     pandas Processing    │
                    │    server/data_loader.py │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │    Processed CSV / DB    │
                    │       Data Storage       │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │       Flask Server       │
                    │        server/app.py     │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
              /api/cards   /api/filters   /api/stats/*
                    │            │            │
                    └────────────┼────────────┘
                                 │ JSON
                                 ▼
                    ┌──────────────────────────┐
                    │       Web Client         │
                    │ HTML + CSS + JavaScript  │
                    │        + Chart.js        │
                    └──────────────────────────┘
```

### Components and Interactions

**Data processing:** Python with pandas is used in `server/data_loader.py` to clean and prepare the raw CSV.

**Server:** Python Flask is used in `server/app.py`. The server loads the processed data and provides JSON APIs for the web client. Flask-CORS allows the client and server to run on different local ports.

**Web client:** The client uses **HTML, CSS, and vanilla JavaScript**. JavaScript uses `fetch()` to request JSON from Flask and Chart.js to display the data visually.

### Three Main API Functions

1. **Cards API: `/api/cards`**
   - Returns the card catalogue as JSON.
   - Supports search, filtering, sorting, and pagination.
   - Filters include name, set, series, rarity, type, supertype, release year, and HP.

2. **Filters API: `/api/filters`**
   - Returns the available values for filter fields.
   - The web client uses these values to populate its filter controls.

3. **Statistics API: `/api/stats/*`**
   - Provides calculated dashboard statistics.
   - The client uses the statistics endpoints for overview figures and charts such as rarity, type, set, and yearly card counts.

## Instructions for Running the Product and Pushing Code to Git

### 1. Start the Flask Server

Open PowerShell or Command Prompt and enter the project folder:

```powershell
cd pokemon-tcg-dashboard
```

Install the required Python libraries:

```powershell
python -m pip install -r server\requirements.txt
```

Generate the processed data:

```powershell
cd server
python data_loader.py
```

Start the Flask server:

```powershell
python app.py
```

The Flask API will run at:

```text
http://127.0.0.1:5000
```

Keep this terminal running.

### 2. Run the HTML Web Client

Open a second PowerShell or Command Prompt window:

```powershell
cd pokemon-tcg-dashboard\client
python -m http.server 8000
```

Open the following address in a browser:

```text
http://127.0.0.1:8000
```

The HTML client communicates with the Flask server through the API at:

```text
http://127.0.0.1:5000/api
```

### 3. Select and Use Filters

Use the dashboard filter controls to:
1. Search for a Pokémon by name.
2. Select a card type.
3. Select a series.
4. Select a set.
5. Select a rarity.
6. Select a release-year range.
7. Select sorting options such as name, release date, HP, set, or rarity.
8. Combine multiple filters at the same time.

The filters are chainable. The card catalogue and dashboard results update according to the selected filters.

To return to the full catalogue, clear the selected filters.

### 4. Push the Project to Git

From the project root:

```powershell
cd pokemon-tcg-dashboard
git init
git add .
git commit -m "Initial Pokémon TCG Card Explorer project"
```

Connect the local repository to a GitHub repository:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
```

Push the project:

```powershell
git branch -M main
git push -u origin main
```

For later changes:

```powershell
git add .
git commit -m "Describe the changes"
git push
```

## Requirements: Installed Libraries and Versions

The project uses the following libraries and version ranges specified in `server/requirements.txt`:

| Library | Version |
|---|---|
| Flask | 3.0 or higher, below 4.0 |
| Flask-CORS | 4.0 or higher, below 7.0 |
| pandas | 2.0 or higher, below 3.0 |
| Gunicorn | 21 or higher, below 24 |
| Chart.js | Used in the web client through CDN |

The Python project uses version ranges rather than exact pinned package versions, so the exact installed patch version may depend on when `pip install -r server/requirements.txt` is run.

## Code: Languages Used

- **Python** — data processing and Flask server/API
- **HTML** — web client structure
- **CSS** — web client styling and responsive layout
- **JavaScript** — client-side API requests, filtering, interaction, and chart rendering
