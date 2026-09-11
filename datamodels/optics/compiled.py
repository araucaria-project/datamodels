"""The compiled artifact (W3): route table + conflict map, *generated from the graph and then
verified against it* in the config repo's CI, committed lockfile-style next to the authored
``optics:`` sections and published verbatim by TIC. Simple clients look routes up here; rich
clients still traverse the graph. The compiled artifact never contains runtime state.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from datamodels.optics.vocabulary import CLOSED_STATE_KEYS, ComponentName, FunctionName, GoalClass, StateKey, Symbol

SCHEMA_VERSION = 1


class Route(BaseModel):
    """One alternative of one detector function, fully resolved to selector positions."""

    model_config = ConfigDict(extra="forbid")

    detector: ComponentName
    function: FunctionName
    alternative: int = Field(ge=0)  #: index into the authored alternatives list (0 for a bare goal)
    realization: int = Field(default=0, ge=0)  #: ordinal among the physical routes realising that alternative (a bare `dark` has several)
    see: GoalClass  #: the authored goal this route realises — never ``undefined``
    positions: dict[StateKey, Symbol] = Field(json_schema_extra=CLOSED_STATE_KEYS)  #: every selector (and emitting aspect) on the path and the position it must hold for a *clean* view
    when: GoalClass | None = None


class RouteKey(BaseModel):
    """Identity of one physical route: authored alternative plus its realization ordinal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    detector: ComponentName
    function: FunctionName
    alternative: int = Field(ge=0)
    realization: int = Field(default=0, ge=0)


class Conflict(BaseModel):
    """Two routes that cannot be active at once because they need the same selector in different
    positions. The reason is machine-generated and shown to the operator as-is."""

    model_config = ConfigDict(extra="forbid")

    selector: StateKey
    a: RouteKey
    b: RouteKey
    a_requires: Symbol
    b_requires: Symbol
    reason: str


class TelescopeCompiled(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selectors: list[ComponentName] = Field(default_factory=list)
    detectors: list[ComponentName] = Field(default_factory=list)
    routes: list[Route] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)


class OpticsCompiled(BaseModel):
    """``optics_compiled`` — the whole observatory. ``generated_from`` is the hash of the authored
    input the compiler consumed; CI fails on drift."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION  #: a future shape gets a new literal; an artifact from it must fail here, not be misread
    generated_from: str
    generator: str | None = None  #: e.g. ``ocabox-common 1.5.0``
    telescopes: dict[str, TelescopeCompiled] = Field(default_factory=dict)
