"""Optical Path Model (v4) — vocabularies and schemas. No solver logic lives here.

Spec: knowledge-base ``Architecture/Optical Path Model.md``;
epic: araucaria-project/ocabox-server#27; this module: araucaria-project/datamodels#10.
"""

from datamodels.optics.compiled import Conflict, OpticsCompiled, Route, RouteKey, TelescopeCompiled
from datamodels.optics.conformance import ConformanceSuite, ConformanceVector, Environment, SelectorState
from datamodels.optics.graph import (
    DetectorPaths,
    DisplayHint,
    EdgeRef,
    GoalAlternative,
    GoalExpr,
    GoalSpec,
    OpticalComponentSpec,
    OpticsEdges,
    PositionSpec,
    PositionsSpec,
    TelescopeOpticsSpec,
)
from datamodels.optics.results import (
    Active,
    CheckResult,
    Collision,
    ConfigError,
    Impossible,
    Invalid,
    SeesRecord,
    Settable,
    Verdict,
)
from datamodels.optics.vocabulary import (
    DARK,
    RESERVED_WORDS,
    UNDEFINED,
    Archetype,
    ComponentName,
    CoreFunction,
    FunctionName,
    LightClass,
    PortOwner,
    SkyState,
    SourceFamily,
    Symbol,
    VerdictKind,
    light_family,
    light_state,
)

__all__ = [
    # vocabulary
    "DARK", "UNDEFINED", "RESERVED_WORDS",
    "Archetype", "SourceFamily", "SkyState", "CoreFunction", "VerdictKind", "PortOwner",
    "ComponentName", "Symbol", "LightClass", "FunctionName", "light_family", "light_state",
    # authored grammar
    "PositionSpec", "PositionsSpec", "EdgeRef", "OpticsEdges", "GoalSpec", "GoalAlternative", "GoalExpr",
    "DetectorPaths", "DisplayHint", "OpticalComponentSpec", "TelescopeOpticsSpec",
    # results
    "SeesRecord", "ConfigError", "Active", "Settable", "Collision", "Impossible", "Invalid", "Verdict", "CheckResult",
    # compiled
    "Route", "RouteKey", "Conflict", "TelescopeCompiled", "OpticsCompiled",
    # conformance
    "SelectorState", "Environment", "ConformanceVector", "ConformanceSuite",
]
