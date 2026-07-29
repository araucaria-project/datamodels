# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`datamodels` is a small Python package of Pydantic v2 data models describing astronomical
observation and project-tracking data for the ocabox TACOSS software (OCM, Araucaria Project).
It has no runtime logic beyond the models themselves — no CLI, no service, no I/O layer.
Consumers construct these models from JSON produced elsewhere in the TACOSS pipeline. There are
currently two independent model modules:

- `datamodels/observation.py` — a single observation's data (files, measurements, quality checks).
- `datamodels/projects_overview.py` — a processing run's overview of projects/objects and their
  statuses.

## Commands

The project uses `uv` (a `uv`-managed `.venv` is checked in as the active environment). Dev
dependencies (`pytest`) live in `[dependency-groups]` with `default-groups = ["dev"]` in
`pyproject.toml`, so a plain `uv sync` always installs them — no `--extra` flag needed.

```bash
uv sync                       # install/sync dependencies
uv run pytest                 # run the full test suite
uv run pytest tests/test_projects_overview.py::TestProjectsOverview::test_from_example_file  # single test
uv run pytest -k measurement  # run tests matching a keyword
python tests/test_observation.py  # each test file is also runnable directly (has a __main__ block)
```

There is no configured linter/formatter and no build/CI pipeline in this repo — don't invent
lint commands.

Packaging uses `hatchling` (PEP 621 metadata in `pyproject.toml`); there is no `[tool.poetry]`
section despite the tracked `poetry.lock`, so treat `uv` as the source of truth for the
environment. `uv.lock` is gitignored (local-only).

## Architecture

### `observation.py`

Re-exported from `datamodels/__init__.py`. The hierarchy mirrors the shape of a single
observation's data:

```
Observation
├── info: Info                       # required identity/timing metadata (obs_id, date_obs, jd_date_obs, oca_night)
├── quality_checks: dict[str, Any]
├── objects: dict[str, Any]
├── files: list[File]                # e.g. raw frame, calibration/master frames, per category
│     └── measurements: list[Measurement]   # per-file measurements (e.g. fwhm on a raw frame)
└── measurements: list[Measurement]  # observation-level measurements (e.g. wcs, photometry)
```

- **Lookup by `category`, not by index.** `File` and `Observation` are matched by a `category`
  string field rather than a fixed schema per kind (e.g. `"raw"`, `"master_z"`, `"wcs"`,
  `"fwhm"`). `Observation.get_measurement()` / `Observation.get_file()` and `File.get_measurement()`
  do linear scans over their respective lists to find a match by category. These accessor
  methods are declared `async def` (no actual async I/O inside) — match that signature/style if
  adding similar lookups.

### `projects_overview.py`

**Not yet re-exported from `datamodels/__init__.py`** — import directly from
`datamodels.projects_overview` for now. The hierarchy mirrors a processing run's report of
projects and their objects:

```
ProjectsOverview
├── processed_date / processed_folder / telescope
└── projects: dict[str, ProjectOverview]        # keyed by project id, e.g. "amcvn"
      ├── display_name / pi / sciprog / status
      └── objects: dict[str, ObjectOverview]     # keyed by object id, e.g. "asassn-14cc"
            ├── display_name / status (required)
            └── lc: dict[str, LightCurve]        # keyed by filter/passband, e.g. "u_s", "V"
                  └── display_name / status (optional)
```

Unlike `observation.py`, `projects`/`objects`/`lc` are looked up directly by dict key (they're
already keyed collections) — there are no `get_*` scan helpers here, and none are needed.

`Status` is a shared `str` enum: `ongoing`, `paused`, `halted`, `waiting`, `finished`. Per current
requirements, `ongoing` on a later report is meant to take precedence over other statuses seen for
the same object across repeated processing runs — that merge/precedence logic is **not yet
implemented**, deliberately deferred.

`ObjectOverview` has two fields commented out (`skymap`, `info`) — their shape isn't settled yet;
don't uncomment/implement them without checking with the user first.

### Shared conventions (both modules)

- **Every model sets `model_config = ConfigDict(extra="allow")`.** The upstream pipeline attaches
  arbitrary extra fields (varies by instrument/reduction step/project); models must keep accepting
  and round-tripping fields not explicitly declared. Don't switch this to `"forbid"` or `"ignore"`.
- **`Measurement.result` is `Any`.** Results can be a scalar, dict, or list depending on
  `category` — don't tighten this type without checking all call sites/tests.
- Models must support `model_dump()` / `model_dump_json()` and `model_validate()` /
  `model_validate_json()` round-tripping losslessly — `extra="allow"` fields must survive the
  round trip too.

## Tests and examples

Each model module has a matching test file (`tests/test_observation.py`,
`tests/test_projects_overview.py`), organized as one `Test<Model>` class per model covering basic
construction and `extra="allow"` behavior. Follow this per-model class structure when adding
tests for new models.

Realistic full payloads live under `examples/` (`observation_example.json`,
`projects_overview_example.json`), pretty-printed for readability. The top-level model's test
class loads its example via a module-level `EXAMPLE_PATH = Path(__file__).parent.parent /
"examples" / "..."` and validates/round-trips against it (`test_from_example_file`,
`test_serialization_roundtrip`, `test_json_roundtrip`) instead of hand-building nested objects
inline — reuse this pattern for new top-level models rather than constructing large fixtures by
hand in the test body.
