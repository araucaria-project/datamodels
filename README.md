# datamodels
Data Models used on ocabox TACOSS software (OCM)

## Modules

- `datamodels.observation` — a single observation's data (files, measurements, quality checks)
- `datamodels.projects_overview` — a processing run's overview of projects/objects and their statuses
- `datamodels.optics` — Optical Path Model v4 vocabularies and schemas (authored grammar, `sees()` records,
  verdicts, compiled route table, conformance vectors). JSON Schemas for TypeScript clients are committed
  under `schemas/optics/`. They are generated under one pinned pydantic (`datamodels.optics.schema.GENERATOR_PYDANTIC`,
  recorded in every file's `$comment`) while the library itself stays on `pydantic>=2`; regenerate with

  ```bash
  uv run --with pydantic==$(uv run python -c 'from datamodels.optics.schema import GENERATOR_PYDANTIC as v; print(v)') datamodels-export-schemas
  ```

  The exporter refuses any other pydantic version. Bumping the pin is a deliberate commit with the regenerated schemas.

## Development

```bash
uv sync
uv run pytest
```
