import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import store
from app.routers import analytics, decisions, dns, migrations, pricing, settings as settings_router
from app.routers.costs import router as costs_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await store.connect()
    yield
    await store.close()


app = FastAPI(
    title="CloudOptima API",
    description="Demo-first multi-cloud spot cost analysis and migration simulation API.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
for api_router in (
    settings_router.router,
    pricing.router,
    costs_router,
    decisions.router,
    analytics.router,
    migrations.router,
    dns.router,
):
    app.include_router(api_router)
