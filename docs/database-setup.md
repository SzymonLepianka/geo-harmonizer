# Przygotowanie PostgreSQL/PostGIS poza Dockerem

GeoHarmonizer celowo nie uruchamia bazy danych w Docker Compose. Polecenia wykonaj jako administrator PostgreSQL, np. przez `psql -U postgres`:

```sql
CREATE DATABASE geoharmonizer;
CREATE USER geoharmonizer WITH PASSWORD 'geoharmonizer_password';
GRANT ALL PRIVILEGES ON DATABASE geoharmonizer TO geoharmonizer;

\c geoharmonizer

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
GRANT ALL ON SCHEMA public TO geoharmonizer;
```

Migracja Alembic również próbuje włączyć oba rozszerzenia. Jeżeli konto aplikacyjne nie ma uprawnień, migracja wyświetli instrukcję, a rozszerzenia trzeba włączyć ręcznie jako administrator.

## Adres połączenia

- Backend lokalny: `postgresql+psycopg://geoharmonizer:password@localhost:5432/geoharmonizer`
- Backend w Dockerze, baza na Windows/Mac: `postgresql+psycopg://geoharmonizer:password@host.docker.internal:5432/geoharmonizer`
- Aplikacja i baza na jednym VPS: `postgresql+psycopg://geoharmonizer:password@127.0.0.1:5432/geoharmonizer`

Nie wystawiaj portu 5432 publicznie. Na VPS ogranicz nasłuch i reguły zapory do połączeń lokalnych.

## Kontrola

```sql
SELECT version();
SELECT PostGIS_Version();
```

API udostępnia dodatkową kontrolę pod `GET /api/health/db`.

