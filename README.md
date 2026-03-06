# ChatDigest v1.0

> 카카오 오픈채팅 내역을 Gemini AI로 분석해 뉴스레터 형식으로 보여주는 개인용 웹 서비스.

---

## 기능 요약

- 카카오톡 오픈채팅 내보내기(.txt) 파일 업로드
- Gemini 2.5 Flash가 채팅방별 메시지를 분석, 토픽 태그 자동 분류
- 일간 / 주간 / 월간 다이제스트 생성 및 뉴스레터 형식으로 표시
- 비밀번호 기반 단일 사용자 인증

---

## 프로젝트 구조

```
openchat-news/
├── frontend/          # Next.js 16 + Tailwind + shadcn/ui  → Vercel 배포
├── backend/           # FastAPI + Python 3.12 (uv)         → 홈서버 Docker
├── docker-compose.yml # PostgreSQL + FastAPI 컨테이너
├── .env               # 실제 환경변수 (git 제외)
└── .env.example       # 환경변수 템플릿
```

---

## 환경변수

| 키 | 설명 |
|----|------|
| `GEMINI_API_KEY` | Google AI Studio API 키 |
| `PASSWD` | 웹 로그인 비밀번호 |
| `SECRET_KEY` | JWT 서명용 랜덤 문자열 |
| `DATABASE_URL` | PostgreSQL 연결 URL (Docker 기본값 사용 가능) |

---

## 로컬 개발

### 사전 준비

- Node.js 18+, Python 3.12+, uv, Docker Desktop

### 1. 환경변수 설정

```bash
cp .env.example .env
# GEMINI_API_KEY, PASSWD, SECRET_KEY 입력

cp .env backend/.env
# backend/.env의 DATABASE_URL은 localhost:5432 사용
```

### 2. DB 컨테이너 시작

```bash
docker compose up -d db
```

### 3. 백엔드 실행

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

### 4. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

---

## 홈서버 배포 (Ubuntu Server 24.04)

### 1. 파일 전송

```bash
rsync -av \
  --exclude='.venv' --exclude='node_modules' --exclude='__pycache__' \
  /path/to/openchat-news/ user@homeserver:~/openchat-news/
```

### 2. 환경변수 설정

```bash
cd ~/openchat-news
cp .env.example .env
nano .env   # GEMINI_API_KEY, PASSWD, SECRET_KEY 입력
```

### 3. 컨테이너 빌드 및 실행

```bash
docker compose up -d --build
# 백엔드 API: http://homeserver-ip:8000
# DB: 컨테이너 내부 전용
```

### 4. 업데이트

```bash
rsync -av ... user@homeserver:~/openchat-news/
docker compose up -d --build backend
```

---

## Vercel 배포 (프론트엔드)

1. 레포지토리를 GitHub에 push
2. Vercel 프로젝트 생성 → **Root Directory**: `frontend`
3. 환경변수 추가:
   ```
   NEXT_PUBLIC_API_URL=http://홈서버IP:8000
   ```
4. Deploy

---

## 사용 흐름

1. 카카오톡 오픈채팅 → 우측 상단 메뉴 → **대화 내보내기** → `.txt` 저장
2. 웹 접속 → 로그인
3. 사이드바 → **파일 업로드** → `.txt` 선택 → 미리보기 확인 → 업로드 확인
4. 사이드바 → **요약 생성** → 날짜 선택 → 생성 (Gemini API 호출)
5. 왼쪽 네비게이션에서 **일간 / 주간 / 월간** 다이제스트 확인

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프론트엔드 | Next.js 16, Tailwind CSS v4, shadcn/ui, react-markdown |
| 백엔드 | FastAPI 0.135, Python 3.12, SQLAlchemy 2.0 (async) |
| 데이터베이스 | PostgreSQL 16 (Docker) |
| AI | Google Gemini 2.5 Flash (`google-genai`) |
| 인증 | JWT (쿠키), 비밀번호 단일 사용자 |
| 배포 | Vercel (프론트) + Docker Compose (백엔드/DB) |

---

## 버전 히스토리

| 버전 | 날짜 | 내용 |
|------|------|------|
| v1.1 | 2026-03-06 | 다중 업로드, 배치 생성, 토픽 가중치, 채팅방 커버리지 체크 |
| v1.0 | 2026-03-06 | 최초 릴리즈 — 업로드/요약생성/일간·주간·월간 뷰 |
