import json
import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from . import gripgains
from .config import APP_TIMEZONE, GRIPGAINS_PASSWORD, GRIPGAINS_USERNAME
from .database import SessionLocal
from .models import GripGainsLog, WeightRecord

logger = logging.getLogger("health_app.scheduler")


def auto_post_weight() -> None:
    tz = ZoneInfo(APP_TIMEZONE)
    today = datetime.now(tz).strftime("%Y-%m-%d")

    db = SessionLocal()
    try:
        existing = (
            db.query(WeightRecord)
            .filter(WeightRecord.date.like(f"{today}%"))
            .first()
        )
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
        weight_lbs = gripgains.lbs(new_weight, latest.unit)

        logger.info(
            "Auto-post: posting %.1f %s (%.1f lbs) for %s based on latest %.1f %s",
            new_weight, latest.unit, weight_lbs, today, latest.weight, latest.unit,
        )

        if not GRIPGAINS_USERNAME or not GRIPGAINS_PASSWORD:
            logger.warning("Auto-post: GripGains credentials not configured, skipping")
            return

        try:
            result = gripgains.post_weight(today, weight_lbs)
            log = GripGainsLog(
                weight_record_id=None,
                date=today,
                weight_lbs=weight_lbs,
                source="auto",
                success=1,
                response=json.dumps(result),
            )
        except RuntimeError as exc:
            logger.exception("Auto-post: GripGains post failed")
            log = GripGainsLog(
                weight_record_id=None,
                date=today,
                weight_lbs=weight_lbs,
                source="auto",
                success=0,
                response=str(exc),
            )
            db.add(log)
            db.commit()
            return

        record = WeightRecord(
            weight=new_weight,
            unit=latest.unit,
            date=today,
            source="auto",
        )
        db.add(record)
        db.flush()
        log.weight_record_id = record.id
        db.add(log)
        db.commit()
        logger.info("Auto-post: saved record id=%s", record.id)
    finally:
        db.close()
