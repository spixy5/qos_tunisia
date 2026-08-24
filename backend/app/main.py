import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth_router, upload_router, admin_router, dashboard_router
import app.kpi_engine  # noqa: F401 - side-effect import registers all KPI modules

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Tunisia Mobile Network QoS Platform",
    description="Automated pipeline: ingestion -> cleaning -> spatial join -> KPI engine -> dashboard",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(upload_router.router)
app.include_router(admin_router.router)
app.include_router(dashboard_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}
