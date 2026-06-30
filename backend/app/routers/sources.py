import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404, require_editor
from app.models import DataSource, SourceRegistry, User
from app.schemas import DataSourceCreate, DataSourceOut, SourceRegistryOut

router = APIRouter(tags=["sources"])


@router.get("/api/source-registry", response_model=list[SourceRegistryOut])
def source_registry(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[SourceRegistry]:
    return list(db.scalars(select(SourceRegistry).order_by(SourceRegistry.category, SourceRegistry.name)).all())


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

