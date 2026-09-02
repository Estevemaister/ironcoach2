import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    cors_origins: str
    auth_cookie_name: str
    cookie_secure: bool
    cookie_samesite: str
    strava_client_id: str
    strava_client_secret: str
    strava_redirect_uri: str
    strava_webhook_verify_token: str
    frontend_url: str


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
    cookie_secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    cookie_samesite=os.getenv("COOKIE_SAMESITE", "lax"),
    strava_client_id=os.getenv("STRAVA_CLIENT_ID", ""),
    strava_client_secret=os.getenv("STRAVA_CLIENT_SECRET", ""),
    strava_redirect_uri=os.getenv("STRAVA_REDIRECT_URI", "https://ironcoach-api.onrender.com/integrations/strava/callback"),
    strava_webhook_verify_token=os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN", ""),
    frontend_url=os.getenv("FRONTEND_URL", "https://estevemaister.github.io/ironcoach2/"),
)
