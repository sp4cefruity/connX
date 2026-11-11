FROM python:3.12-slim

# No .pyc files, and logs reach `docker compose logs` immediately.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# libgeos is required by shapely; psycopg2-binary avoids needing libpq-dev
RUN apt-get update && apt-get install -y --no-install-recommends libgeos-c1v5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user.
RUN useradd --system --no-create-home connx
USER connx

# Configuration comes from environment variables (see docker-compose.yml and
# backend/.env.example). Routing and search call public servers (ORS/OSRM,
# Photon, LocationIQ, Nominatim), so the container needs outbound internet.
# Self-hosted Valhalla is parked (ADR 0007) and is not part of this image.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
