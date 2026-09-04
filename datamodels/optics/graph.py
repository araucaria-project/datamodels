"""The authored side of the Optical Path Model: what a telescope's ``components:`` may say about
optics. These models validate the *grammar* (shape, exclusivity, reserved words) so that a typo
fails at config load. Cross-component semantics — does the referenced port exist, is every
``paths`` goal satisfiable — belong to the solver's ``parse_graph`` and are reported as
``Invalid`` verdicts, not here.

Grammar (v4):

.. code-block:: yaml

    optics:
      from: X               # passive edge from X's single output
      from: {X: port}       # I hang on port `port` OF X (X owns the switch)
      from: {X: [p1, p2]}   # several live positions of X (movable pick-off, dichroic)
      inputs: {my_pos: X}   # fan-in selector: MY position selects which upstream
      from: [X, Y]          # m->1 merger — RESERVED, rejected until implemented
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from datamodels.optics.vocabulary import (
    RESERVED_WORDS,
    UNDEFINED,
    ComponentName,
    FunctionName,
    LightClass,
    PortOwner,
    Symbol,
)


def _reject_reserved(name: str, what: str) -> str:
    if name in RESERVED_WORDS:
        raise ValueError(f"{what} {name!r} is a reserved word")
    return name


# --- selector positions ----------------------------------------------------------------------


class PositionSpec(BaseModel):
    """Hardware mapping of one position symbol. The keys are vendor-specific and deliberately
    open (``port``, ``autoslew-name``, ``slot`` …); the solver never reads them — only the
    device driver does, when resolving symbol -> hardware in ``optical_select(symbol)``.

    Reference shape (jk15, shipped 2026-07-29; AutoSlew ports are 1-based)::

        positions:
          beso:  {port: 1, autoslew-name: 'ADR6'}
          andor: {port: 2, autoslew-name: 'ADR10'}
    """

    model_config = ConfigDict(extra="allow")

    port: int | str | None = None


class PositionsSpec(RootModel[dict[Symbol, PositionSpec]]):
    """``positions:`` — the symbol vocabulary a selector declares. Edges downstream reference
    these symbols and nothing else."""

    @field_validator("root")
    @classmethod
    def _no_reserved_symbols(cls, value: dict[str, PositionSpec]) -> dict[str, PositionSpec]:
        for symbol in value:
            _reject_reserved(symbol, "position symbol")
        return value

    def __iter__(self):
        return iter(self.root)

    def __contains__(self, symbol: object) -> bool:
        return symbol in self.root

    def __getitem__(self, symbol: str) -> PositionSpec:
        return self.root[symbol]


# --- edges -----------------------------------------------------------------------------------


class EdgeRef(BaseModel):
    """One normalized upstream edge. ``port`` is ``None`` for a passive edge; otherwise
    ``port_owner`` says whose port it is (see :class:`PortOwner`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    component: ComponentName
    port: Symbol | None = None
    port_owner: PortOwner | None = None

    @model_validator(mode="after")
    def _owner_iff_port(self) -> "EdgeRef":
        if (self.port is None) != (self.port_owner is None):
            raise ValueError("port and port_owner must be given together")
        return self


FromSpec = str | dict[str, str | list[str]] | list[str]


class OpticsEdges(BaseModel):
    """The ``optics:`` block of one component. Exactly one of ``from`` / ``inputs``.

    Use :meth:`edges` to get the normalized :class:`EdgeRef` list — that is the only form the
    solver and renderers consume; the YAML sugar stops here.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: FromSpec | None = Field(default=None, alias="from")
    inputs: dict[Symbol, ComponentName] | None = None

    @model_validator(mode="after")
    def _exactly_one_form(self) -> "OpticsEdges":
        if (self.from_ is None) == (self.inputs is None):
            raise ValueError("optics: exactly one of 'from' or 'inputs' is required")
        if isinstance(self.from_, list):
            raise ValueError(
                "optics.from: the list form `from: [X, Y]` (m->1 merger) is reserved and not "
                "implemented; use a splitter/selector component instead"
            )
        if isinstance(self.from_, dict):
            if len(self.from_) != 1:
                raise ValueError("optics.from: the mapping form names exactly one upstream component")
            (ports,) = self.from_.values()
            if isinstance(ports, list) and len(ports) == 0:
                raise ValueError("optics.from: the port list must not be empty")
        if self.inputs is not None and len(self.inputs) == 0:
            raise ValueError("optics.inputs: a fan-in selector needs at least one input")
        for ref in self.edges():
            _reject_reserved(ref.component, "component reference")
            if ref.port is not None:
                _reject_reserved(ref.port, "port symbol")
        return self

    def edges(self) -> list[EdgeRef]:
        """Normalize the grammar to edges. Order is the authored order."""
        if self.inputs is not None:
            return [
                EdgeRef(component=upstream, port=my_pos, port_owner=PortOwner.SELF)
                for my_pos, upstream in self.inputs.items()
            ]
        if isinstance(self.from_, str):
            return [EdgeRef(component=self.from_)]
        assert isinstance(self.from_, dict)
        ((component, ports),) = self.from_.items()
        if isinstance(ports, str):
            ports = [ports]
        return [EdgeRef(component=component, port=p, port_owner=PortOwner.UPSTREAM) for p in ports]

    @property
    def is_fan_in(self) -> bool:
        return self.inputs is not None


# --- paths as goals ---------------------------------------------------------------------------


class GoalSpec(BaseModel):
    """The explicit goal form: *see this class, through these selector positions, when this
    condition holds*. ``via`` pins the dark terminal (``dark_strict`` = railway flank
    protection); ``when`` conditions the alternative on the sky state."""

    model_config = ConfigDict(extra="forbid")

    see: LightClass
    via: dict[ComponentName, Symbol] = Field(default_factory=dict)
    when: LightClass | None = None

    @field_validator("see", "when")
    @classmethod
    def _goal_is_never_undefined(cls, value: str | None) -> str | None:
        if value == UNDEFINED:
            raise ValueError("a goal can never be 'undefined'")
        return value


#: One alternative of a goal: a bare light class or an explicit :class:`GoalSpec`.
GoalAlternative = LightClass | GoalSpec

#: What a detector function wants to see: a class, an explicit goal, or an ordered list of
#: alternatives (first satisfiable wins).
GoalExpr = GoalAlternative | list[GoalAlternative]


class DetectorPaths(RootModel[dict[FunctionName, GoalExpr]]):
    """``paths:`` on a detector — functions mapped to goals. Function names from
    :class:`~datamodels.optics.vocabulary.CoreFunction` carry a reserved meaning; others are
    free."""

    @field_validator("root")
    @classmethod
    def _shape(cls, value: dict[str, GoalExpr]) -> dict[str, GoalExpr]:
        # function names are their own namespace: `dark` is the DARK verb here, not the light class
        for function, goal in value.items():
            if isinstance(goal, list) and len(goal) == 0:
                raise ValueError(f"paths.{function}: the alternatives list must not be empty")
            for alt in goal if isinstance(goal, list) else [goal]:
                if alt == UNDEFINED:
                    raise ValueError(f"paths.{function}: a goal can never be 'undefined'")
        return value

    def alternatives(self, function: str) -> list[GoalSpec]:
        """The goal of ``function`` as an ordered list of explicit :class:`GoalSpec`."""
        goal = self.root[function]
        alts = goal if isinstance(goal, list) else [goal]
        return [alt if isinstance(alt, GoalSpec) else GoalSpec(see=alt) for alt in alts]

    def __iter__(self):
        return iter(self.root)

    def __contains__(self, function: object) -> bool:
        return function in self.root

    def __getitem__(self, function: str) -> GoalExpr:
        return self.root[function]


# --- presentation hints -----------------------------------------------------------------------


class DisplayHint(BaseModel):
    """Presentational hints, ignored by the solver. ``color`` overrides the source-class colour of
    a source component; ``x``/``y`` position a node for non-linear graphs (BESO branch)."""

    model_config = ConfigDict(extra="allow")

    color: str | None = None
    x: float | None = None
    y: float | None = None


# --- a component, as optics sees it ------------------------------------------------------------


class OpticalComponentSpec(BaseModel):
    """The optics-relevant view of one ``components:`` entry. Device fields (addresses, device
    numbers, driver options) are carried through as extras and ignored; only ``kind`` is
    required because the archetype is derived from it."""

    model_config = ConfigDict(extra="allow")

    kind: str
    positions: PositionsSpec | None = None
    optics: OpticsEdges | None = None
    paths: DetectorPaths | None = None
    display: DisplayHint | None = None


class TelescopeOpticsSpec(BaseModel):
    """One telescope's components plus optional whole-telescope preset sugar
    (``presets: {name: {detector: function}}`` — an alias table, never truth)."""

    model_config = ConfigDict(extra="allow")

    components: dict[ComponentName, OpticalComponentSpec]
    presets: dict[str, dict[ComponentName, FunctionName]] = Field(default_factory=dict)

    @field_validator("components")
    @classmethod
    def _no_reserved_component_names(cls, value: dict[str, Any]) -> dict[str, Any]:
        for name in value:
            _reject_reserved(name, "component name")
        return value

    @model_validator(mode="after")
    def _presets_reference_declared_paths(self) -> "TelescopeOpticsSpec":
        for preset, entries in self.presets.items():
            for detector, function in entries.items():
                component = self.components.get(detector)
                if component is None:
                    raise ValueError(f"presets.{preset}: unknown detector {detector!r}")
                if component.paths is None or function not in component.paths:
                    raise ValueError(
                        f"presets.{preset}: detector {detector!r} declares no path {function!r}"
                    )
        return self
