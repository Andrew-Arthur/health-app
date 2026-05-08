import hmac
import json
import logging
import os
import random
import urllib.error
import urllib.parse
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, List
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator
from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = f"sqlite:///{os.environ.get('DB_PATH', '/data/health.db')}"
API_KEY = os.environ.get("API_KEY", "")
GRIPGAINS_BASE_URL = os.environ.get("GRIPGAINS_BASE_URL", "https://gripgains.ca")
GRIPGAINS_USERNAME = os.environ.get("GRIPGAINS_USERNAME", "")
GRIPGAINS_PASSWORD = os.environ.get("GRIPGAINS_PASSWORD", "")
APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "America/New_York")

logger = logging.getLogger("health_app")
logging.basicConfig(level=logging.INFO)

_gripgains_token: str | None = None


def _lbs(weight: float, unit: str) -> float:
    unit = unit.lower().strip()
    if unit in ("kg", "kilograms", "kilogram"):
        return round(weight * 2.2046226218, 1)
    return round(weight, 1)


def _gripgains_login() -> str:
    url = f"{GRIPGAINS_BASE_URL}/api/auth/token"
    data = urllib.parse.urlencode(
        {"username": GRIPGAINS_USERNAME, "password": GRIPGAINS_PASSWORD}
    ).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        raise RuntimeError(f"GripGains login failed: {exc.code} {body}") from exc
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("GripGains login response missing access_token")
    return str(token)


def _gripgains_post(date_str: str, weight_lbs: float) -> Any:
    global _gripgains_token

    def _do_post(token: str) -> Any:
        url = f"{GRIPGAINS_BASE_URL}/api/bodyweight/"
        body = json.dumps({"date": date_str, "weight_lbs": weight_lbs}).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    if not _gripgains_token:
        _gripgains_token = _gripgains_login()

    try:
        return _do_post(_gripgains_token)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            _gripgains_token = _gripgains_login()
            try:
                return _do_post(_gripgains_token)
            except urllib.error.HTTPError as exc2:
                body = exc2.read().decode()
                raise RuntimeError(f"GripGains post failed: {exc2.code} {body}") from exc2
        body = exc.read().decode()
        raise RuntimeError(f"GripGains post failed: {exc.code} {body}") from exc

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class WeightRecord(Base):
    __tablename__ = "weight"

    id = Column(Integer, primary_key=True, index=True)
    weight = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    date = Column(String, nullable=False)
    source = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


Base.metadata.create_all(bind=engine)


def _auto_post_weight() -> None:
    tz = ZoneInfo(APP_TIMEZONE)
    today = datetime.now(tz).strftime("%Y-%m-%d")

    db = SessionLocal()
    try:
        existing = db.query(WeightRecord).filter(
            WeightRecord.date.like(f"{today}%")
        ).first()
        if existing:
            logger.info("Auto-post: weight already recorded for %s, skipping", today)
            return

        latest = (
            db.query(WeightRecord)
            .order_by(WeightRecord.date.desc())
            .first()
        )
        if not latest:
            logger.info("Auto-post: no existing weight records to base estimate on")
            return

        noise = random.uniform(-1, 1)
        new_weight = round(latest.weight + noise, 1)
        weight_lbs = _lbs(new_weight, latest.unit)

        logger.info(
            "Auto-post: posting %.1f %s (%.1f lbs) for %s based on latest %.1f %s",
            new_weight, latest.unit, weight_lbs, today, latest.weight, latest.unit,
        )

        if not GRIPGAINS_USERNAME or not GRIPGAINS_PASSWORD:
            logger.warning("Auto-post: GripGains credentials not configured, skipping")
            return

        try:
            _gripgains_post(today, weight_lbs)
        except RuntimeError:
            logger.exception("Auto-post: GripGains post failed")
            return

        record = WeightRecord(
            weight=new_weight,
            unit=latest.unit,
            date=today,
            source="auto",
        )
        db.add(record)
        db.commit()
        logger.info("Auto-post: saved record id=%s", record.id)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    tz = ZoneInfo(APP_TIMEZONE)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _auto_post_weight,
        CronTrigger(hour=22, minute=0, timezone=tz),
        id="auto_post_weight",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — auto-post runs daily at 22:00 %s", APP_TIMEZONE)
    yield
    scheduler.shutdown()


app = FastAPI(title="Health App", docs_url=None, redoc_url=None, lifespan=lifespan)
security = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not configured on server",
        )
    if not hmac.compare_digest(credentials.credentials, API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials


class WeightEntry(BaseModel):
    weight: float
    unit: str
    date: str
    source: str

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v)
        except ValueError as exc:
            raise ValueError("date must be ISO 8601 format") from exc
        return v


class WeightResponse(BaseModel):
    id: int
    weight: float
    unit: str
    date: str
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/post/weight", status_code=status.HTTP_201_CREATED)
def post_weight(
    entry: WeightEntry,
    db: Session = Depends(get_db),
    _: HTTPAuthorizationCredentials = Depends(verify_token),
):
    record = WeightRecord(**entry.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)

    if not GRIPGAINS_USERNAME or not GRIPGAINS_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GripGains credentials not configured on server",
        )

    date_only = datetime.fromisoformat(entry.date).strftime("%Y-%m-%d")
    weight_lbs = _lbs(entry.weight, entry.unit)
    try:
        gripgains_result = _gripgains_post(date_only, weight_lbs)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {"id": record.id, "gripgains": gripgains_result}


@app.get("/api/get/weight", response_model=List[WeightResponse])
def get_weights(db: Session = Depends(get_db)):
    return db.query(WeightRecord).order_by(WeightRecord.date.desc()).all()
