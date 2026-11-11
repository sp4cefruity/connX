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

## Three ways to run ConnX

| | How | You need |
|---|---|---|
| **1. Hosted** | Open **https://connx3.vercel.app** | A browser |
| **2. Docker** | `docker compose --profile full up --build`, then open http://localhost:3000 | Docker |
| **3. Local** | `python run_all.py`, then open http://localhost:3000 | Python 3.12+ and Node 20+ |

Details for each are under [Running ConnX](#running-connx). Routing and search
use public fair-use servers (routing.openstreetmap.de, Photon, Nominatim), so
every option needs an internet connection. Set `ROUTING_PROVIDER=mock` and
`GEOCODING_PROVIDER=mock` to work offline with canned data.

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
- A free-tier hosted demo (Vercel, Render, Neon) with per-IP rate limits, plus
  Docker and local setups.

**Parked (code kept, not wired in)**

- Self-hosted Valhalla routing (ADR 0007, `backend/app/routing/valhalla.py`,
  `scripts/valhalla-setup.sh`). It would remove the dependence on rationed
  public routing servers. The commented-out `valhalla` service in
  `docker-compose.yml` is for this.

**Out of scope**

- Departure times and schedules (spatial only), accounts or sharing (users are
  anonymous), storing trips (only red spots are saved).
- Scaling beyond a demo: one backend process, in-memory caches and rate limits,
  no monitoring or alerting (see `docs/PRD.md`).

## Known issues

- Public routing and geocoding servers have no SLA. When they are slow the app
  shows "Search is slow right now" or a route error; try again.
- The hosted backend runs on a free Render instance that sleeps after about 15
  idle minutes and takes up to a minute to wake. The landing page wakes it in
  the background, and the planner shows a "Waking up the server" notice while
  it is still starting.
- The hosted demo limits each IP address to 10 route requests and 60 searches
  a minute (a `429` with a "Too many requests" message). The limits are held in
  memory and reset when the backend restarts. They are off in Docker and local
  runs.
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
- "Use my location" calls Nominatim's reverse geocoder straight from the
  browser, without the backend's User-Agent or cache.
- Every visitor without a cookie adds a row to the `users` table; nothing
  prunes it.

## First-time setup (Docker and local)

Versions are pinned so everyone gets identical packages.

**Prerequisites**

- Python 3.12 (reference; matches the Docker image). 3.13 and 3.14 are verified too.
- Node 20 or newer (`.nvmrc` says 20) with npm 10 or newer.
- Docker, only for option 2.

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
cd ../frontend && npm test && npm run lint && npm run build
```

Use `npm ci` (not `npm install`) so the lockfile is never rewritten. When you
deliberately upgrade a package, change its pinned version, run the checks
above, and commit `requirements.txt` / `package.json` / `package-lock.json`
together.

## Running ConnX

### 1. Hosted: click the link

Open **https://connx3.vercel.app**. Nothing to install. The first request after
a quiet spell can take up to a minute while the free backend wakes. Red spots
are tied to your browser's cookie, so clearing cookies or switching browsers
loses them.

To run your own copy, see [Deploying your own copy](#deploying-your-own-copy).

### 2. Docker

```bash
docker compose --profile full up --build
```

- Frontend: http://localhost:3000 (the Next.js dev server in a container)
- Backend: http://localhost:8000 (FastAPI docs at `/docs`)
- Postgres: localhost:5432 (schema from `backend/init.sql`, data kept in the
  `connx_db_data` volume)
- The containers run in development mode: no rate limits, `/docs` open, CORS
  open to any localhost port.
- The backend container needs internet access for routing and search.
- Optional settings are read from your shell or a `.env` file next to
  `docker-compose.yml`: `ORS_API_KEY`, `LOCATIONIQ_API_KEY`,
  `NOMINATIM_USER_AGENT` (use a real contact address), `ROUTING_PROVIDER`
  and `GEOCODING_PROVIDER`. Without keys it runs on public OSRM, Photon and
  Nominatim.
- To keep the frontend native for a faster dev loop, leave out the profile:
  `docker compose up --build` starts only Postgres and the backend, and you run
  `cd frontend && npm run dev` yourself.

### 3. Local, no Docker

Zero infrastructure needed. SQLite just works because all spatial math runs in
Python (Shapely), not in the database.

```bash
cp backend/.env.example backend/.env   # SQLite by default; Windows: copy
python run_all.py                      # backend :8000, frontend :3000
```

Open http://localhost:3000. `run_all.py` checks DB reachability first and tells
you exactly how to fix it if something is wrong. For SQLite-only mode, make
sure `backend/.env` contains:

```env
DATABASE_URL=sqlite:///./connx_dev.db
```

Copy `backend/.env.example` first, because the built-in default is Postgres.

**With your own Postgres instead of SQLite.** Install PostgreSQL, create a
database, then point `backend/.env` at it:

```env
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/connx
```

The schema is optional (SQLAlchemy also creates the tables on startup):

```bash
psql -U user -d connx -f backend/init.sql
```

Then run `python run_all.py`, or the backend alone with
`cd backend && python app/main.py`.

## Deploying your own copy

The hosted demo is three free services. The browser only ever talks to the
Vercel site; Next.js proxies `/api/*` to the backend, so the device cookie is
sent and CORS never comes into play.

```
browser -> Vercel (Next.js) --/api/*--> Render (FastAPI, Docker) --> Neon (Postgres)
```

**1. Neon (database).** Create a project and copy its connection string. The
backend creates its tables on first start.

**2. Render (backend).** New Web Service from this repo (or your fork):

| Setting | Value |
|---|---|
| Runtime | Docker |
| Root Directory | `backend` |
| Branch | `main` |
| Health Check Path | `/api/health` |
| Instance type | Free |

Environment variables:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | the Neon connection string |
| `SESSION_SECRET` | a long random value (Render can generate one) |
| `FRONTEND_ORIGIN` | your Vercel URL, no trailing slash (only matters for direct calls to the backend) |
| `ROUTING_PROVIDER` / `ORS_API_KEY` | `ors` and your OpenRouteService key (optional) |
| `GEOCODING_PROVIDER` / `LOCATIONIQ_API_KEY` | `photon` and your LocationIQ key (optional) |
| `NOMINATIM_USER_AGENT` | `ConnX/0.1 (+<your repo URL>)`, a real contact, or OSM blocks you |
| `RATE_LIMIT_ROUTES_PER_MIN`, `RATE_LIMIT_SEARCH_PER_MIN` | optional; default 10 and 60 per IP |

With `ENVIRONMENT=production` the backend hides `/docs`, marks the cookie
`Secure`, turns on the rate limits and spaces Nominatim calls one second apart.
It refuses to start if `SESSION_SECRET` or `DATABASE_URL` is still the default
from the repo, so a missing variable fails with a clear message in the log.
A service created from a public repo URL does not redeploy on push; use
**Manual Deploy**.

**3. Vercel (frontend).**

```bash
cd frontend
vercel link
vercel env add BACKEND_URL production   # your Render URL, e.g. https://connx-api.onrender.com
vercel deploy --prod
```

`BACKEND_URL` is read at build time, so redeploy after changing it. Without it
(local development) the browser calls `NEXT_PUBLIC_API_URL` directly.

**Check it:** `/api/health` on the Vercel URL returns `{"status":"ok"}`, search
returns places, and a compare returns an overlap.

## Collaborating across machines

In development mode the backend's CORS accepts **any** port on
`localhost` / `127.0.0.1`, so nobody needs matching ports or manual
`FRONTEND_ORIGIN` syncing - if your `npm run dev` lands on 3001 instead of
3000, everything still works. Production locks CORS down to the exact
`FRONTEND_ORIGIN`; the hosted setup avoids the question by proxying through
one origin.
