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

En `/laboratorio`, GET consulta las motos guardadas en Neon. POST, PATCH y DELETE ejecutan SQL sobre una tabla temporal que se elimina al cerrar la transacción. Swagger UI está en `/docs`.

## Inventario de Gerencia

Con `DATABASE_URL_UNPOOLED` disponible, aplica la migración una vez por base de datos:

```powershell
.\.venv\Scripts\python.exe -m app.catalog.inventory
```

En `/gerencia` puedes registrar motos y fotos. PostgreSQL guarda el modelo y Neon Object Storage almacena la foto optimizada en WebP. El visor de la KTM usa cinco ángulos oficiales. Las otras fichas enlazan a visores externos cuando están disponibles. Gerencia se abre sin contraseña, por lo que cualquier visitante con acceso a la instancia puede subir modelos.

Después de preparar `inventory_motos`, ejecuta `.\.venv\Scripts\python.exe -m app.catalog.sales` para crear las ofertas por color y los pedidos de motos. Los precios y el stock inicial son de demostración. En `/gerencia/inventario-motos` puedes ajustarlos. La ficha incluye especificaciones por modelo y muestra un enlace de compra cuando el acabado tiene precio y existencias. Confirmar aparta una unidad y registra un pedido pendiente de pago.

## Subtienda de accesorios

Con la conexión directa de Neon disponible, carga los 20 accesorios de demostración:

```powershell
.\.venv\Scripts\python.exe -m app.accessories.inventory
```

Al repetir la carga se conservan los precios y las existencias que ya están en la base. La primera migración de variantes distribuye el stock existente entre las tallas de demostración de cada accesorio. Puedes ajustarlo en `/gerencia/accesorios`.

Explora la tienda en `/accesorios`. El carrito lateral permite cambiar cantidades y el carrito completo muestra la vista previa de factura. El checkout de `/accesorios/checkout` calcula el envío con tarifas de demostración, comprueba nuevamente el stock y registra un pedido pendiente de pago. Confirmar un pedido reduce las existencias en una transacción. Gerencia conserva su acceso abierto y esta versión no cobra pagos.

## Despliegue en Render

Conecta el repositorio `sebastian1015h/Ecommerce-Moto` a un Blueprint de Render. `render.yaml` usa el plan Free para la demo y configura la instalación, el inicio de Uvicorn y la verificación del proceso. Puedes consultar `/health/ready` para comprobar PostgreSQL y Object Storage. Completa en Render las variables solicitadas con los valores locales de Neon. Puedes usar `NEON_STORAGE_BUCKET` para indicar un bucket distinto de `comercio`.
