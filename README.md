# GeoHarmonizer

GeoHarmonizer to badawcza aplikacja webowa do importowania, prezentowania i analizowania relacji między warstwami EGiB, LPIS/GSA/MKO/PZ oraz innymi danymi wektorowymi. Wyniki są kandydatami do dalszej weryfikacji — nie stanowią rozstrzygnięcia prawnego ani automatycznej korekty danych. LPIS jest źródłem pomocniczym, nie wzorcem granic prawnych.

## Architektura

- `backend` — Python 3.12, FastAPI, SQLAlchemy, Alembic, GeoAlchemy2, Shapely, GeoPandas/Fiona.
- `frontend` — React, TypeScript, TanStack Query i OpenLayers.
- PostgreSQL/PostGIS działa poza Dockerem.
- Docker Compose zawiera wyłącznie `api` i `web`.

## Wymagania

- Python 3.12 (uruchomienie lokalne backendu) albo Docker Desktop,
- Node.js 20+ i npm (uruchomienie lokalne frontendu),
- PostgreSQL z PostGIS dostępny poza Dockerem.

## Pierwsze uruchomienie

1. Przygotuj bazę według [docs/database-setup.md](docs/database-setup.md).
2. Skopiuj `.env.example` do `.env` i ustaw co najmniej `SECRET_KEY`, `DATABASE_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`.
3. Wykonaj migracje oraz utwórz administratora.

### Backend lokalnie

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".\backend[dev]"
Set-Location backend
alembic upgrade head
Set-Location ..
python scripts/create_admin.py
uvicorn app.main:app --app-dir backend --reload --port 8000
```

Dokumentacja API w development jest dostępna pod `http://localhost:8000/docs`.

### Frontend lokalnie

```powershell
Set-Location frontend
npm install
npm run dev
```

Otwórz `http://localhost:5173`. Vite proxy kieruje `/api` do `localhost:8000`.

### Docker Compose bez bazy

Jeśli PostgreSQL działa na komputerze Windows/Mac, wpisz w `.env`:

```env
DATABASE_URL=postgresql+psycopg://geoharmonizer:password@host.docker.internal:5432/geoharmonizer
```

Następnie:

```powershell
docker compose build
docker compose run --rm api alembic upgrade head
docker compose run --rm api python /workspace/scripts/create_admin.py
docker compose run --rm api python /workspace/scripts/seed_demo_data.py
docker compose up -d
```

Web działa na `http://localhost:5173`, a API na `http://localhost:8000`.

## Dane demonstracyjne

Po migracji uruchom:

```powershell
python scripts/seed_demo_data.py
```

Skrypt jest idempotentny. Tworzy projekt z działkami, budynkiem wewnątrz działki, budynkiem przecinającym granicę, silnym i częściowym pokryciem LPIS, obiektem LPIS bez odpowiednika oraz liniami blisko i w poprzek granicy.

## Analizy

- `BUILDING_PARCEL_RELATION` — relacja budynków względem działek.
- `EGIB_LPIS_OVERLAP` — pomocnicza analiza pokrycia powierzchniowego.
- `LINE_BOUNDARY_PROXIMITY` — generyczna relacja linii i granicy.

Wszystkie tolerancje i progi są jawnie wpisywane przez użytkownika. Wyniki można oglądać w tabeli i na mapie oraz eksportować do GeoJSON i CSV.

## Import

Obsługiwane są GeoJSON/JSON, pierwsza warstwa GeoPackage, pierwszy SHP w ZIP, podstawowy GML oraz podstawowy WFS. Dane są naprawiane, sprowadzane do 2D i transformowane do EPSG:2180. GeoJSON bez CRS jest interpretowany jako EPSG:4326; pozostałe formaty muszą określać CRS.

## Testy i kontrola jakości

```powershell
python -m pytest backend/tests
Set-Location frontend
npm run lint
npm run build
```

Testy geometrii nie wymagają bazy. Pełny smoke test wymaga przygotowanego `DATABASE_URL`, migracji i danych demo.

## Ograniczenia MVP

- przetwarzanie jest synchroniczne i przeznaczone dla umiarkowanych zbiorów,
- wielowarstwowe pliki importują pierwszą warstwę i logują pominięte warstwy,
- GML i WFS mają podstawową, ogólną obsługę,
- brak GESUT, ortofotomapy, LIDAR i automatycznej detekcji ogrodzeń,
- brak publicznej rejestracji, odzyskiwania hasła, płatności i funkcji SaaS,
- projekty są wspólne dla wszystkich aktywnych użytkowników.

## Dalsze prace

Worker i kolejka zadań, wybór warstw w plikach wielowarstwowych, pełniejsze profile GML EGiB/BDOT500, kafle wektorowe dla dużych zbiorów, uprawnienia per projekt oraz opcjonalne, konfigurowalne warstwy podkładowe.

Więcej o założeniach badawczych: [docs/research-context.md](docs/research-context.md).
