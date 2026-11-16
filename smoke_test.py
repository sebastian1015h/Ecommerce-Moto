import json
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

from sqlalchemy import text

from app.neon_services import database_engine, storage


def verify_services():
    with database_engine().begin() as connection:
        connection.execute(
            text("CREATE TEMP TABLE moto_garaje_smoke (value int) ON COMMIT DROP")
        )
        connection.execute(text("INSERT INTO moto_garaje_smoke VALUES (42)"))
        assert connection.execute(text("SELECT value FROM moto_garaje_smoke")).scalar_one() == 42
    print("PostgreSQL: escritura y lectura en tabla temporal OK")

    client, bucket = storage()
    key = f"_smoke/moto-garaje-{uuid4().hex}.txt"
    payload = b"Moto Garaje Neon smoke test"
    client.put_object(Bucket=bucket, Key=key, Body=payload, ContentType="text/plain")
    try:
        body = client.get_object(Bucket=bucket, Key=key)["Body"]
        try:
            assert body.read() == payload
        finally:
            body.close()
    finally:
        client.delete_object(Bucket=bucket, Key=key)
    print("Object Storage: subida, lectura y limpieza OK")


def verify_store(base):
    pages = {
        "/health/live": '"status":"ok"',
        "/motos": "6 modelos",
        "/motos?categoria=scooters&marca=Honda": "PCX 160",
        "/motos?q=gixxer": "1 modelo",
        "/motos?q=sin-resultados": "No encontramos motos",
        "/motos/ktm-390-duke": "Ficha de demostración",
    }
    for path, expected in pages.items():
        with urlopen(f"{base}{path}", timeout=5) as response:
            assert expected in response.read().decode("utf-8"), path
    for image in ("duke-hero", "urbanas", "scooters", "deportivas", "aventura"):
        with urlopen(f"{base}/static/images/{image}.webp", timeout=5) as response:
            assert response.headers.get_content_type() == "image/webp"
    print("Tienda: portada, catálogo, filtros, fichas e imágenes OK")


def main():
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8637"]
    )
    base = "http://127.0.0.1:8637"
    try:
        for _ in range(40):
            if server.poll() is not None:
                raise RuntimeError("FastAPI terminó durante el arranque")
            try:
                with urlopen(base, timeout=1) as response:
                    assert "próxima moto" in response.read().decode("utf-8")
                break
            except URLError:
                time.sleep(0.25)
        else:
            raise RuntimeError("FastAPI no respondió durante el arranque")

        verify_store(base)
        with urlopen(f"{base}/health/ready", timeout=25) as response:
            services = json.load(response)
            assert services == {"postgres": "ok", "object_storage": "ok"}
            print(f"GET /health/ready -> {response.status} {services}")
        verify_services()
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    main()
