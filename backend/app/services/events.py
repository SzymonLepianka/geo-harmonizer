import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import EventLog


def add_event(
    db: Session,
    *,
    message: str,
    entity_type: str,
    level: str = "INFO",
    project_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> EventLog:
    event = EventLog(
        project_id=project_id,
        entity_type=entity_type,
        entity_id=entity_id,
        level=level,
        message=message,
        details_json=details,
        user_id=user_id,
    )
    db.add(event)
    return event

