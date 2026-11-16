import json
import re
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import SQLAlchemyError

from app.accessories import inventory
from app.accessories.invoice import invoice_preview, invoice_preview_image
from app.accessories.pricing import price, summarize_cart
from app.accessories.products import CATEGORIES, COMPATIBILITY
from app.catalog.router import templates

router = APIRouter(default_response_class=HTMLResponse, include_in_schema=False)
COOKIE = "moto_garaje_accessories"
MAX_QUANTITY = 99
Quantity = Annotated[int, Form(ge=0, le=MAX_QUANTITY)]
SHIPPING = {"bogota": ("Bogotá", 12000), "nacional": ("Otras ciudades", 22000)}


def products():
    try:
        return {row["variant_id"]: row for row in inventory.list_products()}
    except (KeyError, SQLAlchemyError) as error:
        raise HTTPException(503, "El inventario de accesorios no está disponible.") from error


def cart_from_cookie(request, product_map):
    try:
        cart = json.loads(request.cookies.get(COOKIE, "{}"))
    except ValueError:
        return {}
    if not isinstance(cart, dict):
        return {}
    return {
        key: quantity for key, quantity in cart.items()
        if key in product_map and type(quantity) is int and 0 < quantity <= MAX_QUANTITY
    }


def grouped_products(product_map):
    items = {}
    for variant in product_map.values():
        product = items.setdefault(variant["sku"], {**variant, "stock": 0, "variants": []})
        product["variants"].append(variant)
        product["stock"] += variant["stock"]
    return items


def view_cart(request, product_map, cart, error=None, status_code=200):
    drawer = request.headers.get("X-Cart-Drawer") == "1"
    return templates.TemplateResponse(
        request=request, name="accessory_drawer.html" if drawer else "accessory_cart.html", status_code=status_code,
        headers={"Cache-Control": "private, no-store"},
        context={
            **summarize_cart(product_map, cart),
            "price": price, "error": error, "max_quantity": MAX_QUANTITY,
        },
    )


@router.get("/accesorios", name="accessories")
def accessories(request: Request, categoria: str = "", q: str = ""):
    product_map = products()
    query = q.strip().casefold()
    items = [
        product for product in grouped_products(product_map).values()
        if (not categoria or product["category"] == categoria)
        and query in f"{product['name']} {product['description']}".casefold()
    ]
    return templates.TemplateResponse(request=request, name="accessories.html", context={
        "items": items, "categories": CATEGORIES, "category": categoria, "query": q.strip(),
        "price": price, "cart_count": sum(cart_from_cookie(request, product_map).values()),
    })


@router.get("/accesorios/carrito", name="accessory_cart")
def accessory_cart(request: Request):
    product_map = products()
    return view_cart(request, product_map, cart_from_cookie(request, product_map))


def cart_invoice(request):
    product_map = products()
    summary = summarize_cart(product_map, cart_from_cookie(request, product_map))
    if not summary["lines"]:
        raise HTTPException(404, "Agrega un accesorio para generar la vista previa.")
    if summary["has_shortage"]:
        raise HTTPException(409, "Ajusta las cantidades a las existencias para generar el PDF.")
    return invoice_preview(summary)


