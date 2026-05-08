# health-app

A FastAPI service that logs body weight to SQLite and forwards entries to [Grip Gains](https://gripgains.ca). Hosted at `health.andrew-arthur.com`, deployed via the [homelab](https://github.com/Andrew-Arthur/homelab) repo.

## Endpoints

### `POST /api/post/weight`

Record a weight measurement. Requires authentication.

**Headers**

```
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

**Body**

```json
{
    "weight": 185.5,
    "unit": "lbs",
    "date": "2026-05-08T08:30:00-05:00",
    "source": "manual"
}
```

- `weight` — number (float)
- `unit` — `"lbs"` or `"kg"` (auto-converted to lbs before posting to Grip Gains)
- `date` — ISO 8601 string
- `source` — free-form string (e.g. `"manual"`, `"apple_health"`, `"auto"`)

**Response `201`**

```json
{
  "id": 1,
  "gripgains": { ... }
}
```

`gripgains` contains the raw response body from the Grip Gains API.

**Example**

```bash
curl -X POST https://health.andrew-arthur.com/api/post/weight \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"weight": 185.5, "unit": "lbs", "date": "2026-05-08T08:30:00-05:00", "source": "manual"}'
```

---

### `GET /api/get/gripgains-log`

Returns all Grip Gains post attempts, newest first. No authentication required.

**Response `200`**

```json
[
  {
    "id": 1,
    "weight_record_id": 1,
    "date": "2026-05-08",
    "weight_lbs": 185.5,
    "source": "manual",
    "success": true,
    "response": { ... },
    "created_at": "2026-05-08T13:30:00Z"
  }
]
```

- `weight_record_id` — ID of the local weight record that triggered this post (`null` for failed auto-posts)
- `success` — `true` if Grip Gains accepted the post, `false` if it errored
- `response` — parsed Grip Gains response body on success, error message string on failure

---

### `GET /api/get/weight`

Returns all logged weight records, newest first. No authentication required.

**Response `200`**

```json
[
    {
        "id": 1,
        "weight": 185.5,
        "unit": "lbs",
        "date": "2026-05-08T08:30:00-05:00",
        "source": "manual",
        "created_at": "2026-05-08T13:30:00Z"
    }
]
```

---

### `GET /health`

Liveness probe. Returns `{"status": "ok"}`.

---

## Automation

Every day at 10:00 PM (`APP_TIMEZONE`), if no weight has been recorded for the day, the service:

1. Takes the most recent logged weight
2. Adds random noise in the range (-1, 1) in the same unit
3. Posts it to Grip Gains
4. Saves the result locally with `source: "auto"`

---

## Environment variables

| Variable             | Required | Default                | Description                                |
| -------------------- | -------- | ---------------------- | ------------------------------------------ |
| `API_KEY`            | Yes      | —                      | Bearer token for `POST /api/post/weight`   |
| `GRIPGAINS_USERNAME` | Yes      | —                      | Grip Gains login email                     |
| `GRIPGAINS_PASSWORD` | Yes      | —                      | Grip Gains password                        |
| `DB_PATH`            | No       | `/data/health.db`      | SQLite database path                       |
| `PORT`               | No       | `8080`                 | HTTP port                                  |
| `GRIPGAINS_BASE_URL` | No       | `https://gripgains.ca` | Grip Gains base URL                        |
| `APP_TIMEZONE`       | No       | `America/New_York`     | Timezone for the daily auto-post scheduler |

Copy `.env.example` to `.env` for local development. Never commit `.env`.

---

## Generating an API key

```bash
# PowerShell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Max 256 }))

# Linux / macOS
openssl rand -base64 32
```

---

## Deployment

This service is deployed as a Kubernetes app in the [homelab](https://github.com/Andrew-Arthur/homelab) repo under `kubernetes/apps/health-app/`.

The image is published to GHCR on every push to `main`:

```
ghcr.io/andrew-arthur/health-app:sha-<git-sha>
```

After a new image is pushed, update `kubernetes/apps/health-app/kustomization.yaml` in the homelab repo with the new SHA (both `?ref=` and `newTag`).

Secrets (`API_KEY`, `GRIPGAINS_USERNAME`, `GRIPGAINS_PASSWORD`) are managed as GitHub Actions secrets in the homelab repo and applied automatically on deploy.
