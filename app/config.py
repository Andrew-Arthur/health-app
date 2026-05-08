import os

DATABASE_URL = f"sqlite:///{os.environ.get('DB_PATH', '/data/health.db')}"
API_KEY = os.environ.get("API_KEY", "")
GRIPGAINS_BASE_URL = os.environ.get("GRIPGAINS_BASE_URL", "https://gripgains.ca")
GRIPGAINS_USERNAME = os.environ.get("GRIPGAINS_USERNAME", "")
GRIPGAINS_PASSWORD = os.environ.get("GRIPGAINS_PASSWORD", "")
APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "America/New_York")
