from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import geocode, red_spots, routes

settings = get_settings()

app = FastAPI(
    title="ConnX API",
    description="Route overlap detection & avoidance planning.",
    version="0.1.0",
)

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


@app.get("/api/health")
def health():
    return {"status": "ok"}
