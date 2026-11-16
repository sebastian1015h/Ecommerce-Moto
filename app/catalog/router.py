from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.catalog.finishes import FINISHES
from app.catalog.workshops import WORKSHOPS

router = APIRouter(default_response_class=HTMLResponse)
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")

CATEGORIES = {
    "urbanas": "Urbanas",
    "scooters": "Scooters",
    "deportivas": "Deportivas",
    "aventura": "Aventura",
}

# Modelos de demostración. El inventario se incorporará desde PostgreSQL.
MOTOS = {
    "ktm-390-duke": ("KTM", "390 Duke", "urbanas"),
    "suzuki-gixxer-250": ("Suzuki", "Gixxer 250", "urbanas"),
    "honda-pcx-160": ("Honda", "PCX 160", "scooters"),
    "yamaha-nmax": ("Yamaha", "NMAX", "scooters"),
    "kawasaki-ninja-zx-4rr": ("Kawasaki", "Ninja ZX-4RR", "deportivas"),
    "suzuki-v-strom-250-sx": ("Suzuki", "V-Strom 250 SX", "aventura"),
}
BRANDS = ("Suzuki", "Honda", "KTM", "Yamaha", "Kawasaki")
api = APIRouter(prefix="/api", default_response_class=JSONResponse)


def filter_motos(categoria: str, marca: str, q: str):
    query = q.strip().casefold()
    return [
        (slug, brand, model, category)
        for slug, (brand, model, category) in MOTOS.items()
        if (not categoria or category == categoria)
        and (not marca or brand == marca)
        and query in f"{brand} {model}".casefold()
    ]


@api.get("/motos", tags=["Catálogo"])
def list_motos(categoria: str = "", marca: str = "", q: str = ""):
    return [
        {"slug": slug, "marca": brand, "modelo": model, "categoria": category}
        for slug, brand, model, category in filter_motos(categoria, marca, q)
    ]


@api.get("/motos/{slug}", tags=["Catálogo"])
def get_moto(slug: str):
    if slug not in MOTOS:
        raise HTTPException(404, "Moto no encontrada")
    brand, model, category = MOTOS[slug]
    source, finishes = FINISHES[slug]
    return {
        "slug": slug, "marca": brand, "modelo": model, "categoria": category,
        "colores": [color for color, _, _ in finishes], "fuente": source,
    }


class DemoNote(BaseModel):
    nota: str = Field(min_length=1, max_length=140)


@api.post("/laboratorio/muestra", status_code=201, tags=["Laboratorio"])
def simulate_create(note: DemoNote):
    """Simula la creación de una muestra sin persistencia."""
    return {"operacion": "creada", **note.model_dump()}


@api.patch("/laboratorio/muestra", tags=["Laboratorio"])
def simulate_update(note: DemoNote):
    """Simula la actualización de una muestra sin persistencia."""
    return {"operacion": "actualizada", **note.model_dump()}


@api.delete("/laboratorio/muestra", status_code=204, tags=["Laboratorio"])
def simulate_delete():
    """Simula la eliminación de una muestra sin persistencia."""
    return Response(status_code=204)


@router.get("/laboratorio", name="lab", include_in_schema=False)
def lab(request: Request):
    return templates.TemplateResponse(request=request, name="lab.html")


@router.get("/", name="home", include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(
        request=request, name="home.html", context={"categories": CATEGORIES, "brands": BRANDS}
    )


@router.get("/motos", name="catalog", include_in_schema=False)
def catalog(request: Request, categoria: str = "", marca: str = "", q: str = ""):
    motos = filter_motos(categoria, marca, q)
    return templates.TemplateResponse(
        request=request,
        name="catalog.html",
        context={
            "categories": CATEGORIES, "brands": BRANDS, "motos": motos, "finishes": FINISHES,
            "category": categoria, "brand_filter": marca, "query": q.strip(),
        },
    )


@router.get("/motos/{slug}", name="moto_detail", include_in_schema=False)
def moto_detail(request: Request, slug: str):
    moto = MOTOS.get(slug)
    if moto is None:
        return templates.TemplateResponse(request=request, name="not_found.html", status_code=404)
    brand, model, category = moto
    source, finishes = FINISHES[slug]
    return templates.TemplateResponse(
        request=request,
        name="detail.html",
        context={
            "brand": brand, "model": model, "category": category,
            "category_name": CATEGORIES[category], "finishes": finishes, "source": source,
            "views": WORKSHOPS[slug],
        },
    )
