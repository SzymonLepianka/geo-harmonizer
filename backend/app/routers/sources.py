import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404, require_editor
from app.models import DataSource, SourceRegistry, User
from app.schemas import (
    AreaPresetOut,
    CatalogCheckOut,
    DataSourceCreate,
    DataSourceOut,
    SourceRegistryOut,
)
from app.services.catalog_imports import (
    AREA_PRESETS,
    check_catalog_source,
    get_catalog_source,
)

router = APIRouter(tags=["sources"])


@router.get("/api/source-registry", response_model=list[SourceRegistryOut])
def source_registry(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[SourceRegistry]:
    return list(db.scalars(select(SourceRegistry).order_by(SourceRegistry.sort_order, SourceRegistry.name)).all())


@router.get("/api/source-catalog", response_model=list[SourceRegistryOut])
def source_catalog(
    category: str | None = None,
    import_mode: str | None = None,
    status: str | None = None,
    include_inactive: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[SourceRegistry]:
    query = select(SourceRegistry)
    if category:
        query = query.where(SourceRegistry.category == category)
    if import_mode:
        query = query.where(SourceRegistry.import_mode == import_mode)
    if status:
        query = query.where(SourceRegistry.implementation_status == status)
    if not include_inactive:
        query = query.where(SourceRegistry.is_active.is_(True))
    return list(db.scalars(query.order_by(SourceRegistry.sort_order, SourceRegistry.name)).all())


@router.get("/api/source-catalog/area-presets", response_model=list[AreaPresetOut])
def area_presets(_: User = Depends(get_current_user)) -> list[dict]:
    return list(AREA_PRESETS.values())


@router.post("/api/source-catalog/{key}/check", response_model=CatalogCheckOut)
def check_source(key: str, db: Session = Depends(get_db), _: User = Depends(require_editor)) -> CatalogCheckOut:
    return check_catalog_source(db, get_catalog_source(db, key))


@router.get("/api/projects/{project_id}/data-sources", response_model=list[DataSourceOut])
def list_sources(project_id: uuid.UUID, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[DataSource]:
    get_project_or_404(project_id, db)
    return list(db.scalars(select(DataSource).where(DataSource.project_id == project_id).order_by(DataSource.created_at.desc()).limit(limit).offset(offset)).all())


@router.post("/api/projects/{project_id}/data-sources", response_model=DataSourceOut, status_code=201)
def create_source(project_id: uuid.UUID, payload: DataSourceCreate, db: Session = Depends(get_db), _: User = Depends(require_editor)) -> DataSource:
    get_project_or_404(project_id, db)
    source = DataSource(project_id=project_id, **payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.get("/api/projects/{project_id}/data-sources/{source_id}", response_model=DataSourceOut)
def get_source(project_id: uuid.UUID, source_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> DataSource:
    source = db.get(DataSource, source_id)
    if not source or source.project_id != project_id:
        raise HTTPException(status_code=404, detail="Nie znaleziono źródła danych")
    return source
