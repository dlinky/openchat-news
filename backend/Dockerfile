# ── 빌드 스테이지 ──────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ── 런타임 스테이지 ────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# 빌드 스테이지의 venv만 복사
COPY --from=builder /app/.venv /app/.venv

# 소스 복사 (.env는 docker-compose에서 환경변수로 주입)
COPY app/ ./app/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
