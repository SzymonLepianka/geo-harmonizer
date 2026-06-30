"""Create the first administrator from ADMIN_EMAIL and ADMIN_PASSWORD."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402


def main() -> None:
    settings = get_settings()
    email = settings.admin_email.lower()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user:
            user.role = "ADMIN"
            user.is_active = True
            print(f"Administrator {email} już istnieje; rola i aktywność zostały potwierdzone.")
        else:
            user = User(email=email, password_hash=hash_password(settings.admin_password), role="ADMIN", is_active=True)
            db.add(user)
            print(f"Utworzono administratora {email}.")
        db.commit()


if __name__ == "__main__":
    main()

