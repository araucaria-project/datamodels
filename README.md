# datamodels
Data Models used on ocabox TACOSS software (OCM)

## Modules

- `datamodels.observation` — a single observation's data (files, measurements, quality checks)
- `datamodels.projects_overview` — a processing run's overview of projects/objects and their statuses
- `datamodels.optics` — Optical Path Model v4 vocabularies and schemas (authored grammar, `sees()` records,
  verdicts, compiled route table, conformance vectors). JSON Schemas for TypeScript clients are committed
  under `schemas/optics/` and regenerated with `uv run datamodels-export-schemas`.

## Development

```bash
uv sync
uv run pytest
```
