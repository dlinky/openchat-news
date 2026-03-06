from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Response, Cookie
from pydantic import BaseModel
from jose import jwt
from passlib.context import CryptContext
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    password: str


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def verify_token(token: str) -> bool:
    try:
        jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return True
    except Exception:
        return False


@router.post("/login")
async def login(request: LoginRequest, response: Response):
    if request.password != settings.passwd:
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다")

    token = create_access_token({"sub": "admin"})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="none",
        secure=True,
    )
    return {"message": "로그인 성공"}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "로그아웃 성공"}


@router.get("/verify")
async def verify(access_token: str | None = Cookie(default=None)):
    if not access_token or not verify_token(access_token):
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    return {"authenticated": True}
