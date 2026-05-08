from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String

from .database import Base


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


class GripGainsLog(Base):
    __tablename__ = "gripgains_log"

    id = Column(Integer, primary_key=True, index=True)
    weight_record_id = Column(Integer, nullable=True)
    date = Column(String, nullable=False)
    weight_lbs = Column(Float, nullable=False)
    source = Column(String, nullable=False)
    success = Column(Integer, nullable=False)  # 1 = ok, 0 = error
    response = Column(String, nullable=False)  # JSON or error message
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
