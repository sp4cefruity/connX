Connecting hearts, hearts so much bigger than maps.

## Running ConnX

Three ways to run the stack - pick whichever fits your situation.

### 1. Everything in Docker

```bash
docker compose up --build
```

- Backend: http://localhost:8000 (FastAPI docs at `/docs`)
- Postgres: localhost:5432
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

(see `backend/.env.example`).

## Collaborating across machines

In development mode the backend's CORS accepts **any** port on
`localhost` / `127.0.0.1`, so nobody needs matching ports or manual
`FRONTEND_ORIGIN` syncing - if your `npm run dev` lands on 3001 instead of
3000, everything still works. Production builds lock CORS down to the exact
`FRONTEND_ORIGIN`, so set that properly when deploying.
