# criptonautas-featured-ghost-filter

**ENGLISH** | [ESPAÑOL](README.es.md)

Maintained by Criptonautas. Not affiliated with or endorsed by the Ghost Foundation.

Turns the featured image of a Ghost post into the Criptonautas look: exact 5-color palette, 45° halftone, ink lines and paper grain. Output is a PNG with no metadata.

It is a small internal HTTP service. n8n calls it; it is never exposed to the internet.

## How it fits

1. A post is published with the internal tag `#cover-filter` (photos and illustrations) or `#graph-filter` (charts and screenshots, sent with `mode=chart`).
2. The n8n workflow `ghost-featured-image-send` downloads its featured image, sends it to this service, uploads the result to Ghost, swaps the featured image and logs it in the `featured_image_variants` data table. `original_url` stays in the table to revert.
3. A manual backfill over already published posts runs in draft mode: it only uploads and logs, so each image is reviewed before it is applied.

Faces and third-party material never get either tag.

## Install

GitHub Actions tests the image and publishes it to `ghcr.io/somos-criptonautas/criptonautas-featured-ghost-filter` on every push to `main`. Nothing is built on the server.

Paste the service from this repo's [`docker-compose.yml`](docker-compose.yml) under `services:` in the `docker-compose.yml` that runs n8n. If the n8n service lists `networks:`, add the same networks to this service. Then:

```bash
docker compose up -d criptonautas-featured-ghost-filter
docker compose ps criptonautas-featured-ghost-filter   # should say "healthy"
```

The image build downloads the line-art weights from Hugging Face (pinned by SHA-256) and converts them to ONNX. The published image holds neither the original weights nor the conversion tools.

In n8n the service is `http://criptonautas-featured-ghost-filter:8000`.

## Update

Push to `main`, wait for the Build workflow to pass, then on the server:

```bash
docker compose pull criptonautas-featured-ghost-filter
docker compose up -d criptonautas-featured-ghost-filter
```

## API

- `POST /filter?seed=<post-slug>` with the image as the body → PNG.
  - Optional `&accent=violet|red` and `&stroke=thin|thick` force the variant.
  - `X-Variant` header: the variant used (`accent`, `stroke`, `cell`, `grain`).
  - Optional `&mode=chart` for charts and screenshots: palette only, no halftone or ink lines, dark backgrounds turn to paper. `X-Variant` is then `{"mode": "chart"}`.
  - `Content-Disposition` carries `<slug>.png`, so Ghost accepts the upload.
  - Input up to 20 MB; output at most 1600 px wide.
  - Same seed, same image: reprocessing a post never changes its result.
- `GET /health` → `ok`.

## Production settings

The service block runs read-only, as an unprivileged user, with no Linux capabilities, no published ports, and limits of 1 GB memory, 2 CPUs and 64 processes. Peak memory is about 0.7 GB at the largest input, because the line model runs at 768 px and its map is upscaled. Images are processed one at a time.

## Tests

```bash
pip install -r requirements.txt
python -m unittest discover tests                                  # fast, no models needed
SERVICE_URL=http://127.0.0.1:8000 python tests/service_check.py    # against a running container
```

`scripts/check_ghost_api.py` runs the full upload and featured-image swap against a test Ghost. Never point it at production.

GitHub Actions runs the unit tests, builds the image, checks the running container with the production limits, and publishes it only if everything passes.

## Credits and license

Line art: [Informative Drawings](https://github.com/carolineec/informative-drawings) by Caroline Chan, Frédo Durand and Phillip Isola (MIT). Weights from [lllyasviel/Annotators](https://huggingface.co/lllyasviel/Annotators).

Code: [MIT](LICENSE). README text: [CC BY-NC-SA 4.0](CC-BY-NC-SA-4.0.txt).
