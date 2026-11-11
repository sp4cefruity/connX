import sys
from pathlib import Path

# Direct execution (`python app/main.py`) only puts backend/app on
# sys.path, which breaks `import app.*`; add backend/ itself.
_BACKEND_ROOT = str(Path(__file__).resolve().parent.parent)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.database import init_db
from app.routers import geocode, red_spots, routes

settings = get_settings()
_production = settings.environment != "development"

if _production and settings.session_secret == Settings.model_fields["session_secret"].default:
    # The default is public (it is in this repo), so cookies signed with it
    # could be forged. Refuse to start rather than run that way.
    raise RuntimeError("SESSION_SECRET must be set to a random value outside development")

if _production and "localhost" in settings.database_url:
    # The code default points at a local Postgres; on a host it means the
    # DATABASE_URL variable never arrived (missing, misnamed or not saved).
    raise RuntimeError("DATABASE_URL is not set (still the localhost default); set it to the hosted Postgres URL")

app = FastAPI(
    title="ConnX API",
    description="Route overlap detection & avoidance planning.",
    version="0.1.0",
    # No interactive API docs on the public deployment.
    docs_url=None if _production else "/docs",
    redoc_url=None if _production else "/redoc",
    openapi_url=None if _production else "/openapi.json",
)

if settings.environment == "development":
    # Match any port on localhost/127.0.0.1 so every developer's frontend
    # works regardless of which port `npm run dev` happened to bind to —
    # no more syncing FRONTEND_ORIGIN by hand across machines.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Production: lock down to the exact configured origin(s). Never widen
    # this to a regex/wildcard once real user traffic is involved.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(geocode.router)
app.include_router(routes.router)
app.include_router(red_spots.router)

init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
