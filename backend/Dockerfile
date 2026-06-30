FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace
RUN apt-get update \
    && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml /workspace/backend/pyproject.toml
COPY backend/app /workspace/backend/app
RUN python -m pip install --upgrade pip && pip install "/workspace/backend"
RUN python -c "import fiona; required={'GeoJSON','GPKG','ESRI Shapefile','GML'}; missing=required-set(fiona.supported_drivers); assert not missing, f'Missing GDAL drivers: {missing}'"

COPY backend /workspace/backend
COPY scripts /workspace/scripts
WORKDIR /workspace/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
