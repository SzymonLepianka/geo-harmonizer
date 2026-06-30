import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404, require_editor
from app.enums import LAYER_TYPES
from app.models import DatasetImport, SourceRegistry, User
from app.schemas import CatalogImportRequest, CatalogPreviewOut, ImportOut
from app.services.catalog_imports import (
    get_catalog_source,
    import_catalog_source,
    preview_catalog_import,
    resolve_bbox,
)
from app.services.imports import import_uploaded_file

router = APIRouter(prefix="/api/projects/{project_id}/imports", tags=["imports"])


@router.post("/file", response_model=ImportOut, status_code=201)
def upload_file(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    layer_type: str = Form(...),
    layer_name: str = Form(...),
    source_name: str = Form(...),
    target_crs: str = Form("EPSG:2180"),
    source_key: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
) -> DatasetImport:
    get_project_or_404(project_id, db)
    if layer_type not in LAYER_TYPES:
        raise HTTPException(status_code=422, detail="Nieobsługiwany typ warstwy")
    catalog_source = None
    if source_key:
        catalog_source = db.scalar(select(SourceRegistry).where(SourceRegistry.key == source_key))
        if not catalog_source:
            raise HTTPException(status_code=404, detail="Nie znaleziono źródła katalogowego")
        if catalog_source.import_mode not in {"MANUAL_DOWNLOAD", "MANUAL_ORDER"}:
            raise HTTPException(status_code=422, detail="To źródło nie jest profilem importu plikowego")
    record, _ = import_uploaded_file(
        db,
        project_id=project_id,
        user_id=user.id,
        upload=file,
        layer_type=layer_type,
        layer_name=layer_name,
        source_name=source_name,
        target_crs=target_crs,
        catalog_source=catalog_source,
    )
    return record


@router.post("/catalog/preview", response_model=CatalogPreviewOut)
def preview_catalog(project_id: uuid.UUID, payload: CatalogImportRequest, db: Session = Depends(get_db), _: User = Depends(require_editor)) -> CatalogPreviewOut:
    get_project_or_404(project_id, db)
    source = get_catalog_source(db, payload.source_key)
    return preview_catalog_import(source, resolve_bbox(payload))


@router.post("/catalog", response_model=ImportOut, status_code=201)
def upload_catalog(project_id: uuid.UUID, payload: CatalogImportRequest, db: Session = Depends(get_db), user: User = Depends(require_editor)) -> DatasetImport:
    get_project_or_404(project_id, db)
    source = get_catalog_source(db, payload.source_key)
    record, _ = import_catalog_source(
        db,
        project_id=project_id,
        user_id=user.id,
        source=source,
        bbox=resolve_bbox(payload),
        layer_name=payload.layer_name,
    )
    return record


@router.get("", response_model=list[ImportOut])
def list_imports(project_id: uuid.UUID, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[DatasetImport]:
    get_project_or_404(project_id, db)
    return list(db.scalars(select(DatasetImport).where(DatasetImport.project_id == project_id).order_by(DatasetImport.created_at.desc()).limit(limit).offset(offset)).all())


@router.get("/{import_id}", response_model=ImportOut)
def get_import(project_id: uuid.UUID, import_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> DatasetImport:
    record = db.get(DatasetImport, import_id)
    if not record or record.project_id != project_id:
        raise HTTPException(status_code=404, detail="Nie znaleziono importu")
    return record
