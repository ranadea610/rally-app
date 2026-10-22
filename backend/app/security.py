import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import LoginSession, User

hasher = PasswordHasher()
dummy_hash = hasher.hash('rally-invalid-account-timing-placeholder')


def digest(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def verify_password(password: str, password_hash: str):
    try:
        return hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_session(db: Session, user: User):
    token = secrets.token_urlsafe(32)
    session = LoginSession(token_hash=digest(token), user_id=user.id,
                           csrf_token=secrets.token_urlsafe(32),
                           expires_at=datetime.now(timezone.utc) + timedelta(hours=settings().session_hours))
    db.add(session)
    return token, session


def current_session(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get('rally_session')
    session = db.get(LoginSession, digest(token)) if token else None
    if not session or session.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(401, 'Sign in to continue.')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session.csrf_token):
            raise HTTPException(403, 'A valid CSRF token is required.')
    return session


def current_user(session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, 'Sign in to continue.')
    return user


def coach_user(user: User = Depends(current_user)):
    if user.requested_role not in ('coach', 'both') or not user.coach_approved:
        raise HTTPException(403, 'An officer must approve your coach access first.')
    return user


def admin_user(user: User = Depends(current_user)):
    if not user.is_admin:
        raise HTTPException(403, 'Officer access required.')
    return user
