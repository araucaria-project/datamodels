# datamodels
Data Models used on ocabox TACOSS software (OCM)

## Modules

- `datamodels.observation` — a single observation's data (files, measurements, quality checks)
- `datamodels.projects_overview` — a processing run's overview of projects/objects and their statuses
- `datamodels.optics` — Optical Path Model v4 vocabularies and schemas (authored grammar, `sees()` records,
  verdicts, compiled route table, conformance vectors). The pydantic models are the only source of truth;
  the JSON Schemas TypeScript clients generate their types from are a **build artifact**: not committed,
  produced by the release workflow under one pinned pydantic (`datamodels.optics.schema.GENERATOR_PYDANTIC`)
  and attached to the GitHub Release of the tag `v<version>` as `optics-schemas-v<version>.zip` (`$id` carries
  the version). Clients pin a release. To look at the output locally:

  ```bash
  uv run --with pydantic==$(uv run python -c 'from datamodels.optics.schema import GENERATOR_PYDANTIC as v; print(v)') datamodels-export-schemas
  ```

  Releasing = bumping `version` in `pyproject.toml` and pushing the matching `v<version>` tag.

## Development

```bash
uv sync
uv run pytest
```