@router.get("/accesorios/carrito/factura.pdf", name="accessory_invoice")
def accessory_invoice(request: Request):
    return Response(
        cart_invoice(request), media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="moto-garaje-factura-previa.pdf"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/accesorios/carrito/factura-previa.webp", name="accessory_invoice_image")
def accessory_invoice_image(request: Request):
    return Response(
        invoice_preview_image(cart_invoice(request)), media_type="image/webp",
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/accesorios/carrito", name="accessory_cart_change")
def accessory_cart_change(
    request: Request,
    sku: Annotated[str, Form(max_length=40)],
    quantity: Quantity,
    action: Annotated[str, Form(pattern="^(add|set)$")] = "set",
):
    product_map = products()
    cart = cart_from_cookie(request, product_map)
    product = product_map.get(sku)
    if product is None:
        return view_cart(request, product_map, cart, "Ese accesorio ya no está en el catálogo.", 404)
    if action == "add":
        quantity += cart.get(sku, 0)
    if quantity > min(product["stock"], MAX_QUANTITY):
        message = f"Hay {product['stock']} unidades disponibles de {product['name']}."
        return view_cart(request, product_map, cart, message, 409)
    if quantity:
        cart[sku] = quantity
    else:
        cart.pop(sku, None)

    if request.headers.get("X-Cart-Drawer") == "1":
        response = view_cart(request, product_map, cart)
    else:
        response = RedirectResponse(str(request.url_for("accessory_cart")), status_code=303)
    response.set_cookie(
        COOKIE, json.dumps(cart, separators=(",", ":")), max_age=60 * 60 * 24 * 7,
        httponly=True, secure=request.url.scheme == "https", samesite="lax",
        path="/accesorios",
    )
    return response


def checkout_page(request, zone, order_id, values=None, error=None, status_code=200):
    product_map = products()
    summary = summarize_cart(product_map, cart_from_cookie(request, product_map))
    _, shipping = SHIPPING[zone]
    return templates.TemplateResponse(
        request=request, name="accessory_checkout.html", status_code=status_code,
        headers={"Cache-Control": "private, no-store"}, context={
            **summary, "price": price, "zone": zone, "zones": SHIPPING, "shipping": shipping,
            "checkout_total": summary["total"] + shipping, "order_id": order_id,
            "values": values or {}, "error": error,
        },
    )


@router.get("/accesorios/checkout", name="accessory_checkout")
def accessory_checkout(request: Request, zona: str = "bogota"):
    return checkout_page(request, zona if zona in SHIPPING else "bogota", uuid4())


@router.post("/accesorios/checkout", name="accessory_checkout_submit")
def accessory_checkout_submit(
    request: Request,
    order_id: Annotated[UUID, Form()],
    expected_total: Annotated[int, Form(ge=0)],
    zone: Annotated[str, Form(max_length=20)],
    customer_name: Annotated[str, Form(max_length=100)],
    email: Annotated[str, Form(max_length=150)],
    phone: Annotated[str, Form(max_length=30)],
    address: Annotated[str, Form(max_length=200)],
    city: Annotated[str, Form(max_length=100)],
):
    check_origin(request)
    contact = {
        "customer_name": customer_name.strip(), "email": email.strip(), "phone": phone.strip(),
        "address": address.strip(), "city": city.strip(), "zone": zone,
    }
    if (
        zone not in SHIPPING or not all(contact.values())
        or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contact["email"])
        or not 7 <= sum(char.isdigit() for char in phone) <= 15
    ):
        return checkout_page(request, zone if zone in SHIPPING else "bogota", order_id, contact,
                             "Revisa los datos de contacto y entrega.", 422)
    if (zone == "bogota") != (city.strip().casefold() in {"bogotá", "bogota"}):
        return checkout_page(request, zone, order_id, contact, "La zona de envío debe coincidir con la ciudad.", 422)
    product_map = products()
    try:
        inventory.place_order(
            order_id, cart_from_cookie(request, product_map), contact, SHIPPING[zone][1], expected_total,
        )
    except inventory.OrderConflict as error:
        return checkout_page(request, zone, order_id, contact, str(error), 409)
    except SQLAlchemyError as error:
        raise HTTPException(503, "No se pudo confirmar el pedido. Vuelve a intentarlo.") from error
    response = RedirectResponse(str(request.url_for("accessory_receipt", order_id=order_id)), status_code=303)
    response.delete_cookie(COOKIE, path="/accesorios")
    return response


@router.get("/accesorios/pedido/{order_id}", name="accessory_receipt")
def accessory_receipt(request: Request, order_id: UUID):
    order = inventory.order_receipt(order_id)
    if order is None:
        raise HTTPException(404, "Pedido no encontrado.")
    return templates.TemplateResponse(
        request=request, name="accessory_receipt.html",
        headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"},
        context={"order": order, "reference": order_id.hex[:12].upper(), "price": price},
    )


@router.get("/accesorios/{sku}", name="accessory_detail")
def accessory_detail(request: Request, sku: str):
    product = grouped_products(products()).get(sku)
    if product is None:
        raise HTTPException(404, "Accesorio no encontrado.")
    return templates.TemplateResponse(request=request, name="accessory_detail.html", context={
        "item": product, "price": price, "categories": CATEGORIES, "compatible": COMPATIBILITY.get(sku),
    })


def stock_page(request, error=None, status_code=200):
    return templates.TemplateResponse(request=request, name="accessory_stock.html", status_code=status_code, context={
        "items": products().values(), "categories": CATEGORIES, "error": error,
        "updated": request.query_params.get("actualizado") == "1",
    })


@router.get("/gerencia/accesorios", name="accessory_stock")
def accessory_stock(request: Request):
    return stock_page(request)


@router.post("/gerencia/accesorios", name="accessory_stock_change")
def accessory_stock_change(
    request: Request,
    sku: Annotated[str, Form(max_length=40)],
    old_stock: Annotated[int, Form(ge=0, le=100000)],
    new_stock: Annotated[int, Form(ge=0, le=100000)],
):
    check_origin(request)
    try:
        updated = inventory.update_stock(sku, old_stock, new_stock)
    except (KeyError, SQLAlchemyError) as error:
        raise HTTPException(503, "No se pudo actualizar el inventario.") from error
    if updated is None:
        return stock_page(request, "El stock cambió. Revisa el valor actual e inténtalo de nuevo.", 409)
    url = request.url_for("accessory_stock").include_query_params(actualizado="1")
    return RedirectResponse(str(url), status_code=303)


def check_origin(request):
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "Origen del formulario inválido.")
