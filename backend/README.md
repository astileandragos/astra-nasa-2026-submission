# backend/

Flask API + SQLite. Owner: Blue (Dragoș). Follows `docs/api_contract.md`.

Implemented: health, measurements (POST, latest, history), daily check-in (`/api/journal`), and the analysis endpoints `/api/quality`, `/api/stats/daily`, `/api/baseline`, `/api/observation`, `/api/activity` (docs/api_contract.md sections 6 and 6.7), `/api/status` (freshness for a stale warning), `/api/export.csv` (CSV download) and `/api/reference` (curated external references, 6.8 to 6.10). All analysis endpoints take `?source=` (default `live_hardware`, use `simulated` for the demo) and never mix sources.

## Run it (from the repo root, Git Bash or PowerShell)
```bash
cd backend
python -m venv .venv            # once
source .venv/Scripts/activate   # Git Bash. PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt # once

python init_db.py               # creates astra.db (the server also does this on start)
python app.py                   # server on 0.0.0.0:5000
```
In a second terminal (same venv):
```bash
python simulator.py             # posts a "simulated" reading every 2 seconds
```
Check it:
```bash
curl http://127.0.0.1:5000/api/health
sqlite3 astra.db "select id, received_at, heart_rate_bpm, source from measurements order by id desc limit 5;"   # if sqlite3 is installed
```
Tests: `pytest` (inside `backend/`).

## For the ESP32
Find the laptop IP with `ipconfig` (Wi-Fi adapter, IPv4). The ESP32 posts to `http://<LAPTOP_IP>:5000/api/measurements`. Allow Python through Windows Firewall (private network) when asked.

## Files
- `app.py`: server and validation. `schema.sql`: table. `init_db.py`: creates the database. `simulator.py`: fake data, always `simulated`. `test_app.py`: tests.
- `astra.db` is git-ignored.

## Dashboard
`http://<LAPTOP_IP>:5000/` serves `frontend/index.html` (and the other files in `frontend/`), so the page and the API share one address. In the page's JavaScript call the API with the relative path `/api` (for example `fetch('/api/measurements/latest')`). CORS is also enabled for `/api/*` so a page opened from a file or Live Server can call it too (local demo only).

## Demo data without hardware
```bash
python seed_demo.py                 # 6 earlier days + today of SIMULATED data (device SEED-SIM)
python seed_demo.py --today normal  # today like the other days (also: elevated, lower)
python seed_demo.py --late-bed      # last night's rest starts about 2 hours later (shows the rest observation)
python seed_demo.py --clear         # remove only the seeded data
```
Everything it writes is labelled `simulated`; it never writes `live_hardware` rows and only deletes its own rows. Then open `http://<LAPTOP_IP>:5000/api/observation?source=simulated` or the dashboard with `?source=simulated`. Note: `simulator.py` also posts `simulated` rows (device SIM-01), so running it adds to today's simulated data.

Files: `analysis.py` (statistics and the observation rules), `rest.py` (rest from movement, rest regularity, wear time; contract 6.12 and 6.13), `notices.py` (traffic-light notifications, daily suggestions and advice; contract 6.14), `osdr.py` (search of NASA OSDR study metadata, external; contract 6.16, `docs/OSDR_RESOURCES.md`), `radiation.py` (Radiation Risk Monitor: NOAA GOES proton flux, event detection, alerts, illustrative exposure budget; contract 6.15, `docs/RADIATION_MONITOR.md`), `seed_demo.py`, `test_analysis.py`.

## Logs, errors and the database
- Rejected requests and server errors go to `backend/astra.log` (the field and the reason, never the request body). The file is git-ignored.
- Errors are always JSON (`400`, `404`, `405`, `413` for bodies over 64 KB, `500`), so the ESP32 never has to parse an HTML page.
- SQLite runs in WAL mode so the ESP32 can write while the dashboard reads. You will see `astra.db-wal` and `astra.db-shm` next to `astra.db`; they are git-ignored.
- CSV: `http://<LAPTOP_IP>:5000/api/export.csv?source=simulated&days=7` (add `&kind=journal` for the check-ins). Missing values are empty cells, never 0.
- External references live in `data/reference.json` (not in the database). Add an entry only with facts you read from the source; the server refuses a file with a missing field or a non-https link.
