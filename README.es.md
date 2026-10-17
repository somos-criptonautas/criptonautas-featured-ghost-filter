# criptonautas-featured-ghost-filter

[ENGLISH](README.md) | **ESPAÑOL**

Mantenido por Criptonautas. Sin afiliación ni respaldo de la Ghost Foundation.

Convierte la imagen destacada de un post de Ghost al estilo de Criptonautas: paleta exacta de 5 colores, trama a 45°, líneas de tinta y grano de papel. Devuelve un PNG sin metadatos.

Es un servicio HTTP interno. Lo llama n8n; nunca queda expuesto a internet.

## Cómo encaja

1. Se publica un post con la etiqueta interna `#cover-filter` (fotos e ilustraciones) o `#graph-filter` (gráficos y capturas, que se envían con `mode=chart`).
2. El workflow de n8n `ghost-featured-image-send` descarga la imagen destacada, la manda a este servicio, sube el resultado a Ghost, cambia la imagen destacada y lo anota en la tabla `featured_image_variants`. `original_url` queda en la tabla para revertir.
3. La pasada manual sobre lo ya publicado corre en modo borrador: solo sube y anota, para revisar cada imagen antes de aplicarla.

Los rostros y el material de terceros no llevan ninguna de las dos etiquetas.

## Instalar

GitHub Actions prueba la imagen y la publica en `ghcr.io/somos-criptonautas/criptonautas-featured-ghost-filter` en cada push a `main`. En el servidor no se construye nada.

Pega el servicio del [`docker-compose.yml`](docker-compose.yml) de este repo bajo `services:` en el `docker-compose.yml` donde corre n8n. Si el servicio de n8n declara `networks:`, agrega las mismas redes a este servicio. Luego:

```bash
docker compose up -d criptonautas-featured-ghost-filter
docker compose ps criptonautas-featured-ghost-filter   # debe decir "healthy"
```

El build de la imagen descarga los pesos de Hugging Face (verificados por SHA-256) y los convierte a ONNX. La imagen publicada no lleva ni los pesos originales ni las herramientas de conversión.

En n8n el servicio es `http://criptonautas-featured-ghost-filter:8000`.

## Actualizar

Push a `main`, esperar que pase el workflow Build y en el servidor:

```bash
docker compose pull criptonautas-featured-ghost-filter
docker compose up -d criptonautas-featured-ghost-filter
```

## API

- `POST /filter?seed=<slug-del-post>` con la imagen como cuerpo → PNG.
  - Opcional `&accent=violet|red` y `&stroke=thin|thick` fuerzan la variante.
  - Cabecera `X-Variant`: la variante usada (`accent`, `stroke`, `cell`, `grain`).
  - Opcional `&mode=chart` para gráficos y capturas: solo la paleta, sin trama ni líneas de tinta; los fondos oscuros pasan a papel. `X-Variant` es entonces `{"mode": "chart"}`.
  - `Content-Disposition` lleva `<slug>.png`, para que Ghost acepte la subida.
  - Entrada de hasta 20 MB; salida de 1600 px de ancho como máximo.
  - Misma semilla, misma imagen: reprocesar un post no cambia su resultado.
- `GET /health` → `ok`.

## Ajustes de producción

El servicio corre en solo lectura, con usuario sin privilegios, sin capacidades de Linux, sin puertos publicados y con límites de 1 GB de memoria, 2 CPU y 64 procesos. El pico de memoria es de unos 0,7 GB con la entrada más grande, porque el modelo de líneas trabaja a 768 px y su mapa se amplía. Las imágenes se procesan de a una.

## Tests

```bash
pip install -r requirements.txt
python -m unittest discover tests                                  # rápidos, sin modelos
SERVICE_URL=http://127.0.0.1:8000 python tests/service_check.py    # contra un contenedor corriendo
```

`scripts/check_ghost_api.py` prueba la subida completa y el cambio de imagen destacada contra un Ghost de prueba. Nunca contra producción.

GitHub Actions corre los tests, construye la imagen, prueba el contenedor con los límites de producción y la publica solo si todo pasa.

## Créditos y licencia

Líneas: [Informative Drawings](https://github.com/carolineec/informative-drawings) de Caroline Chan, Frédo Durand y Phillip Isola (MIT). Pesos de [lllyasviel/Annotators](https://huggingface.co/lllyasviel/Annotators).

Código: [MIT](LICENSE). Texto de los README: CC BY-NC-SA 4.0.
