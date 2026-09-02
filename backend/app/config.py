import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    cors_origins: str
    auth_cookie_name: str


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./ironcoach.db")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url

settings = Settings(
    database_url=_database_url(),
    jwt_secret=os.getenv("JWT_SECRET", "dev-only-change-me"),
    cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:8000"),
    auth_cookie_name=os.getenv("AUTH_COOKIE_NAME", "ironcoach_session"),
)
