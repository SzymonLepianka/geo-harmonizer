import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404
from app.models import EventLog, User
from app.schemas import EventLogOut

router = APIRouter(prefix="/api/projects/{project_id}/logs", tags=["logs"])


@router.get("", response_model=list[EventLogOut])
def list_logs(project_id: uuid.UUID, level: str | None = None, limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0), db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[EventLog]:
    get_project_or_404(project_id, db)
    query = select(EventLog).where(EventLog.project_id == project_id)
    if level:
        query = query.where(EventLog.level == level)
    return list(db.scalars(query.order_by(EventLog.created_at.desc()).limit(limit).offset(offset)).all())

