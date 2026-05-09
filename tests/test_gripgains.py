"""Tests for the gripgains helper module."""
import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

import app.gripgains as gg


# ---------------------------------------------------------------------------
# lbs()
# ---------------------------------------------------------------------------

class TestLbs:
    def test_lbs_passthrough(self):
        assert gg.lbs(185.5, "lbs") == 185.5

    def test_kg_converted(self):
        assert gg.lbs(84.0, "kg") == pytest.approx(185.2, abs=0.1)

    def test_kilogram_alias(self):
        assert gg.lbs(84.0, "kilogram") == pytest.approx(185.2, abs=0.1)

    def test_kilograms_alias(self):
        assert gg.lbs(84.0, "kilograms") == pytest.approx(185.2, abs=0.1)

    def test_case_insensitive(self):
        assert gg.lbs(84.0, "KG") == pytest.approx(185.2, abs=0.1)

    def test_rounds_to_one_decimal(self):
        result = gg.lbs(185.123, "lbs")
        assert result == 185.1


# ---------------------------------------------------------------------------
# _login()
# ---------------------------------------------------------------------------

def _mock_response(payload: dict, status: int = 200):
    body = json.dumps(payload).encode()
    mock = MagicMock()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    mock.read.return_value = body
    mock.status = status
    return mock


class TestLogin:
    def test_returns_token(self):
        with patch("urllib.request.urlopen", return_value=_mock_response({"access_token": "tok123"})):
            token = gg._login()
        assert token == "tok123"

    def test_raises_on_missing_token(self):
        with patch("urllib.request.urlopen", return_value=_mock_response({})):
            with pytest.raises(RuntimeError, match="missing access_token"):
                gg._login()

    def test_raises_on_http_error(self):
        err = urllib.error.HTTPError(url="", code=401, msg="Unauthorized", hdrs=None, fp=BytesIO(b"bad creds"))
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(RuntimeError, match="GripGains login failed: 401"):
                gg._login()


# ---------------------------------------------------------------------------
# post_weight()  (public entry point)
# ---------------------------------------------------------------------------

class TestPostWeight:
    def setup_method(self):
        # Reset module-level token cache before each test
        gg._token = None

    def test_posts_successfully(self):
        login_resp = _mock_response({"access_token": "tok"})
        post_resp = _mock_response({"id": 1, "date": "2026-05-08", "weight_lbs": 185.5})

        with patch("urllib.request.urlopen", side_effect=[login_resp, post_resp]):
            result = gg.post_weight("2026-05-08", 185.5)
        assert result["id"] == 1

    def test_retries_on_401(self):
        """If the cached token is stale (401), should re-login and retry."""
        gg._token = "stale-token"

        relogin_resp = _mock_response({"access_token": "fresh"})
        post_resp = _mock_response({"id": 2})

        unauth_err = urllib.error.HTTPError(url="", code=401, msg="Unauth", hdrs=None, fp=BytesIO(b""))

        with patch("urllib.request.urlopen", side_effect=[unauth_err, relogin_resp, post_resp]):
            result = gg.post_weight("2026-05-08", 185.5)
        assert result["id"] == 2

    def test_raises_on_non_401_http_error(self):
        gg._token = "tok"
        err = urllib.error.HTTPError(url="", code=500, msg="Server Error", hdrs=None, fp=BytesIO(b"oops"))

        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(RuntimeError, match="GripGains post failed: 500"):
                gg.post_weight("2026-05-08", 185.5)
