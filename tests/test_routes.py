"""Tests for API routes."""
from unittest.mock import patch

import pytest

from tests.conftest import AUTH


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestAuth:
    def test_missing_token_returns_401(self, client):
        assert client.get("/api/health").status_code == 401

    def test_wrong_token_returns_401(self, client):
        r = client.get("/api/health", headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401

    def test_valid_token_accepted(self, client):
        r = client.get("/api/health", headers=AUTH)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_returns_ok(self, client):
        r = client.get("/api/health", headers=AUTH)
        assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /api/post/weight
# ---------------------------------------------------------------------------

VALID_ENTRY = {
    "weight": 185.5,
    "unit": "lbs",
    "date": "2026-05-08T08:30:00-05:00",
    "source": "manual",
}


class TestPostWeight:
    def test_creates_record(self, client):
        mock_result = {"id": 99, "date": "2026-05-08", "weight_lbs": 185.5}
        with patch("app.routes.gripgains.post_weight", return_value=mock_result), \
             patch("app.routes.GRIPGAINS_USERNAME", "user"), \
             patch("app.routes.GRIPGAINS_PASSWORD", "pass"):
            r = client.post("/api/post/weight", json=VALID_ENTRY, headers=AUTH)
        assert r.status_code == 201
        body = r.json()
        assert "id" in body
        assert body["gripgains"] == mock_result

    def test_kg_unit_accepted(self, client):
        entry = {**VALID_ENTRY, "weight": 84.0, "unit": "kg"}
        mock_result = {"id": 1}
        with patch("app.routes.gripgains.post_weight", return_value=mock_result), \
             patch("app.routes.GRIPGAINS_USERNAME", "user"), \
             patch("app.routes.GRIPGAINS_PASSWORD", "pass"):
            r = client.post("/api/post/weight", json=entry, headers=AUTH)
        assert r.status_code == 201

    def test_missing_credentials_returns_500(self, client):
        with patch("app.routes.GRIPGAINS_USERNAME", ""), \
             patch("app.routes.GRIPGAINS_PASSWORD", ""):
            r = client.post("/api/post/weight", json=VALID_ENTRY, headers=AUTH)
        assert r.status_code == 500

    def test_gripgains_failure_returns_502(self, client):
        with patch("app.routes.gripgains.post_weight", side_effect=RuntimeError("upstream down")), \
             patch("app.routes.GRIPGAINS_USERNAME", "user"), \
             patch("app.routes.GRIPGAINS_PASSWORD", "pass"):
            r = client.post("/api/post/weight", json=VALID_ENTRY, headers=AUTH)
        assert r.status_code == 502

    def test_duplicate_day_returns_502(self, client):
        """If the user deleted the GripGains entry themselves, the second post
        should hit GripGains and propagate whatever error it returns."""
        mock_result = {"id": 1}
        with patch("app.routes.gripgains.post_weight", return_value=mock_result), \
             patch("app.routes.GRIPGAINS_USERNAME", "user"), \
             patch("app.routes.GRIPGAINS_PASSWORD", "pass"):
            r1 = client.post("/api/post/weight", json=VALID_ENTRY, headers=AUTH)
            assert r1.status_code == 201

        with patch("app.routes.gripgains.post_weight", side_effect=RuntimeError("duplicate entry")), \
             patch("app.routes.GRIPGAINS_USERNAME", "user"), \
             patch("app.routes.GRIPGAINS_PASSWORD", "pass"):
            r2 = client.post("/api/post/weight", json=VALID_ENTRY, headers=AUTH)
        assert r2.status_code == 502

    def test_invalid_date_returns_422(self, client):
        entry = {**VALID_ENTRY, "date": "not-a-date"}
        r = client.post("/api/post/weight", json=entry, headers=AUTH)
        assert r.status_code == 422

    def test_requires_auth(self, client):
        r = client.post("/api/post/weight", json=VALID_ENTRY)
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/get/weight
# ---------------------------------------------------------------------------

class TestGetWeight:
    def test_empty_list(self, client):
        r = client.get("/api/get/weight", headers=AUTH)
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_created_record(self, client):
        mock_result = {"id": 1}
        with patch("app.routes.gripgains.post_weight", return_value=mock_result), \
             patch("app.routes.GRIPGAINS_USERNAME", "user"), \
             patch("app.routes.GRIPGAINS_PASSWORD", "pass"):
            client.post("/api/post/weight", json=VALID_ENTRY, headers=AUTH)

        r = client.get("/api/get/weight", headers=AUTH)
        assert r.status_code == 200
        records = r.json()
        assert len(records) == 1
        assert records[0]["weight"] == 185.5
        assert records[0]["unit"] == "lbs"

    def test_requires_auth(self, client):
        r = client.get("/api/get/weight")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/get/gg-log
# ---------------------------------------------------------------------------

class TestGetGripGainsLog:
    def test_empty_list(self, client):
        r = client.get("/api/get/gg-log", headers=AUTH)
        assert r.status_code == 200
        assert r.json() == []

    def test_log_recorded_on_success(self, client):
        mock_result = {"id": 99}
        with patch("app.routes.gripgains.post_weight", return_value=mock_result), \
             patch("app.routes.GRIPGAINS_USERNAME", "user"), \
             patch("app.routes.GRIPGAINS_PASSWORD", "pass"):
            client.post("/api/post/weight", json=VALID_ENTRY, headers=AUTH)

        r = client.get("/api/get/gg-log", headers=AUTH)
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) == 1
        assert logs[0]["success"] is True
        assert logs[0]["weight_lbs"] == pytest.approx(185.5, abs=0.1)

    def test_log_recorded_on_failure(self, client):
        with patch("app.routes.gripgains.post_weight", side_effect=RuntimeError("err")), \
             patch("app.routes.GRIPGAINS_USERNAME", "user"), \
             patch("app.routes.GRIPGAINS_PASSWORD", "pass"):
            client.post("/api/post/weight", json=VALID_ENTRY, headers=AUTH)

        r = client.get("/api/get/gg-log", headers=AUTH)
        logs = r.json()
        assert len(logs) == 1
        assert logs[0]["success"] is False

    def test_requires_auth(self, client):
        r = client.get("/api/get/gg-log")
        assert r.status_code == 401
