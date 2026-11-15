from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from src.config.database import get_db
from src.models import User
from src.utils.security import verify_password, token_for
from src.middlewares.auth import current_user
from src.services.audit import record
router=APIRouter(prefix='/auth')
class Login(BaseModel):
    email:str=Field(max_length=150)
    password:str=Field(max_length=200)
@router.post('/login')
def login(data:Login, db=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==data.email))
    if not u or not verify_password(data.password,u.password): raise HTTPException(401,'账号或密码不正确')
    record(db,u.email,'auth.login'); db.commit()
    return {'access_token':token_for(u),'user':{'name':u.name,'role':u.role,'email':u.email}}
@router.get('/me')
def me(u=Depends(current_user)):return {'name':u.name,'role':u.role,'email':u.email}
