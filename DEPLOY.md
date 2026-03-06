# 배포 가이드 — 홈서버(백엔드) + Vercel(프론트엔드)

## 구성 개요

```
[브라우저] → [Vercel - Next.js] → [홈서버 HTTPS] → [FastAPI + PostgreSQL]
```

---

## 1단계: 홈서버 준비

### 1-1. Docker 설치 (Ubuntu 기준)

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 재로그인 필요
```

### 1-2. 코드 복사

개발 PC에서 홈서버로 전송:

```bash
# 개발 PC에서 실행
rsync -av --exclude='node_modules' --exclude='__pycache__' --exclude='.git' \
  /path/to/openchat-news/ user@homeserver:/opt/openchat-news/
```

또는 GitHub에 올린 경우:

```bash
# 홈서버에서
git clone https://github.com/your/repo.git /opt/openchat-news
```

### 1-3. 환경변수 설정

```bash
cd /opt/openchat-news
cp .env.example .env
nano .env
```

```dotenv
GEMINI_API_KEY=your-gemini-api-key
PASSWD=your-login-password
SECRET_KEY=여기에-랜덤-긴-문자열-입력   # openssl rand -hex 32
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/openchat_news
```

### 1-4. 백엔드 CORS에 Vercel 도메인 추가

`backend/app/main.py` 의 `allow_origins` 수정:

```python
allow_origins=[
    "http://localhost:3000",
    "https://your-project.vercel.app",   # ← 실제 Vercel URL로 변경
    "https://your-custom-domain.com",    # 커스텀 도메인이 있다면 추가
],
```

### 1-5. 컨테이너 실행

```bash
cd /opt/openchat-news
docker compose up -d
docker compose logs -f   # 정상 시작 확인
```

---

## 2단계: HTTPS 설정 (외부 접근용)

Vercel(HTTPS)에서 홈서버를 호출하려면 백엔드도 HTTPS여야 합니다.

### 옵션 A: Caddy (권장 — 자동 HTTPS)

```bash
# Ubuntu
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

`/etc/caddy/Caddyfile`:

```
your-domain.com {
    reverse_proxy localhost:8000
}
```

```bash
sudo systemctl enable --now caddy
```

### 옵션 B: Nginx + Let's Encrypt

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

`/etc/nginx/sites-available/openchat`:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    # certbot이 자동으로 ssl 설정을 추가함

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # SSE 스트리밍 필수 설정
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        chunked_transfer_encoding on;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/openchat /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 2-3. 공유기 포트포워딩

공유기 관리 페이지에서:
- 외부 포트 80 → 홈서버 IP:80
- 외부 포트 443 → 홈서버 IP:443

---

## 3단계: 도메인 / DDNS

고정 IP가 없다면 무료 DDNS 서비스 사용:

- **DuckDNS** (추천): https://www.duckdns.org
  - 도메인 발급 후 자동 IP 갱신 스크립트 설치
  ```bash
  # cron으로 5분마다 IP 업데이트
  echo "*/5 * * * * curl -s https://www.duckdns.org/update?domains=YOURDOMAIN&token=YOURTOKEN&ip=" | crontab -
  ```

- **No-IP**: https://www.noip.com

---

## 4단계: Vercel 배포

### 4-1. GitHub에 코드 push

```bash
git add .
git commit -m "deploy"
git push origin main
```

### 4-2. Vercel 프로젝트 생성

1. https://vercel.com → "Add New Project"
2. GitHub 저장소 선택
3. **Framework Preset**: Next.js 자동 감지
4. **Root Directory**: `frontend` 로 변경 (중요)

### 4-3. 환경변수 설정

Vercel 프로젝트 Settings → Environment Variables:

| Key | Value |
|-----|-------|
| `NEXT_PUBLIC_API_URL` | `https://your-domain.com` |

### 4-4. 배포

"Deploy" 클릭. 이후 `git push`할 때마다 자동 재배포됩니다.

---

## 확인 체크리스트

- [ ] `https://your-domain.com/health` → `{"status":"ok"}` 응답
- [ ] Vercel 배포 URL에서 로그인 동작
- [ ] 파일 업로드 → 미리보기 → 커밋 동작
- [ ] 요약 생성 SSE 스트리밍 동작

---

## 업데이트 방법

```bash
# 홈서버에서
cd /opt/openchat-news
git pull
docker compose up -d --build backend
```

프론트엔드는 `git push`만 하면 Vercel이 자동 재배포합니다.
