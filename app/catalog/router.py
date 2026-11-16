import os
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.catalog.finishes import FINISHES, VIEWERS
from app.catalog import inventory
from app.catalog.workshops import WORKSHOPS
from app.neon_services import storage

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
    models = {**MOTOS, **{
        row["slug"]: (row["marca"], row["modelo"], row["categoria"])
        for row in inventory.list_inventory()
    }}
    return [
        (slug, brand, model, category)
        for slug, (brand, model, category) in models.items()
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
        moto = inventory.lookup_moto(slug)
        if moto is None:
            raise HTTPException(404, "Moto no encontrada")
        return moto
    brand, model, category = MOTOS[slug]
    source, finishes = FINISHES[slug]
    return {
        "slug": slug, "marca": brand, "modelo": model, "categoria": category,
        "colores": [color for color, _, _ in finishes], "fuente": source,
    }


class DemoNote(BaseModel):
    nota: str = Field(min_length=1, max_length=140)


def run_db_example(operation, value=""):
    if not os.getenv("DATABASE_URL"):
        raise HTTPException(503, "PostgreSQL aún no está configurado.")
    try:
        return inventory.inventory_example(operation, value)
    except SQLAlchemyError as error:
        raise HTTPException(503, "PostgreSQL no respondió.") from error


@api.get("/laboratorio/inventario", tags=["Laboratorio"])
def read_inventory(q: str = ""):
    """Consulta las motos registradas desde Gerencia en PostgreSQL."""
    if not os.getenv("DATABASE_URL"):
        raise HTTPException(503, "PostgreSQL aún no está configurado.")
    try:
        rows = inventory.list_inventory()
    except SQLAlchemyError as error:
        raise HTTPException(503, "PostgreSQL no respondió.") from error
    query = q.strip().casefold()
    return [row for row in rows if query in f"{row['marca']} {row['modelo']}".casefold()]


@api.post("/laboratorio/muestra", status_code=201, tags=["Laboratorio"])
def example_create(note: DemoNote):
    """Ejecuta INSERT en una tabla temporal de PostgreSQL."""
    return {"operacion": "INSERT", "modelo": run_db_example("insert", note.nota)}


@api.patch("/laboratorio/muestra", tags=["Laboratorio"])
def example_update(note: DemoNote):
    """Ejecuta UPDATE en una tabla temporal de PostgreSQL."""
    return {"operacion": "UPDATE", "modelo": run_db_example("update", note.nota)}


@api.delete("/laboratorio/muestra", status_code=204, tags=["Laboratorio"])
def example_delete():
    """Ejecuta DELETE en una tabla temporal de PostgreSQL."""
    run_db_example("delete")
    return Response(status_code=204)


@router.get("/laboratorio", name="lab", include_in_schema=False)
def lab(request: Request):
    return templates.TemplateResponse(request=request, name="lab.html")


@router.get("/gerencia", name="manager", include_in_schema=False)
def manager(request: Request):
    return templates.TemplateResponse(request=request, name="manager.html", context={
        "brands": BRANDS, "categories": CATEGORIES, "values": {},
    })


@router.post("/gerencia/motos", name="manager_create", include_in_schema=False)
def manager_create(
    request: Request,
    marca: str = Form(max_length=30),
    modelo: str = Form(max_length=80),
    categoria: str = Form(max_length=30),
    color: str = Form(max_length=40),
    imagen: UploadFile = File(),
):
    modelo, color = modelo.strip(), color.strip()
    values = dict(marca=marca, modelo=modelo, categoria=categoria, color=color)

    def reject(message, status=400):
        return templates.TemplateResponse(
            request=request, name="manager.html", status_code=status,
            context={"brands": BRANDS, "categories": CATEGORIES, "values": values, "error": message},
        )

    if marca not in BRANDS or categoria not in CATEGORIES or not modelo or not color:
        return reject("Revisa la marca, la categoría, el modelo y el color.")
    if any(marca == b and modelo.casefold() == m.casefold() for b, m, _ in MOTOS.values()):
        return reject("Ese modelo ya está en el catálogo.", 409)
    if not os.getenv("DATABASE_URL"):
        return reject("Configura Neon para poder guardar motos.", 503)
    max_bytes = 5 * 1024 * 1024
    raw = imagen.file.read(max_bytes + 1)
    if len(raw) > max_bytes:
        return reject("La foto supera el máximo de 5 MB.", 413)
    try:
        photo = inventory.prepare_image(raw)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        return reject("Usa una foto fija JPG, PNG o WebP de hasta 20 megapíxeles.")
    try:
        slug = inventory.create_moto(marca, modelo, categoria, color, photo)
    except IntegrityError:
        return reject("Ese modelo ya está registrado.", 409)
    except (SQLAlchemyError, BotoCoreError, ClientError, KeyError):
        return reject("No se pudo guardar el modelo. Revisa la conexión con Neon.", 503)
    return RedirectResponse(str(request.url_for("moto_detail", slug=slug)), status_code=303)


@router.get("/fotos/{slug}", name="inventory_photo", include_in_schema=False)
def inventory_photo(slug: str):
    if not slug.startswith("modelo-") or inventory.lookup_moto(slug) is None:
        raise HTTPException(404, "Foto no encontrada")
    client, bucket = storage()
    url = client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": f"catalogo/{slug}.webp"}, ExpiresIn=900,
    )
    return RedirectResponse(url, headers={"Cache-Control": "no-store"})


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
        row = inventory.lookup_moto(slug)
        if row is None:
            return templates.TemplateResponse(request=request, name="not_found.html", status_code=404)
        return templates.TemplateResponse(request=request, name="detail.html", context={
            "brand": row["marca"], "model": row["modelo"],
            "category_name": CATEGORIES[row["categoria"]], "uploaded_color": row["color"],
            "uploaded_photo": request.url_for("inventory_photo", slug=slug), "views": (),
        })
    brand, model, category = moto
    source, finishes = FINISHES[slug]
    return templates.TemplateResponse(
        request=request,
        name="detail.html",
        context={
            "brand": brand, "model": model, "category": category,
            "category_name": CATEGORIES[category], "finishes": finishes, "source": source,
            "views": WORKSHOPS[slug],
            "angles": (
                ("Delantera derecha", "duke-black-front-right"),
                ("Trasera derecha", "duke-black-rear-right"),
                ("Trasera izquierda", "duke-black-rear-left"),
                ("Lateral izquierdo", "duke-black-left"),
                ("Delantera izquierda", "duke-black-front-left"),
            ) if slug == "ktm-390-duke" else (),
            "viewer": VIEWERS.get(slug),
        },
    )
