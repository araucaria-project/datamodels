"""What the solver answers: ``sees()`` records and ``check()`` verdicts. Every client — TIC RPC,
CLI, TOI, the browser visualizer — consumes these shapes; none of them computes them.
"""

from typing import Annotated, Literal

from annotated_types import Len

from pydantic import BaseModel, ConfigDict, Field, model_validator

from datamodels.optics.vocabulary import CLOSED_STATE_KEYS, ComponentName, FunctionName, GoalClass, LightClass, StateKey, Symbol, VerdictKind


class SeesRecord(BaseModel):
    """One thing a detector sees. ``sees(detector)`` returns a *set* of these — a cover-open +
    calibrator-on state yields both ``sky.*`` and ``lamp``; a splitter yields several.

    ``terminal`` is the source component — or, for ``dark``, the *blocking* component:
    ``dark @ tertiary`` (looking at the back of M3) is not ``dark @ covercalibrator`` (closed
    covers). For ``undefined`` it is the selector whose state is unknown.

    ``via`` lists the components crossed between the terminal (exclusive) and the detector
    (exclusive), in the direction light travels — enough for a renderer to colour the edges.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    light_class: LightClass = Field(alias="class")
    terminal: ComponentName
    via: tuple[ComponentName, ...]  #: required on the wire, empty for a direct view — so that equal records are equal JSON objects


class ConfigError(BaseModel):
    """One load-time problem with the authored graph."""

    model_config = ConfigDict(extra="forbid")

    code: str  #: stable machine-readable code, e.g. ``undeclared_port``, ``duplicate_from``, ``unsatisfiable_path``
    message: str
    component: ComponentName | None = None
    path: str | None = None  #: dotted location in the config, e.g. ``camera.paths.dark_strict[1].via``


class Active(BaseModel):
    """The detector already sees the goal."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[VerdictKind.ACTIVE]
    see: GoalClass  #: a satisfied goal is a goal: never ``undefined``
    positions: dict[StateKey, Symbol] = Field(default_factory=dict, json_schema_extra=CLOSED_STATE_KEYS)  #: proven selector positions on the path


class Settable(BaseModel):
    """Not active, but these selector moves make it so. ``moves`` is the subset of ``positions``
    that differs from the proven state; ``confirm`` the moves that wait for a person's confirmation
    before anything moves (the telescope and the dome to the flat screen; the covers by day)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[VerdictKind.SETTABLE]
    see: GoalClass
    positions: dict[StateKey, Symbol] = Field(json_schema_extra=CLOSED_STATE_KEYS)
    #: at least one move — with nothing to move the verdict would be ``active``
    moves: Annotated[dict[StateKey, Symbol], Len(min_length=1), Field(json_schema_extra=CLOSED_STATE_KEYS)]
    confirm: tuple[StateKey, ...] = ()

    @model_validator(mode="after")
    def _confirm_is_a_move(self) -> "Settable":
        stray = sorted(set(self.confirm) - set(self.moves))
        if stray:
            raise ValueError(f"confirm names {', '.join(stray)}, which are not moves")
        return self


class Collision(BaseModel):
    """A required selector is held in a contradictory position. ``holder`` names who holds it when
    the access grantor knows; the reason is human-readable and stable enough to display."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[VerdictKind.COLLISION]
    selector: StateKey
    required: Symbol
    held: Symbol
    holder: str | None = None
    reason: str


class Impossible(BaseModel):
    """No alternative of the goal can be provided now — typically the source class is
    unavailable (``sky.science`` in daytime) or every path crosses an ``undefined`` selector.

    ``awaits`` is the light that will come by itself (the sky's science light at dusk): the goal is
    only *not yet* possible, and ``prepare`` holds the selector moves that make the path ready for
    it — empty when it already is. A lamp or the flat screen never comes by itself, so it is never
    awaited."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[VerdictKind.IMPOSSIBLE]
    reason: str
    unavailable: LightClass | None = None
    undefined_at: tuple[StateKey, ...] = ()
    awaits: LightClass | None = None
    prepare: dict[StateKey, Symbol] = Field(default_factory=dict, json_schema_extra=CLOSED_STATE_KEYS)

    @model_validator(mode="after")
    def _prepare_awaits(self) -> "Impossible":
        if self.prepare and self.awaits is None:
            raise ValueError("prepare without awaits: moves prepare a path only for light that will come")
        return self


class Invalid(BaseModel):
    """Config error. Raised at load/deploy time by ``parse_graph``; never a runtime surprise."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[VerdictKind.INVALID]
    errors: Annotated[list[ConfigError], Len(min_length=1)]  #: an invalid verdict always says why


#: The tag is required on every variant — Python and the JSON Schema agree that an untagged verdict is no verdict.
Verdict = Annotated[Active | Settable | Collision | Impossible | Invalid, Field(discriminator="kind")]


class CheckResult(BaseModel):
    """``check(detector, function)`` — the verdict, addressed."""

    model_config = ConfigDict(extra="forbid")

    detector: ComponentName
    function: FunctionName
    verdict: Verdict
