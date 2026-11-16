from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth import current_user, hash_password
from ..database import get_db
from ..models import User
from ..schemas import UserCreateIn, UserUpdateIn

router = APIRouter(prefix="/users", tags=["users"])

def admin(user: User = Depends(current_user)):
    if user.role != "admin": raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
def output(user: User): return {"id":user.id,"team_id":user.team_id,"name":user.name,"email":user.email,"role":user.role,"active":user.active}

@router.get("")
def list_users(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [output(item) for item in db.scalars(select(User).where(User.team_id == user.team_id).order_by(User.name))]

@router.post("", status_code=201)
def create_user(data: UserCreateIn, db: Session = Depends(get_db), user: User = Depends(admin)):
    if data.role not in {"admin", "member"}: raise HTTPException(422, "Role must be admin or member")
    if db.scalar(select(User).where(User.email == str(data.email).lower())): raise HTTPException(409, "Email is already registered")
    member = User(team_id=user.team_id, name=data.name, email=str(data.email).lower(), password_hash=hash_password(data.password), role=data.role)
    db.add(member); db.commit(); db.refresh(member); return output(member)

@router.patch("/{user_id}")
def update_user(user_id: int, data: UserUpdateIn, db: Session = Depends(get_db), user: User = Depends(admin)):
    member = db.scalar(select(User).where(User.id == user_id, User.team_id == user.team_id))
    if not member: raise HTTPException(404, "User not found")
    values = data.model_dump(exclude_unset=True)
    if values.get("role") and values["role"] not in {"admin", "member"}: raise HTTPException(422, "Role must be admin or member")
    for key, value in values.items(): setattr(member, key, value)
    db.commit(); db.refresh(member); return output(member)
