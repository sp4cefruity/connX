Connecting hearts, hearts so much bigger than maps.

ConnX compares two trips and shows how much they overlap and where they come
close. Pick a travel mode (driving, walking or cycling), enter your route and
the route to avoid, then set a danger distance. The map shows both routes, the
shared stretches, a red zone band around their route and a marker (with the
gap in metres) wherever you pass within the danger distance. You can also draw
red spots (circles Route A should stay out of) and ask for a recommended
alternative.

![Dark theme, driving comparison with a red spot hit](docs/screenshots/dark-driving.png)

![Light theme](docs/screenshots/light-driving.png)

On a phone the side panel becomes a bottom sheet:

<img src="docs/screenshots/mobile-light-sheet.png" alt="Mobile layout" width="280">

## Quick start (no Docker, no Postgres)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env   # SQLite by default; Windows: copy
cd frontend && npm ci && cd ..
python run_all.py                  # backend :8000, frontend :3000
```

Open http://localhost:3000. Routing and search use public fair-use servers
(routing.openstreetmap.de, Photon, Nominatim), so you need an internet
connection. Set `ROUTING_PROVIDER=mock` / `GEOCODING_PROVIDER=mock` in
`backend/.env` to work offline with canned data.

## Scope

**Working today**

- Compare two trips in driving, walking or cycling: overlap, red zone band,
  encounters within the danger distance.
- Red spots (circles Route A should avoid), saved per anonymous cookie user.
- Recommended alternatives, ranked by time, distance, overlap, encounters and
  red spot hits, with a hand-off to Google Maps.
- Routing: OpenRouteService when `ORS_API_KEY` is set, otherwise (or when ORS
  fails or runs out of quota) public OSRM servers, one per travel mode.
- Search: Photon, then LocationIQ (if `LOCATIONIQ_API_KEY` is set), then
  Nominatim. Nominatim also does reverse geocoding.
- Light and dark themes, and a mobile bottom-sheet layout.

**Parked (code kept, not wired in)**

- Self-hosted Valhalla routing (ADR 0007, `backend/app/routing/valhalla.py`,
  `scripts/valhalla-setup.sh`). It would remove the dependence on rationed
  public routing servers. The commented-out `valhalla` service in
  `docker-compose.yml` is for this.

**Out of scope**

- Departure times and schedules (spatial only), accounts or sharing (users are
  anonymous), storing trips (only red spots are saved).
- Hosting and deployment (see `docs/PRD.md`).

## Known issues

- Public routing and geocoding servers have no SLA. When they are slow the app
  shows "Search is slow right now" or a route error; try again.
- Recommend builds its own detours when the servers return too few
  alternatives (ADR 0006). With an `ORS_API_KEY` it asks the router to keep out
  of Route B's road. On OSRM alone it can only steer with via points, which do
  not help on a long shared highway; it then says "No better route found
  nearby", as it does where there is no other road to take.
- On a phone, the map is fitted while the bottom sheet is open, so the ends of
  a long route can sit under the sheet or off the top. Collapse the sheet and
  pan to see them.
- Encounters right next to an overlap stretch (the approach and the exit of a
  shared road) are still listed. Whether to hide them is an open design choice.
- The Docker setup (`docker compose up --build`) was last run before the
  Photon, LocationIQ and per-mode routing changes. The compose file has been
  updated to match, but treat it as untested until you have run it once.


## First-time setup

Versions are pinned so everyone gets identical packages.

**Prerequisites**

- Python 3.12 (reference; matches the Docker image). 3.13 and 3.14 are verified too.
- Node 20 or newer (`.nvmrc` says 20) with npm 10 or newer.

**Install** (from the repo root)

```bash
# Backend: create a virtualenv and install the pinned packages
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# Frontend: `npm ci` installs exactly what package-lock.json says
cd frontend && npm ci && cd ..
```

**Check it works**

```bash
cd backend && python -m pytest     # backend tests
cd ../frontend && npm run lint && npm run build
```

Use `npm ci` (not `npm install`) so the lockfile is never rewritten. When you
deliberately upgrade a package, change its pinned version, run the checks
above, and commit `requirements.txt` / `package.json` / `package-lock.json`
together.

## Running ConnX

Three ways to run the stack - pick whichever fits your situation.

### 1. Everything in Docker

```bash
docker compose up --build
```

- Backend: http://localhost:8000 (FastAPI docs at `/docs`)
- Postgres: localhost:5432 (schema from `backend/init.sql`, data kept in the
  `connx_db_data` volume)
- The backend container needs internet access for routing and search.
- Optional settings are read from your shell or a `.env` file next to
  `docker-compose.yml`: `ORS_API_KEY`, `LOCATIONIQ_API_KEY`,
  `NOMINATIM_USER_AGENT` (use a real contact address), `ROUTING_PROVIDER`
  and `GEOCODING_PROVIDER`. Without keys it runs on public OSRM, Photon and
  Nominatim.
- Frontend stays native by default for a fast dev loop; add the optional containerized frontend with:

```bash
docker compose --profile full up --build   # adds Next.js on :3000
```

### 2. Postgres without Docker

Install PostgreSQL locally, create a database, then point `backend/.env` at it:

```env
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/connx
```

Apply the schema (optional - SQLAlchemy also auto-creates tables on startup):

```bash
psql -U user -d connx -f backend/init.sql
```

Then run the backend from `backend/`:

```bash
pip install -r requirements.txt
python app/main.py
```

### 3. Local dev with no Docker and no Postgres (SQLite)

Zero infrastructure needed - SQLite just works because all spatial math runs
in Python (Shapely), not in the database:

```bash
python run_all.py    # starts backend (:8000) + frontend (:3000)
```

`run_all.py` checks DB reachability first and tells you exactly how to fix it
if something's wrong. For SQLite-only mode, make sure `backend/.env` contains:

```env
DATABASE_URL=sqlite:///./connx_dev.db
```

(see `backend/.env.example`; copy it to `backend/.env` first, because the
built-in default is Postgres).

## Collaborating across machines

In development mode the backend's CORS accepts **any** port on
`localhost` / `127.0.0.1`, so nobody needs matching ports or manual
`FRONTEND_ORIGIN` syncing - if your `npm run dev` lands on 3001 instead of
3000, everything still works. Production builds lock CORS down to the exact
`FRONTEND_ORIGIN`, so set that properly when deploying.
