import hmac
import os
from datetime import datetime, timezone
from typing import List

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator
from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = f"sqlite:///{os.environ.get('DB_PATH', '/data/health.db')}"
API_KEY = os.environ.get("API_KEY", "")

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

app = FastAPI(title="Health App", docs_url=None, redoc_url=None)
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
    return {"id": record.id}


@app.get("/api/get/weight", response_model=List[WeightResponse])
def get_weights(db: Session = Depends(get_db)):
    return db.query(WeightRecord).order_by(WeightRecord.date.desc()).all()
