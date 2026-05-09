import logging
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from app.config import APP_TIMEZONE
from app.database import Base, engine
from app.routes import router
from app.scheduler import auto_post_weight

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("health_app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    tz = ZoneInfo(APP_TIMEZONE)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        auto_post_weight,
        CronTrigger(hour=22, minute=0, timezone=tz),
        id="auto_post_weight",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started � auto-post runs daily at 22:00 %s", APP_TIMEZONE)
    yield
    scheduler.shutdown()


app = FastAPI(title="Health App", docs_url="/api/docs", redoc_url="/api/redoc", lifespan=lifespan)
app.include_router(router, prefix="/api")
