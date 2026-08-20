FROM python:3.12-slim

WORKDIR /app

# libgeos is required by shapely; psycopg2-binary avoids needing libpq-dev
RUN apt-get update && apt-get install -y --no-install-recommends libgeos-c1v5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
