from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import COOKIE_NAME, create_access_token, verify_password
from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import LoginRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nieprawidłowy e-mail lub hasło")
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        create_access_token(user.id),
        httponly=True,
        secure=settings.secure_cookie,
        samesite="lax",
        max_age=settings.session_hours * 3600,
        path="/",
    )
    return user


@router.post("/logout", status_code=204)
def logout(response: Response, _: User = Depends(get_current_user)) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
