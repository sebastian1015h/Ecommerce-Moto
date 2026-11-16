import json
import os
from io import BytesIO
from uuid import uuid4

from PIL import Image, ImageOps
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.catalog import sales
from app.neon_services import database_engine, storage

INVENTORY_QUERY = """SELECT slug, marca, modelo, categoria, color
FROM inventory_motos
WHERE strpos(lower(marca || ' ' || modelo), lower(:query)) > 0
ORDER BY created_at DESC
LIMIT 500"""

EXAMPLE_QUERIES = {
    "insert": "INSERT INTO inventory_example VALUES (1, :value)\nRETURNING modelo",
    "update": "UPDATE inventory_example SET modelo = :value\nWHERE id = 1 RETURNING modelo",
    "delete": "DELETE FROM inventory_example\nWHERE id = 1 RETURNING modelo",
}


def migrate():
    url = make_url(os.environ["DATABASE_URL_UNPOOLED"]).set(drivername="postgresql+psycopg")
    engine = create_engine(url, connect_args={"connect_timeout": 8})
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS inventory_motos (
                slug text PRIMARY KEY,
                marca text NOT NULL,
                modelo text NOT NULL,
                categoria text NOT NULL,
                color text NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now()
            )
        """))
        connection.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS inventory_motos_brand_model
            ON inventory_motos (marca, lower(modelo))
        """))
    engine.dispose()


def describe_target(connection, relation, target):
    row = connection.execute(text("""
        SELECT current_database() AS database, ns.nspname AS schema, cls.relname AS relation
        FROM pg_catalog.pg_class AS cls
        JOIN pg_catalog.pg_namespace AS ns ON ns.oid = cls.relnamespace
        WHERE cls.oid = to_regclass(:relation)
    """), {"relation": relation}).mappings().one()
    target.update(row)
    if branch := os.getenv("NEON_BRANCH"):
        target["branch"] = branch


def list_inventory(query="", *, target=None):
    if not os.getenv("DATABASE_URL"):
        return []
    with database_engine().connect() as connection:
        rows = [
            dict(row) for row in connection.execute(text(INVENTORY_QUERY), {"query": query}).mappings()
        ]
        if target is not None:
            describe_target(connection, "inventory_motos", target)
        return rows


def lookup_moto(slug):
    if not os.getenv("DATABASE_URL"):
        return None
    with database_engine().connect() as connection:
        row = connection.execute(text("""
            SELECT slug, marca, modelo, categoria, color, specs FROM inventory_motos WHERE slug = :slug
        """), {"slug": slug}).mappings().first()
        return dict(row) if row else None


def prepare_image(raw):
    with Image.open(BytesIO(raw), formats=["JPEG", "PNG", "WEBP"]) as image:
        if image.width * image.height > 20_000_000 or getattr(image, "is_animated", False):
            raise ValueError("Usa una imagen fija de hasta 20 megapíxeles.")
        image = ImageOps.exif_transpose(image).convert("RGBA")
        image.thumbnail((1400, 1050), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="WEBP", quality=88)
        return output.getvalue()


def create_moto(brand, model, category, color, image, *, price_cop=None, stock=0, specs=None):
    slug = "modelo-" + uuid4().hex
    client, bucket = storage()
    with database_engine().begin() as connection:
        connection.execute(text("""
            INSERT INTO inventory_motos (slug, marca, modelo, categoria, color, specs)
            VALUES (:slug, :brand, :model, :category, :color, CAST(:specs AS jsonb))
        """), dict(slug=slug, brand=brand, model=model, category=category, color=color,
                   specs=json.dumps(specs or {})))
        sales.insert_offer(connection, slug, color, price_cop, stock)
        client.put_object(
            Bucket=bucket, Key=f"catalogo/{slug}.webp", Body=image, ContentType="image/webp",
            CacheControl="public, max-age=31536000, immutable",
        )
    return slug


def inventory_example(operation, value="", *, target=None):
    with database_engine().begin() as connection:
        connection.execute(text("CREATE TEMP TABLE inventory_example (id int, modelo text) ON COMMIT DROP"))
        if operation != "insert":
            connection.execute(text("INSERT INTO inventory_example VALUES (1, 'Moto de ejemplo')"))
        result = connection.execute(text(EXAMPLE_QUERIES[operation]), {"value": value}).scalar_one()
        if target is not None:
            describe_target(connection, "pg_temp.inventory_example", target)
        return result


if __name__ == "__main__":
    migrate()
