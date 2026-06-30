from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "GeoHarmonizer API"}


@router.get("/db")
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        version = db.execute(text("SELECT PostGIS_Version()")) .scalar_one()
        return {"status": "ok", "database": "PostgreSQL", "postgis": version}
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Brak połączenia z PostgreSQL/PostGIS") from exc

