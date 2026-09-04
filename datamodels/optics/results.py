"""What the solver answers: ``sees()`` records and ``check()`` verdicts. Every client — TIC RPC,
CLI, TOI, the browser visualizer — consumes these shapes; none of them computes them.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from datamodels.optics.vocabulary import ComponentName, FunctionName, LightClass, Symbol, VerdictKind


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
    via: tuple[ComponentName, ...] = ()


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

    kind: Literal[VerdictKind.ACTIVE] = VerdictKind.ACTIVE
    see: LightClass
    positions: dict[ComponentName, Symbol] = Field(default_factory=dict)  #: proven selector positions on the path


class Settable(BaseModel):
    """Not active, but these selector moves make it so. ``moves`` is the subset of ``positions``
    that differs from the proven state."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[VerdictKind.SETTABLE] = VerdictKind.SETTABLE
    see: LightClass
    positions: dict[ComponentName, Symbol]
    moves: dict[ComponentName, Symbol]


class Collision(BaseModel):
    """A required selector is held in a contradictory position. ``holder`` names who holds it when
    the access grantor knows; the reason is human-readable and stable enough to display."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[VerdictKind.COLLISION] = VerdictKind.COLLISION
    selector: ComponentName
    required: Symbol
    held: Symbol
    holder: str | None = None
    reason: str


class Impossible(BaseModel):
    """No alternative of the goal can be provided now — typically the source class is
    unavailable (``sky.science`` in daytime) or every path crosses an ``undefined`` selector."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[VerdictKind.IMPOSSIBLE] = VerdictKind.IMPOSSIBLE
    reason: str
    unavailable: LightClass | None = None
    undefined_at: tuple[ComponentName, ...] = ()


class Invalid(BaseModel):
    """Config error. Raised at load/deploy time by ``parse_graph``; never a runtime surprise."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[VerdictKind.INVALID] = VerdictKind.INVALID
    errors: list[ConfigError]


Verdict = Annotated[Active | Settable | Collision | Impossible | Invalid, Field(discriminator="kind")]


class CheckResult(BaseModel):
    """``check(detector, function)`` — the verdict, addressed."""

    model_config = ConfigDict(extra="forbid")

    detector: ComponentName
    function: FunctionName
    verdict: Verdict
