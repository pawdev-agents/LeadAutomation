from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth import create_access_token, current_user, hash_password, verify_password
from ..database import get_db
from ..models import Team, User
from ..schemas import LoginIn, RegisterIn

router = APIRouter(prefix="/auth", tags=["auth"])

def account_response(user: User):
    return {"access_token": create_access_token(user), "token_type": "bearer", "team_id": user.team_id, "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role}}

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == str(data.email).lower())):
        raise HTTPException(status_code=409, detail="Email is already registered")
    if db.scalar(select(Team).where(Team.name == data.team_name)):
        raise HTTPException(status_code=409, detail="Team name is already in use")
    team = Team(name=data.team_name)
    db.add(team); db.flush()
    user = User(team_id=team.id, email=str(data.email).lower(), name=data.name, password_hash=hash_password(data.password), role="admin")
    db.add(user); db.commit(); db.refresh(user)
    return account_response(user)

@router.post("/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    if not user or not user.active or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return account_response(user)

@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    team = db.get(Team, user.team_id)
    return {"user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role, "active": user.active}, "team": {"id": team.id, "name": team.name, "timezone": team.timezone}}
