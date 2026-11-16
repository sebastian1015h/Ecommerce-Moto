import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.catalog.finishes import FINISHES
from app.neon_services import database_engine

# Demonstration prices and initial availability, indexed by showroom model.
DEMO_OFFERS = {
    "ktm-390-duke": (29990000, (3, 1)),
    "suzuki-gixxer-250": (14990000, (4, 2)),
    "honda-pcx-160": (16990000, (2, 3)),
    "yamaha-nmax": (16800000, (4, 2, 0)),
    "kawasaki-ninja-zx-4rr": (48990000, (2,)),
    "suzuki-v-strom-250-sx": (20990000, (3, 2)),
}


def migrate():
    url = make_url(os.environ["DATABASE_URL_UNPOOLED"]).set(drivername="postgresql+psycopg")
    engine = create_engine(url, connect_args={"connect_timeout": 8})
    try:
        with engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS moto_offers (
                    slug text NOT NULL, color text NOT NULL,
                    price_cop integer CHECK (price_cop > 0),
                    stock integer NOT NULL CHECK (stock >= 0),
                    PRIMARY KEY (slug, color)
                )
            """))
            connection.execute(text("""
                ALTER TABLE inventory_motos
                ADD COLUMN IF NOT EXISTS specs jsonb NOT NULL DEFAULT '{}'::jsonb
            """))
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS moto_orders (
                    id uuid PRIMARY KEY, slug text NOT NULL, color text NOT NULL,
                    brand text NOT NULL, model text NOT NULL,
                    price_cop integer NOT NULL CHECK (price_cop > 0),
                    customer_name text NOT NULL, email text NOT NULL, phone text NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    FOREIGN KEY (slug, color) REFERENCES moto_offers(slug, color)
                )
            """))
            for slug, (price_cop, stock_by_color) in DEMO_OFFERS.items():
                for (color, _, _), stock in zip(FINISHES[slug][1], stock_by_color, strict=True):
                    insert_offer(connection, slug, color, price_cop, stock)
            connection.execute(text("""
                INSERT INTO moto_offers (slug, color, price_cop, stock)
                SELECT slug, color, NULL, 0 FROM inventory_motos
                ON CONFLICT (slug, color) DO NOTHING
            """))
    finally:
        engine.dispose()


def insert_offer(connection, slug, color, price_cop, stock):
    connection.execute(text("""
        INSERT INTO moto_offers (slug, color, price_cop, stock)
        VALUES (:slug, :color, :price_cop, :stock)
        ON CONFLICT (slug, color) DO NOTHING
    """), dict(slug=slug, color=color, price_cop=price_cop, stock=stock))


def offers(slug=None):
    if not os.getenv("DATABASE_URL"):
        return []
    with database_engine().connect() as connection:
        return connection.execute(text("""
            SELECT slug, color, price_cop, stock FROM moto_offers
            WHERE (CAST(:slug AS text) IS NULL OR slug = :slug) ORDER BY slug, color
        """), {"slug": slug}).mappings().all()


def change_offer(slug, color, price_cop, stock, previous_price, previous_stock):
    with database_engine().begin() as connection:
        return connection.execute(text("""
            UPDATE moto_offers SET price_cop = :price_cop, stock = :stock
            WHERE slug = :slug AND color = :color AND stock = :previous_stock
              AND price_cop IS NOT DISTINCT FROM CAST(:previous_price AS integer)
            RETURNING slug
        """), dict(slug=slug, color=color, price_cop=price_cop, stock=stock,
                   previous_price=previous_price, previous_stock=previous_stock)).scalar_one_or_none()


class MotoOrderConflict(Exception):
    pass


def place_order(order_id, slug, color, brand, model, expected_price, contact):
    with database_engine().begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                           {"key": "moto:" + str(order_id)})
        if connection.execute(text("SELECT 1 FROM moto_orders WHERE id = :id"), {"id": order_id}).scalar():
            return
        offer = connection.execute(text("""
            SELECT price_cop, stock FROM moto_offers
            WHERE slug = :slug AND color = :color FOR UPDATE
        """), dict(slug=slug, color=color)).mappings().first()
        if not offer or offer["price_cop"] is None or offer["stock"] < 1:
            raise MotoOrderConflict("Este acabado ya no está disponible para compra.")
        if offer["price_cop"] != expected_price:
            raise MotoOrderConflict("El precio cambió. Revisa el importe antes de confirmar.")
        connection.execute(text("""
            INSERT INTO moto_orders (id, slug, color, brand, model, price_cop, customer_name, email, phone)
            VALUES (:id, :slug, :color, :brand, :model, :price_cop, :customer_name, :email, :phone)
        """), dict(id=order_id, slug=slug, color=color, brand=brand, model=model,
                   price_cop=offer["price_cop"], **contact))
        connection.execute(text("""
            UPDATE moto_offers SET stock = stock - 1 WHERE slug = :slug AND color = :color
        """), dict(slug=slug, color=color))


def order_receipt(order_id):
    with database_engine().connect() as connection:
        return connection.execute(text("""
            SELECT slug, color, brand, model, price_cop FROM moto_orders WHERE id = :id
        """), {"id": order_id}).mappings().first()


if __name__ == "__main__":
    migrate()
