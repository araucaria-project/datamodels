"""JSON Schema export — the contract TypeScript clients generate their types from.

Run ``datamodels-export-schemas [out_dir]`` (default ``schemas/optics``). The committed files
are checked against a fresh export in the tests, so schema drift fails CI.
"""

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from enum import Enum

from pydantic import BaseModel

import datamodels.optics as optics
from datamodels.optics.results import Verdict

DEFAULT_OUT_DIR = Path("schemas") / "optics"


def _public_contracts() -> dict[str, Any]:
    """Every public model and enum of ``datamodels.optics`` (from its ``__all__``), plus the
    ``Verdict`` union — one schema file each, so the registry cannot drift from the package API.
    Identifier aliases (``ComponentName`` …) are not contracts of their own; they appear inline."""
    exported: dict[str, Any] = {}
    for name in optics.__all__:
        obj = getattr(optics, name)
        if isinstance(obj, type) and (issubclass(obj, BaseModel) or issubclass(obj, Enum)):
            exported[name] = obj
    exported["Verdict"] = Verdict
    return dict(sorted(exported.items()))


#: name -> type; one schema file per entry
EXPORTED: dict[str, Any] = _public_contracts()


def json_schemas() -> dict[str, dict[str, Any]]:
    """Every exported schema, keyed by name, with a stable ``$id``."""
    return {
        name: {"$id": f"https://araucaria-project.github.io/datamodels/optics/{name}.schema.json", **TypeAdapter(tp).json_schema()}
        for name, tp in EXPORTED.items()
    }


def render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def export_json_schemas(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, schema in json_schemas().items():
        path = out_dir / f"{name}.schema.json"
        path.write_text(render(schema), encoding="utf-8")
        written[name] = path
    return written


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    out_dir = Path(args[0]) if args else DEFAULT_OUT_DIR
    for name, path in export_json_schemas(out_dir).items():
        print(f"{name:24s} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
