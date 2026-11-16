# Moto Garaje

Tienda de motos con FastAPI y Jinja2. Incluye portada, catálogo con filtros, fichas estilo warehouse y un laboratorio de API. Las fichas enlazan a la fuente de las fotos y acabados de referencia. Las tarjetas de categorías usan imágenes conceptuales.

## Ejecutar en Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Abre http://127.0.0.1:8000. La portada y el catálogo de demostración funcionan sin credenciales. Para verificar Neon, configura las variables en `.env.local` o en el entorno y ejecuta:

```powershell
npm run build
.\.venv\Scripts\python.exe smoke_test.py
```

En `/laboratorio` puedes consultar el catálogo y probar escrituras simuladas. Los endpoints de muestra responden a POST, PATCH y DELETE sin guardar datos. Swagger UI está en `/docs`.

## Despliegue en Render

Conecta el repositorio `sebastian1015h/Ecommerce-Moto` a un Blueprint de Render. `render.yaml` usa el plan Free para la demo y configura la instalación, el inicio de Uvicorn y la verificación del proceso. Puedes consultar `/health/ready` para comprobar PostgreSQL y Object Storage. Completa en Render las variables solicitadas con los valores locales de Neon. Puedes usar `NEON_STORAGE_BUCKET` para indicar un bucket distinto de `comercio`.
