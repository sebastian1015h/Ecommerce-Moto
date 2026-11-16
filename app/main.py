import logging
import mimetypes
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles

from app.catalog.router import router as catalog_router
from app.catalog.router import api as catalog_api
from app.neon_services import check_postgres, check_storage

app = FastAPI(title="Moto Garaje")
logger = logging.getLogger(__name__)
mimetypes.add_type("image/webp", ".webp")


app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(catalog_router)
app.include_router(catalog_api)


@app.get("/health/live")
def liveness():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness(response: Response):
    services = {}
    for name, check in (("postgres", check_postgres), ("object_storage", check_storage)):
        try:
            check()
        except Exception as error:
            logger.warning("Neon %s readiness failed (%s)", name, type(error).__name__)
            services[name] = "unavailable"
            response.status_code = 503
        else:
            services[name] = "ok"
    return services
