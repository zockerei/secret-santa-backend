from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import logging

from .config import settings, setup_logging
from .database import init_db
from .routers import auth, admin, users

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="""
    ## Secret Santa Gift Exchange Backend API

    A comprehensive backend system for managing Secret Santa gift exchanges with intelligent assignment algorithms
    and admin controls.

    ### Features:
    * **User Authentication**: Secure JWT-based authentication system
    * **Smart Assignments**: Avoids repeat assignments from previous events
    * **Admin Controls**: Complete event and user management
    * **Flexible Events**: Support for past, present, and future events
    * **Message System**: Optional participant messages and wishes

    ### User Roles:
    * **Regular Users**: Can join events, write messages, and view their assignments
    * **Administrators**: Full control over events, users, and assignments

    ### Workflow:
    1. Admin creates events and manages participants
    2. Users join events and optionally write messages
    3. Admin manually triggers assignments when ready
    4. Users can view their gift recipient assignments
    """,
    version=settings.app_version,
    debug=settings.debug,
    contact={
        "name": "Secret Santa API",
        "email": "admin@example.com"
    },
    license_info={
        "name": "MIT License"
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(users.router)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    await init_db()
    logger.info("Application startup completed")


@app.get(
    "/",
    summary="API Documentation",
    description="Redirects to the interactive API documentation.",
    tags=["General"]
)
async def root():
    return RedirectResponse(url="/docs")


@app.get(
    "/health",
    summary="Health Check",
    description="Returns the API service health status.",
    tags=["General"]
)
async def health_check():
    return {"status": "healthy"}
