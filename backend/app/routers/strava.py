from datetime import datetime, timezone
import json
import secrets
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base

from ..config import settings
from ..main import SessionLocal, User, user_from_request

router = APIRouter(prefix="/integrations/strava", tags=["strava"])

# Integration tables live in the same database and are intentionally small for MVP.
IntegrationBase = declarative_base()

class StravaConnection(IntegrationBase):
    __tablename__ = "strava_connections"
    id = Column(Integer, primary_key=True)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), unique=True, nullable=False)
    strava_athlete_id = Column(Integer, unique=True, nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    expires_at = Column(Integer, nullable=False)
    scope = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class StravaActivity(IntegrationBase):
    __tablename__ = "strava_activities"
    id = Column(Integer, primary_key=True)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=False, index=True)
    strava_id = Column(Integer, unique=True, nullable=False, index=True)
    sport = Column(String(40))
    name = Column(String(255))
    start_date = Column(DateTime)
    duration_sec = Column(Integer, default=0)
    distance_m = Column(Integer, default=0)
    avg_hr = Column(Integer)
    avg_power = Column(Integer)
    raw_json = Column(Text, default="{}")
    imported_at = Column(DateTime, default=datetime.utcnow)

# create_all is safe for the additive MVP tables and keeps the deploy migration-free.
from ..main import engine
IntegrationBase.metadata.create_all(engine)


def _require_config():
    if not settings.strava_client_id or not settings.strava_client_secret:
        raise HTTPException(503, "Strava integration is not configured yet")


def _api(path, token=None, method="GET", data=None):
    url = "https://api-v3.strava.com" + path
    body = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode()) if r.readable() else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")
        raise HTTPException(e.code, f"Strava API error: {detail[:500]}")


def _token_exchange(code=None, refresh_token=None):
    _require_config()
    data = {
        "client_id": settings.strava_client_id,
        "client_secret": settings.strava_client_secret,
        "grant_type": "authorization_code" if code else "refresh_token",
    }
    data["code" if code else "refresh_token"] = code or refresh_token
    return _api("/oauth/token", method="POST", data=data)


def _valid_token(conn):
    now = int(datetime.now(timezone.utc).timestamp())
    if conn.expires_at > now + 300:
        return conn.access_token
    data = _token_exchange(refresh_token=conn.refresh_token)
    conn.access_token = data["access_token"]
    conn.refresh_token = data.get("refresh_token", conn.refresh_token)
    conn.expires_at = data["expires_at"]
    return conn.access_token


@router.get("/connect")
def connect(request: Request):
    _require_config()
    db = SessionLocal()
    try:
        user = user_from_request(request, db)
        state = secrets.token_urlsafe(32)
        # State is bound to the authenticated athlete in a short-lived signed payload.
        from jose import jwt
        signed = jwt.encode({"state": state, "athlete_id": user.athlete.id, "exp": datetime.now(timezone.utc).timestamp() + 600}, settings.jwt_secret, algorithm="HS256")
        params = {
            "client_id": settings.strava_client_id,
            "redirect_uri": settings.strava_redirect_uri,
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": "activity:read_all",
            "state": signed,
        }
        return {"authorization_url": "https://www.strava.com/oauth/authorize?" + urllib.parse.urlencode(params)}
    finally:
        db.close()


@router.get("/callback")
def callback(code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        return RedirectResponse(settings.frontend_url + "?strava=denied")
    if not code or not state:
        raise HTTPException(400, "Missing Strava OAuth parameters")
    from jose import jwt
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=["HS256"])
        athlete_id = int(payload["athlete_id"])
    except Exception:
        raise HTTPException(400, "Invalid or expired OAuth state")
    data = _token_exchange(code=code)
    athlete = data.get("athlete") or {}
    strava_id = athlete.get("id")
    if not strava_id:
        raise HTTPException(400, "Strava did not return athlete information")
    db = SessionLocal()
    try:
        conn = db.query(StravaConnection).filter_by(athlete_id=athlete_id).first()
        if not conn:
            conn = StravaConnection(athlete_id=athlete_id, strava_athlete_id=strava_id, access_token=data["access_token"], refresh_token=data["refresh_token"], expires_at=data["expires_at"], scope=data.get("scope", ""))
            db.add(conn)
        else:
            conn.strava_athlete_id = strava_id
            conn.access_token = data["access_token"]
            conn.refresh_token = data["refresh_token"]
            conn.expires_at = data["expires_at"]
            conn.scope = data.get("scope", "")
        db.commit()
    finally:
        db.close()
    return RedirectResponse(settings.frontend_url + "?strava=connected")


@router.get("/status")
def status(request: Request):
    db = SessionLocal()
    try:
        athlete = user_from_request(request, db).athlete
        conn = db.query(StravaConnection).filter_by(athlete_id=athlete.id).first()
        return {"connected": bool(conn), "strava_athlete_id": conn.strava_athlete_id if conn else None, "scope": conn.scope if conn else None}
    finally:
        db.close()


@router.post("/import")
def import_activities(request: Request):
    db = SessionLocal()
    try:
        athlete = user_from_request(request, db).athlete
        conn = db.query(StravaConnection).filter_by(athlete_id=athlete.id).first()
        if not conn:
            raise HTTPException(400, "Connect Strava first")
        token = _valid_token(conn)
        db.commit()
        activities = _api("/api/v3/athlete/activities?per_page=100", token=token)
        imported = 0
        for x in activities:
            sid = int(x["id"])
            row = db.query(StravaActivity).filter_by(strava_id=sid).first()
            if not row:
                row = StravaActivity(athlete_id=athlete.id, strava_id=sid)
                db.add(row)
                imported += 1
            row.sport = x.get("sport_type") or x.get("type")
            row.name = x.get("name")
            row.duration_sec = int(x.get("moving_time") or x.get("elapsed_time") or 0)
            row.distance_m = int(x.get("distance") or 0)
            row.avg_hr = int(x["average_heartrate"]) if x.get("average_heartrate") else None
            row.avg_power = int(x["average_watts"]) if x.get("average_watts") else None
            row.raw_json = json.dumps(x, separators=(",", ":"))
        db.commit()
        return {"ok": True, "imported": imported, "total_received": len(activities)}
    finally:
        db.close()


@router.get("/webhook")
def webhook_verify(request: Request):
    # Strava validates the callback with hub.challenge; respond immediately.
    params = request.query_params
    if settings.strava_webhook_verify_token and params.get("hub.verify_token") != settings.strava_webhook_verify_token:
        raise HTTPException(403, "Invalid verify token")
    return {"hub.challenge": params.get("hub.challenge", "")}


@router.post("/webhook")
def webhook_event(payload: dict):
    # Acknowledge quickly; processing can be moved to a worker as volume grows.
    return {"ok": True}
