import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from .database import init_db
from .logging_config import setup_logging
from .routers import admin, auth, events, me

setup_logging()
logger = logging.getLogger(__name__)

VERSION = "5.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting Secret Santa API v{VERSION}")
    await init_db()
    logger.info("Startup completed")
    yield


app = FastAPI(
    title="Secret Santa API",
    description="Backend for a family Secret Santa: events, wish lists and the draw.",
    version=VERSION,
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(events.router)
app.include_router(admin.router)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["General"], summary="Health check")
async def health_check():
    return {"status": "healthy"}
