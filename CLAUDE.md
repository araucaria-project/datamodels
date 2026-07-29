# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`datamodels` is a small Python package of Pydantic v2 data models describing astronomical
observation data for the ocabox TACOSS software (OCM, Araucaria Project). It has no runtime
logic beyond the models themselves — no CLI, no service, no I/O layer. Consumers construct
these models from JSON produced elsewhere in the TACOSS pipeline.

## Commands

The project uses `uv` (a `uv`-managed `.venv` is checked in as the active environment).

```bash
uv sync                       # install/sync dependencies (incl. dev extras)
uv run pytest                 # run the full test suite
uv run pytest tests/test_observation.py::TestObservation::test_full_observation  # single test
uv run pytest -k measurement  # run tests matching a keyword
```

There is no configured linter/formatter and no build/CI pipeline in this repo — don't invent
lint commands.

Packaging uses `hatchling` (PEP 621 metadata in `pyproject.toml`); there is no `[tool.poetry]`
section despite the tracked `poetry.lock`, so treat `uv` as the source of truth for the
environment. `uv.lock` is gitignored (local-only).

## Architecture

All models live in `datamodels/observation.py` and are re-exported from `datamodels/__init__.py`.
The hierarchy mirrors the shape of a single observation's data:

```
Observation
├── info: Info                       # required identity/timing metadata (obs_id, date_obs, jd_date_obs, oca_night)
├── quality_checks: dict[str, Any]
├── objects: dict[str, Any]
├── files: list[File]                # e.g. raw frame, calibration/master frames, per category
│     └── measurements: list[Measurement]   # per-file measurements (e.g. fwhm on a raw frame)
└── measurements: list[Measurement]  # observation-level measurements (e.g. wcs, photometry)
```

Key design points to preserve when editing these models:

- **Every model sets `model_config = ConfigDict(extra="allow")`.** The upstream pipeline attaches
  arbitrary extra fields (varies by instrument/reduction step); models must keep accepting and
  round-tripping fields not explicitly declared. Don't switch this to `"forbid"` or `"ignore"`.
- **`Measurement.result` is `Any`.** Results can be a scalar, dict, or list depending on
  `category` — don't tighten this type without checking all call sites/tests.
- **Lookup by `category`, not by index.** `File` and `Observation` are matched by a `category`
  string field rather than a fixed schema per kind (e.g. `"raw"`, `"master_z"`, `"wcs"`,
  `"fwhm"`). `Observation.get_measurement()` / `Observation.get_file()` and `File.get_measurement()`
  do linear scans over their respective lists to find a match by category. These accessor
  methods are declared `async def` (no actual async I/O inside) — match that signature/style if
  adding similar lookups.
- Models must support `model_dump()` / `model_dump_json()` and `model_validate()` /
  `model_validate_json()` round-tripping losslessly (see `test_serialization_roundtrip` /
  `test_json_roundtrip` in `tests/test_observation.py`) — keep this in mind since `extra="allow"`
  fields must survive the round trip too.

## Tests

`tests/test_observation.py` is the only test module and is organized as one `Test<Model>` class
per model, covering: basic construction, `extra="allow"` behavior, and (for `Observation`)
serialization round-trips. Follow this per-model class structure when adding tests for new models.
