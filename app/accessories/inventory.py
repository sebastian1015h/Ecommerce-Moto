import json
import os

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import make_url

from app.accessories.pricing import summarize_cart
from app.accessories.products import PRODUCTS, SIZES
from app.neon_services import database_engine


def migrate():
    url = make_url(os.environ["DATABASE_URL_UNPOOLED"]).set(drivername="postgresql+psycopg")
    engine = create_engine(url, connect_args={"connect_timeout": 8})
    try:
        with engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS accessory_inventory (
                    sku text PRIMARY KEY,
                    name text NOT NULL,
                    category text NOT NULL,
                    description text NOT NULL,
                    price_cop integer NOT NULL CHECK (price_cop >= 0),
                    stock integer NOT NULL CHECK (stock >= 0)
                )
            """))
            connection.execute(text("""
                INSERT INTO accessory_inventory (sku, name, category, description, price_cop, stock)
                VALUES (:sku, :name, :category, :description, :price_cop, :stock)
                ON CONFLICT (sku) DO NOTHING
            """), [
                dict(zip(("sku", "name", "category", "description", "price_cop", "stock"), product))
                for product in PRODUCTS
            ])
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS accessory_variants (
                    id text PRIMARY KEY,
                    sku text NOT NULL REFERENCES accessory_inventory(sku),
                    label text NOT NULL,
                    stock integer NOT NULL CHECK (stock >= 0),
                    position integer NOT NULL
                )
            """))
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS accessory_orders (
                    id uuid PRIMARY KEY,
                    customer_name text NOT NULL,
                    email text NOT NULL,
                    phone text NOT NULL,
                    address text NOT NULL,
                    city text NOT NULL,
                    zone text NOT NULL,
                    items jsonb NOT NULL,
                    subtotal integer NOT NULL,
                    iva integer NOT NULL,
                    shipping integer NOT NULL,
                    total integer NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT now()
                )
            """))
            for row in connection.execute(text("""
                SELECT sku, stock FROM accessory_inventory p
                WHERE NOT EXISTS (SELECT 1 FROM accessory_variants v WHERE v.sku = p.sku)
            """)).mappings().all():
                sizes = SIZES.get(row["sku"], ("Única",))
                base, extra = divmod(row["stock"], len(sizes))
                for position, label in enumerate(sizes):
                    key = row["sku"] if len(sizes) == 1 else f"{row['sku']}:{label.lower()}"
                    connection.execute(text("""
                        INSERT INTO accessory_variants (id, sku, label, stock, position)
                        VALUES (:id, :sku, :label, :stock, :position)
                        ON CONFLICT (id) DO NOTHING
                    """), dict(id=key, sku=row["sku"], label=label, stock=base + (position < extra), position=position))
    finally:
        engine.dispose()


def list_products():
    with database_engine().connect() as connection:
        return connection.execute(text("""
            SELECT p.sku, p.name, p.category, p.description, p.price_cop,
                v.id AS variant_id, v.label AS variant, v.stock
            FROM accessory_inventory p JOIN accessory_variants v ON v.sku = p.sku
            ORDER BY p.name, p.sku, v.position
        """)).mappings().all()


def update_stock(sku, old_stock, new_stock):
    with database_engine().begin() as connection:
        return connection.execute(text("""
            UPDATE accessory_variants SET stock = :new_stock
            WHERE id = :sku AND stock = :old_stock RETURNING id
        """), dict(sku=sku, old_stock=old_stock, new_stock=new_stock)).scalar_one_or_none()


class OrderConflict(Exception):
    pass


def order_receipt(order_id):
    with database_engine().connect() as connection:
        return connection.execute(text("""
            SELECT id, items, subtotal, iva, shipping, total FROM accessory_orders WHERE id = :id
        """), {"id": order_id}).mappings().first()


def place_order(order_id, cart, customer, shipping, expected_total):
    with database_engine().begin() as connection:
        # Serialize retries for this order before touching any inventory rows.
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": str(order_id)})
        if connection.execute(text("SELECT 1 FROM accessory_orders WHERE id = :id"), {"id": order_id}).scalar():
            return
        if not cart:
            raise OrderConflict("Tu carrito está vacío.")
        rows = connection.execute(text("""
            SELECT v.id, v.label AS variant, v.stock, p.sku, p.name, p.price_cop
            FROM accessory_variants v JOIN accessory_inventory p ON p.sku = v.sku
            WHERE v.id IN :ids ORDER BY v.id FOR UPDATE OF p, v
        """).bindparams(bindparam("ids", expanding=True)), {"ids": tuple(cart)}).mappings().all()
        summary = summarize_cart({row["id"]: row for row in rows}, cart)
        if len(rows) != len(cart) or summary["has_shortage"]:
            raise OrderConflict("Las existencias cambiaron. Revisa las cantidades antes de confirmar.")
        total = summary["total"] + shipping
        if total != expected_total:
            raise OrderConflict("El total cambió. Revisa el nuevo importe antes de confirmar.")
        items = [
            dict(name=line["product"]["name"], variant=line["product"]["variant"],
                 quantity=line["qty"], unit_price=line["product"]["price_cop"])
            for line in summary["lines"]
        ]
        connection.execute(text("""
            INSERT INTO accessory_orders
                (id, customer_name, email, phone, address, city, zone, items, subtotal, iva, shipping, total)
            VALUES (:id, :customer_name, :email, :phone, :address, :city, :zone,
                    CAST(:items AS jsonb), :subtotal, :iva, :shipping, :total)
        """), dict(id=order_id, items=json.dumps(items), subtotal=summary["subtotal"],
                   iva=summary["iva"], shipping=shipping, total=total, **customer))
        connection.execute(text("""
            UPDATE accessory_variants SET stock = stock - :quantity WHERE id = :id
        """), [dict(id=key, quantity=quantity) for key, quantity in cart.items()])


if __name__ == "__main__":
    migrate()
