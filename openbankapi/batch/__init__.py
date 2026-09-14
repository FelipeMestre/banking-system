"""The batch worker package (Credit Cards Phase 4) — this repo's first
non-HTTP, non-Kafka entry point.

Placed at `openbankapi/batch/` (not a top-level sibling package) so the
existing Docker build — `docker-compose.yml`'s `openbankapi`/`db-migrate`
services already set `build.context: ./openbankapi`, and the Dockerfile's
`COPY . /app/openbankapi` only ever copies files inside that context — picks
this package up for free, with zero changes to how the image is built.
A genuinely top-level `batch/` package (sibling to `openbankapi/` at the repo
root) would sit outside that build context and never reach the image.
"""
