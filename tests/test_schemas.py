"""Tests for Pydantic schemas."""
import pytest
from pydantic import ValidationError

from app.schemas import WeightEntry


class TestWeightEntry:
    def test_valid_entry(self):
        e = WeightEntry(weight=185.5, unit="lbs", date="2026-05-08T08:30:00-05:00", source="manual")
        assert e.weight == 185.5

    def test_invalid_date_raises(self):
        with pytest.raises(ValidationError, match="date must be ISO 8601"):
            WeightEntry(weight=185.5, unit="lbs", date="08/05/2026", source="manual")

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            WeightEntry(weight=185.5, unit="lbs", date="2026-05-08T08:30:00Z")

    def test_date_only_iso_accepted(self):
        # Python's fromisoformat accepts plain dates too
        e = WeightEntry(weight=185.5, unit="lbs", date="2026-05-08", source="manual")
        assert e.date == "2026-05-08"

    def test_negative_weight_accepted(self):
        # No domain constraint on sign — schema allows it
        e = WeightEntry(weight=-1.0, unit="lbs", date="2026-05-08", source="test")
        assert e.weight == -1.0
