import json
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from . import gripgains
from .auth import verify_token
from .config import GRIPGAINS_PASSWORD, GRIPGAINS_USERNAME
from .database import get_db
from .models import GripGainsLog, WeightRecord
from .schemas import GripGainsLogResponse, WeightEntry, WeightResponse

logger = logging.getLogger("health_app.routes")
router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/post/weight", status_code=status.HTTP_201_CREATED)
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

    weight_lbs = gripgains.lbs(entry.weight, entry.unit)
    try:
        gripgains_result = gripgains.post_weight(date_only, weight_lbs)
        db.add(GripGainsLog(
            weight_record_id=record.id,
            date=date_only,
            weight_lbs=weight_lbs,
            source=entry.source,
            success=1,
            response=json.dumps(gripgains_result),
        ))
        db.commit()
    except RuntimeError as exc:
        db.add(GripGainsLog(
            weight_record_id=record.id,
            date=date_only,
            weight_lbs=weight_lbs,
            source=entry.source,
            success=0,
            response=str(exc),
        ))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {"id": record.id, "gripgains": gripgains_result}


@router.get("/get/weight", response_model=List[WeightResponse])
def get_weights(
    db: Session = Depends(get_db),
    _: HTTPAuthorizationCredentials = Depends(verify_token),
):
    return db.query(WeightRecord).order_by(WeightRecord.date.desc()).all()


@router.get("/get/gg-log", response_model=List[GripGainsLogResponse])
def get_gripgains_log(
    db: Session = Depends(get_db),
    _: HTTPAuthorizationCredentials = Depends(verify_token),
):
    rows = db.query(GripGainsLog).order_by(GripGainsLog.created_at.desc()).all()
    results = []
    for row in rows:
        try:
            parsed = json.loads(row.response)
        except (json.JSONDecodeError, TypeError):
            parsed = row.response
        results.append(GripGainsLogResponse(
            id=row.id,
            weight_record_id=row.weight_record_id,
            date=row.date,
            weight_lbs=row.weight_lbs,
            source=row.source,
            success=bool(row.success),
            response=parsed,
            created_at=row.created_at,
        ))
    return results
