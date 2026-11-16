from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import User
security=HTTPBearer()
# PBKDF2 is stdlib-backed and avoids bcrypt 5.x / passlib compatibility failures.
passwords = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
def hash_password(password: str) -> str: return passwords.hash(password)
def verify_password(password: str, password_hash: str) -> bool: return passwords.verify(password, password_hash)
def create_access_token(user: User):
    return jwt.encode({"sub":str(user.id),"team_id":user.team_id,"exp":datetime.now(timezone.utc)+timedelta(hours=12)}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
def current_user(credentials: HTTPAuthorizationCredentials=Depends(security), db:Session=Depends(get_db)):
    try: claims=jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm]); user=db.get(User, int(claims["sub"]))
    except Exception: user=None
    if not user or not user.active: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user
