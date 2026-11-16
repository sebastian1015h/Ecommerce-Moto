import re
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import SQLAlchemyError

from app.accessories.pricing import price
from app.accessories.router import check_origin
from app.catalog import inventory, sales
from app.catalog.router import MOTOS, templates

router = APIRouter(default_response_class=HTMLResponse, include_in_schema=False)


def model_identity(slug):
    if slug in MOTOS:
        return MOTOS[slug][:2]
    row = inventory.lookup_moto(slug)
    if row is None:
        raise HTTPException(404, "Moto no encontrada.")
    return row["marca"], row["modelo"]


def order_page(request, slug, color, order_id, values=None, error=None, status_code=200):
    brand, model = model_identity(slug)
    offers = {row["color"]: row for row in sales.offers(slug)}
    selected = offers.get(color)
    if color is None and offers:
        selected = next((offer for offer in offers.values() if offer["stock"] and offer["price_cop"]), None)
    return templates.TemplateResponse(
        request=request, name="moto_checkout.html", status_code=status_code,
        headers={"Cache-Control": "private, no-store"}, context={
            "brand": brand, "model": model, "slug": slug, "offer": selected, "price": price,
            "order_id": order_id, "values": values or {}, "error": error,
        },
    )


@router.get("/motos/{slug}/comprar", name="moto_checkout")
def moto_checkout(request: Request, slug: str, color: str | None = None):
    return order_page(request, slug, color, uuid4())


@router.post("/motos/{slug}/comprar", name="moto_checkout_submit")
def moto_checkout_submit(
    request: Request,
    slug: str,
    color: Annotated[str, Form(max_length=40)],
    order_id: Annotated[UUID, Form()],
    expected_price: Annotated[int, Form(ge=1, le=1000000000)],
    customer_name: Annotated[str, Form(max_length=100)],
    email: Annotated[str, Form(max_length=150)],
    phone: Annotated[str, Form(max_length=30)],
):
    check_origin(request)
    brand, model = model_identity(slug)
    customer = {"customer_name": customer_name.strip(), "email": email.strip(), "phone": phone.strip()}
    if (
        not customer["customer_name"] or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", customer["email"])
        or not 7 <= sum(char.isdigit() for char in phone) <= 15
    ):
        return order_page(request, slug, color, order_id, customer, "Revisa los datos de contacto.", 422)
    try:
        sales.place_order(order_id, slug, color, brand, model, expected_price, customer)
    except sales.MotoOrderConflict as error:
        return order_page(request, slug, color, order_id, customer, str(error), 409)
    except (SQLAlchemyError, KeyError) as error:
        raise HTTPException(503, "No se pudo confirmar el pedido.") from error
    url = request.url_for("moto_receipt", order_id=order_id)
    return RedirectResponse(str(url), status_code=303)


@router.get("/motos/pedido/{order_id}", name="moto_receipt")
def moto_receipt(request: Request, order_id: UUID):
    receipt = sales.order_receipt(order_id)
    if receipt is None:
        raise HTTPException(404, "Pedido no encontrado.")
    return templates.TemplateResponse(
        request=request, name="moto_receipt.html", headers={
            "Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer",
        }, context={"order": receipt, "reference": order_id.hex[:12].upper(), "price": price},
    )


def inventory_page(request, error=None, status_code=200):
    identities = {
        **{slug: (brand, model) for slug, (brand, model, _) in MOTOS.items()},
        **{row["slug"]: (row["marca"], row["modelo"]) for row in inventory.list_inventory()},
    }
    rows = [
        {**row, "brand": identities[row["slug"]][0], "model": identities[row["slug"]][1]}
        for row in sales.offers() if row["slug"] in identities
    ]
    return templates.TemplateResponse(
        request=request, name="moto_stock.html", status_code=status_code, context={
            "rows": rows, "error": error, "updated": request.query_params.get("actualizado") == "1",
        },
    )


@router.get("/gerencia/inventario-motos", name="moto_stock")
def moto_stock(request: Request):
    return inventory_page(request)


@router.post("/gerencia/inventario-motos", name="moto_stock_change")
def moto_stock_change(
    request: Request,
    slug: Annotated[str, Form(max_length=80)],
    color: Annotated[str, Form(max_length=40)],
    stock: Annotated[int, Form(ge=0, le=10000)],
    previous_stock: Annotated[int, Form(ge=0, le=10000)],
    price_cop: Annotated[int | None, Form(ge=1, le=1000000000)] = None,
    previous_price: Annotated[int | None, Form(ge=1, le=1000000000)] = None,
):
    check_origin(request)
    try:
        updated = sales.change_offer(slug, color, price_cop, stock, previous_price, previous_stock)
    except (SQLAlchemyError, KeyError) as error:
        raise HTTPException(503, "No se pudo actualizar la variante.") from error
    if updated is None:
        return inventory_page(request, "El inventario cambió. Revisa el precio y stock actuales.", 409)
    url = request.url_for("moto_stock").include_query_params(actualizado="1")
    return RedirectResponse(str(url), status_code=303)
