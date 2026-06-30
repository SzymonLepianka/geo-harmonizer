import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404, require_editor
from app.models import AnalysisRun, Layer, Project, User
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.services.events import add_event

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _project_dict(db: Session, project: Project) -> dict:
    return {
        **{column.name: getattr(project, column.name) for column in Project.__table__.columns},
        "layer_count": db.scalar(select(func.count()).select_from(Layer).where(Layer.project_id == project.id)) or 0,
        "analysis_count": db.scalar(select(func.count()).select_from(AnalysisRun).where(AnalysisRun.project_id == project.id)) or 0,
    }


@router.get("", response_model=list[ProjectOut])
def list_projects(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    projects = db.scalars(select(Project).order_by(Project.updated_at.desc()).limit(limit).offset(offset)).all()
    return [_project_dict(db, project) for project in projects]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(require_editor)) -> dict:
    project = Project(**payload.model_dump(), created_by_user_id=user.id)
    db.add(project)
    db.flush()
    add_event(db, project_id=project.id, entity_type="project", entity_id=project.id, user_id=user.id, message=f"Utworzono projekt „{project.name}”.")
    db.commit()
    db.refresh(project)
    return _project_dict(db, project)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    return _project_dict(db, get_project_or_404(project_id, db))


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: uuid.UUID, payload: ProjectUpdate, db: Session = Depends(get_db), user: User = Depends(require_editor)) -> dict:
    project = get_project_or_404(project_id, db)
    for key, value in payload.model_dump().items():
        setattr(project, key, value)
    add_event(db, project_id=project.id, entity_type="project", entity_id=project.id, user_id=user.id, message=f"Zaktualizowano projekt „{project.name}”.")
    db.commit()
    db.refresh(project)
    return _project_dict(db, project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_editor)) -> None:
    project = get_project_or_404(project_id, db)
    db.delete(project)
    db.commit()

