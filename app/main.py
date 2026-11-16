import logging
import mimetypes
from hashlib import sha256
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles

from app.accessories.router import router as accessory_router
from app.catalog.router import router as catalog_router
from app.catalog.router import api as catalog_api
from app.catalog.router import templates
from app.catalog.sales_routes import router as moto_sales_router
from app.neon_services import check_postgres, check_storage

app = FastAPI(title="Moto Garaje")
logger = logging.getLogger(__name__)
mimetypes.add_type("image/webp", ".webp")


static_dir = Path(__file__).parent / "static"
templates.env.globals["asset_versions"] = {
    filename: sha256((static_dir / filename).read_bytes()).hexdigest()[:12]
    for filename in ("store.css", "store.js", "lab.js")
}
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.include_router(catalog_router)
app.include_router(catalog_api)
app.include_router(moto_sales_router)
app.include_router(accessory_router)


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
