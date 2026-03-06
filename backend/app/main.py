from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import jwt
from app.config import settings
from app.database import engine
from app.models.models import Base
from app.routers import auth, rooms, upload, summaries, generate


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 테이블 자동 생성 (없을 때만)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="ChatDigest API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://openchat-news.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 인증 제외 경로
PUBLIC_PATHS = {"/auth/login", "/auth/logout", "/health", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/docs"):
        return await call_next(request)

    token = request.cookies.get("access_token")
    if not token:
        response = JSONResponse(status_code=401, content={"detail": "인증이 필요합니다"})
        response.headers["Access-Control-Allow-Origin"] = request.headers.get("origin", "*")
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    try:
        jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except Exception:
        response = JSONResponse(status_code=401, content={"detail": "인증이 만료되었습니다"})
        response.headers["Access-Control-Allow-Origin"] = request.headers.get("origin", "*")
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    return await call_next(request)


app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(upload.router)
app.include_router(summaries.router)
app.include_router(generate.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
