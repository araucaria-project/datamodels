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

from typing import Annotated, Any

from annotated_types import Len
from pydantic import BaseModel, ConfigDict, Field, model_validator, RootModel

from datamodels.common import JsonInteger, JsonNumber
from datamodels.optics.vocabulary import (
    CLOSED_NAME_KEYS,
    CLOSED_STATE_KEYS,
    ComponentName,
    FunctionName,
    GoalClass,
    LightClass,
    PortOwner,
    SourceLightClass,
    StateKey,
    Symbol,
)


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

    port: JsonInteger | str | None = None  #: a JSON integer or a string; never a Boolean


class PositionsSpec(RootModel[dict[Symbol, PositionSpec]]):
    """``positions:`` — the symbol vocabulary a selector declares. Edges downstream reference
    these symbols and nothing else. Reserved words are excluded by :data:`Symbol` itself."""

    model_config = ConfigDict(json_schema_extra=CLOSED_NAME_KEYS)

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

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            # port and port_owner come together or not at all — stated for JSON Schema validators too
            "oneOf": [
                {"required": ["port", "port_owner"], "properties": {"port": {"type": "string"}, "port_owner": {"type": "string"}}},
                {"properties": {"port": {"type": "null"}, "port_owner": {"type": "null"}}},
            ]
        },
    )

    component: ComponentName
    port: Symbol | None = None
    port_owner: PortOwner | None = None

    @model_validator(mode="after")
    def _owner_iff_port(self) -> "EdgeRef":
        if (self.port is None) != (self.port_owner is None):
            raise ValueError("port and port_owner must be given together")
        return self


#: ``from: X`` | ``from: {X: port}`` | ``from: {X: [p1, p2]}``. The reserved list form is not part of
#: the type: a ``before`` validator turns it into a clear error, and the schema simply does not admit it.
Ports = Symbol | Annotated[list[Symbol], Len(min_length=1)]
FromSpec = ComponentName | Annotated[dict[ComponentName, Ports], Len(min_length=1, max_length=1), Field(json_schema_extra=CLOSED_NAME_KEYS)]

#: Exactly one of ``from`` / ``inputs`` — stated in the schema, not only in Python.
_EXACTLY_ONE_FORM = {
    # `required` only checks presence, so each branch also pins the other form to null-or-absent and its own to non-null
    "oneOf": [
        {"required": ["from"], "properties": {"from": {"not": {"type": "null"}}, "inputs": {"type": "null"}}},
        {"required": ["inputs"], "properties": {"inputs": {"not": {"type": "null"}}, "from": {"type": "null"}}},
    ]
}


class OpticsEdges(BaseModel):
    """The ``optics:`` block of one component. Exactly one of ``from`` / ``inputs``.

    Use :meth:`edges` to get the normalized :class:`EdgeRef` list — that is the only form the
    solver and renderers consume; the YAML sugar stops here.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True, json_schema_extra=_EXACTLY_ONE_FORM)

    from_: FromSpec | None = Field(default=None, alias="from")
    inputs: Annotated[dict[Symbol, ComponentName], Len(min_length=1), Field(json_schema_extra=CLOSED_NAME_KEYS)] | None = None

    @model_validator(mode="before")
    @classmethod
    def _reserved_list_form(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("from", data.get("from_")), list):
            raise ValueError(
                "optics.from: the list form `from: [X, Y]` (m->1 merger) is reserved and not "
                "implemented; use a splitter/selector component instead"
            )
        return data

    @model_validator(mode="after")
    def _exactly_one_form(self) -> "OpticsEdges":
        if (self.from_ is None) == (self.inputs is None):
            raise ValueError("optics: exactly one of 'from' or 'inputs' is required")
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
    condition holds, with these positions held too*. ``via`` pins components the light passes
    (``dark_strict`` = railway flank protection); ``when`` conditions the alternative on the sky
    state; ``also`` holds positions of components that are *not* on the path — the covers closed
    while M3 already turns the camera away (stray light finds its way around a mirror)."""

    model_config = ConfigDict(extra="forbid")

    see: GoalClass
    via: dict[StateKey, Symbol] = Field(default_factory=dict, json_schema_extra=CLOSED_STATE_KEYS)
    when: GoalClass | None = None
    also: dict[StateKey, Symbol] | None = Field(default=None, json_schema_extra=CLOSED_STATE_KEYS)  #: absent, like ``when``, when nothing more is held

    @model_validator(mode="after")
    def _also_is_not_via(self) -> "GoalSpec":
        both = sorted(set(self.via) & set(self.also or {}))
        if both:
            raise ValueError(f"{', '.join(both)}: in both via and also — via already holds what the light passes")
        return self


#: One alternative of a goal: a bare light class (never ``undefined``) or an explicit :class:`GoalSpec`.
GoalAlternative = GoalClass | GoalSpec

#: What a detector function wants to see: a class, an explicit goal, or an ordered list of
#: alternatives (first satisfiable wins).
GoalExpr = GoalAlternative | Annotated[list[GoalAlternative], Len(min_length=1)]


class DetectorPaths(RootModel[dict[FunctionName, GoalExpr]]):
    """``paths:`` on a detector — functions mapped to goals. Function names from
    :class:`~datamodels.optics.vocabulary.CoreFunction` carry a reserved meaning; others are
    free."""

    model_config = ConfigDict(json_schema_extra={"additionalProperties": False})  # `dark` is a legal function name here

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
    """Presentational hints, never optical truth. ``label`` is what people call the component
    ("mirror covers", "ThAr lamp") and ``aspects`` names its aspects (``{calibrator: "flat lamp"}``)
    — both override the kind's defaults in every human-facing text; ``glyph`` names the symbol it
    wears instead of its kind's (a guider camera: ``guider``); ``color`` overrides the
    source-class colour of a source component; ``x``/``y`` place it on the schematic grid, in
    cells — ``x`` the column along the light (sources left, detectors right), ``y`` the row
    (branches below the main line); components without them are laid out automatically
    (``obcom.optics.schematic``)."""

    model_config = ConfigDict(extra="allow")

    label: str | None = None
    aspects: dict[str, str] | None = None
    glyph: str | None = None
    color: str | None = None
    x: JsonNumber | None = None
    y: JsonNumber | None = None


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
    light: SourceLightClass | None = None  #: sources only: the state of the kind's family this one emits (``lamp.thar``)
    display: DisplayHint | None = None


class TelescopeOpticsSpec(BaseModel):
    """One telescope's components plus optional whole-telescope preset sugar
    (``presets: {name: {detector: function}}`` — an alias table, never truth).

    Shape only: whether a preset names an existing detector and one of its declared paths is a
    cross-component fact and is reported by the solver's ``parse_graph`` (``preset_unknown_detector``
    / ``preset_unknown_path``), so Python and TypeScript consumers share one shape contract."""

    model_config = ConfigDict(extra="allow")

    components: dict[ComponentName, OpticalComponentSpec] = Field(json_schema_extra=CLOSED_NAME_KEYS)
    presets: dict[str, Annotated[dict[ComponentName, FunctionName], Field(json_schema_extra=CLOSED_NAME_KEYS)]] = Field(default_factory=dict)
