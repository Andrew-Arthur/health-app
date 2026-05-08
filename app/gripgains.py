import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import GRIPGAINS_BASE_URL, GRIPGAINS_PASSWORD, GRIPGAINS_USERNAME

_token: str | None = None


def lbs(weight: float, unit: str) -> float:
    """Convert weight to lbs if needed."""
    unit = unit.lower().strip()
    if unit in ("kg", "kilograms", "kilogram"):
        return round(weight * 2.2046226218, 1)
    return round(weight, 1)


def _login() -> str:
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


def _do_post(token: str, date_str: str, weight_lbs: float) -> Any:
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


def post_weight(date_str: str, weight_lbs: float) -> Any:
    """Post a bodyweight entry to GripGains. Re-auths once on 401."""
    global _token

    if not _token:
        _token = _login()

    try:
        return _do_post(_token, date_str, weight_lbs)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            _token = _login()
            try:
                return _do_post(_token, date_str, weight_lbs)
            except urllib.error.HTTPError as exc2:
                body = exc2.read().decode()
                raise RuntimeError(f"GripGains post failed: {exc2.code} {body}") from exc2
        body = exc.read().decode()
        raise RuntimeError(f"GripGains post failed: {exc.code} {body}") from exc
