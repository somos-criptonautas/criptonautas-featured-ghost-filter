# AGENTS.md

## Checks

```bash
pip install -r requirements.txt
python -m unittest discover tests
```

Full check needs Docker: build the image, run it, then `SERVICE_URL=http://127.0.0.1:8000 python tests/service_check.py`. The Build workflow does both and publishes the image to GHCR on `main`; servers only pull it.

## Review rules

- Output must use only the 5 palette colors in `brand_filter.py` and carry no metadata.
- Same seed must give byte-identical output. Changing the variant logic changes every published image: say so in the PR.
- Peak memory must stay under the 1 GB container limit with a 1600 px wide input.
- Everything in English: names, endpoints, headers, comments, messages. Descriptive names, no abbreviations nobody would guess.
- Comments explain why, in one plain line. No history, no tool tags.
- Docker file is `docker-compose.yml`, and it holds a service block meant to be pasted into the n8n `docker-compose.yml`. It uses the published image, never `build:`.
- Commits use Discourse prefixes: `FEATURE:`, `FIX:`, `DEV:`, `DOCS:`.
