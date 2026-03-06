from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str
    passwd: str
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/openchat_news"
    secret_key: str = "changeme-secret-key-for-jwt"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
