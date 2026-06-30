import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404, require_editor
from app.enums import LAYER_TYPES
from app.models import DatasetImport, User
from app.schemas import ImportOut, WFSImportRequest
from app.services.imports import import_uploaded_file, import_wfs

router = APIRouter(prefix="/api/projects/{project_id}/imports", tags=["imports"])


@router.post("/file", response_model=ImportOut, status_code=201)
def upload_file(project_id: uuid.UUID, file: UploadFile = File(...), layer_type: str = Form(...), layer_name: str = Form(...), source_name: str = Form(...), target_crs: str = Form("EPSG:2180"), db: Session = Depends(get_db), user: User = Depends(require_editor)) -> DatasetImport:
    get_project_or_404(project_id, db)
    if layer_type not in LAYER_TYPES:
        raise HTTPException(status_code=422, detail="Nieobsługiwany typ warstwy")
    record, _ = import_uploaded_file(db, project_id=project_id, user_id=user.id, upload=file, layer_type=layer_type, layer_name=layer_name, source_name=source_name, target_crs=target_crs)
    return record


@router.post("/wfs", response_model=ImportOut, status_code=201)
def upload_wfs(project_id: uuid.UUID, payload: WFSImportRequest, db: Session = Depends(get_db), user: User = Depends(require_editor)) -> DatasetImport:
    get_project_or_404(project_id, db)
    record, _ = import_wfs(db, project_id=project_id, user_id=user.id, **payload.model_dump())
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

