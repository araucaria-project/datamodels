"""Vocabulary of the Optical Path Model (v4).

Everything here is a *name*, never logic: light classes, detector functions, archetypes,
verdict kinds and the reserved words. The reference solver (ocabox-common) and every client
import these so that the same word means the same thing on every telescope.

Spec: knowledge-base ``Architecture/Optical Path Model.md``.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, StringConstraints, WithJsonSchema

# --- reserved words ------------------------------------------------------------------------

#: The detector looks at something that emits no light: a closed cover, the back of M3, a
#: beam dump. ``dark`` is a legitimate steady state, never an error.
DARK = "dark"
#: The path crosses a selector whose state is unknown: mid-slew, unmapped readback, stale
#: telemetry. ``undefined`` validates nothing and is rendered as an alarm.
UNDEFINED = "undefined"

RESERVED_WORDS: frozenset[str] = frozenset({DARK, UNDEFINED})

# --- identifier shapes ----------------------------------------------------------------------

_IDENT = r"[a-z][a-z0-9_]*"


def _not_reserved(value: str) -> str:
    """No part of a name (``x`` or ``x.y``) may be a reserved word. Part of the identifier *types*
    below, so every model that names a component, a symbol or a state key rejects ``dark`` /
    ``undefined`` — results and compiled artifacts included, not only the authored grammar."""
    for part in value.split("."):
        if part in RESERVED_WORDS:
            raise ValueError(f"{value!r}: {part!r} is a reserved word")
    return value


#: The same rule in JSON Schema (pydantic's regex engine has no look-around, so the exclusion is a
#: ``not`` clause rather than part of the pattern). A TypeScript validator rejects exactly what Python does.
_NAME_SCHEMA = {"type": "string", "pattern": rf"^{_IDENT}$", "not": {"enum": sorted(RESERVED_WORDS)}}
_STATE_KEY_SCHEMA = {
    "type": "string",
    "pattern": rf"^{_IDENT}(\.{_IDENT})?$",
    "not": {"anyOf": [{"pattern": r"^(dark|undefined)(\.|$)"}, {"pattern": r"\.(dark|undefined)$"}]},
}

#: JSON Schema extras for maps keyed by the identifier types: pydantic emits ``patternProperties``
#: from the key pattern but neither closes the object nor carries the reserved-word exclusion.
#: Attach with ``Field(json_schema_extra=...)`` so a JSON Schema validator rejects exactly the keys
#: Python rejects.
CLOSED_NAME_KEYS = {"additionalProperties": False, "propertyNames": {"not": _NAME_SCHEMA["not"]}}
CLOSED_STATE_KEYS = {"additionalProperties": False, "propertyNames": {"not": _STATE_KEY_SCHEMA["not"]}}

#: A component name as it appears under ``components:`` in the observatory config
#: (``tertiary``, ``guider_beso``). Lower-case identifiers only, never a reserved word.
ComponentName = Annotated[str, StringConstraints(pattern=rf"^{_IDENT}$"), AfterValidator(_not_reserved), WithJsonSchema(_NAME_SCHEMA)]

#: A selector position symbol declared under a device's ``positions:`` (``beso``, ``andor``,
#: ``open``, ``thar``). Symbols are the *only* thing edges reference; hardware numbers stay
#: inside the ``positions:`` mapping. Never a reserved word.
Symbol = Annotated[str, StringConstraints(pattern=rf"^{_IDENT}$"), AfterValidator(_not_reserved), WithJsonSchema(_NAME_SCHEMA)]

#: A light class: ``<family>`` or ``<family>.<state>`` (``lamp``, ``flatscreen``,
#: ``sky.science``). The dotted form is reserved for stateful sources; the reserved words
#: ``dark`` and ``undefined`` share the shape so that a ``sees()`` result is one type.
LightClass = Annotated[str, StringConstraints(pattern=rf"^{_IDENT}(\.{_IDENT})?$")]

#: A detector function name — the key of a ``paths:`` entry (``object``, ``dark``, ``domeflat``).
FunctionName = Annotated[str, StringConstraints(pattern=rf"^{_IDENT}$")]

#: What a selector position is keyed by in proven state, ``via`` and route tables: a component
#: name, or ``<component>.<aspect>`` for one axis of a multi-aspect selector — the reserved
#: dotted state form. An Alpaca cover calibrator is one component with two independent axes:
#: ``covercalibrator`` (the cover: open/close) and ``covercalibrator.calibrator`` (the lamp:
#: on/off). Which aspects a kind has is device contract, never config.
StateKey = Annotated[str, StringConstraints(pattern=rf"^{_IDENT}(\.{_IDENT})?$"), AfterValidator(_not_reserved), WithJsonSchema(_STATE_KEY_SCHEMA)]


def state_key(component: str, aspect: str | None = None) -> str:
    """``("covercalibrator", "calibrator")`` -> ``covercalibrator.calibrator``; no aspect -> the name."""
    return f"{component}.{aspect}" if aspect else component


def split_state_key(key: str) -> tuple[str, str | None]:
    """``covercalibrator.calibrator`` -> ``("covercalibrator", "calibrator")``; ``tertiary`` -> ``("tertiary", None)``."""
    component, _, aspect = key.partition(".")
    return component, (aspect or None)


def light_family(light_class: str) -> str:
    """``sky.science`` -> ``sky``; ``lamp`` -> ``lamp``."""
    return light_class.split(".", 1)[0]


def light_state(light_class: str) -> str | None:
    """``sky.science`` -> ``science``; ``lamp`` -> ``None``."""
    _, _, state = light_class.partition(".")
    return state or None


# --- closed vocabularies ---------------------------------------------------------------------


class Archetype(StrEnum):
    """What a component does to light. Derived from ``kind`` by an explicit registry in code
    (ocabox-server), never from config strings. Also the drawing glyph."""

    SOURCE = "source"  #: emits a light class: sky, lamp, flatscreen, beamdump
    SELECTOR = "selector"  #: routes one input to one of several outputs, or blocks it: M3, cover, lamp wheel
    SPLITTER = "splitter"  #: feeds several outputs at once: beamsplitter, guider pick-off
    PASSIVE = "passive"  #: transmits unchanged: rotator, filterwheel, fibre
    DETECTOR = "detector"  #: the sink light is asked about: camera, spectrograph


class SourceFamily(StrEnum):
    """Light-class families that ship with the model. Open vocabulary — a config may introduce a
    new family and the solver treats it as an opaque source class; these are the ones the
    vocabulary, rendering colours and the sky predicate know about."""

    SKY = "sky"
    LAMP = "lamp"
    FLATSCREEN = "flatscreen"
    BEAMDUMP = "beamdump"


class SkyState(StrEnum):
    """States of the stateful ``sky`` source, computed from sun altitude by the solver (config may
    override thresholds). ``sky.science`` is what OBJECT needs; ``sky.flat`` is what SKYFLAT needs."""

    SCIENCE = "science"  #: sun below -18 deg
    TWILIGHT = "twilight"
    FLAT = "flat"  #: roughly -15 .. +1 deg
    DAY = "day"


class CoreFunction(StrEnum):
    """Detector functions with a reserved meaning — the obsplan verbs, lower-cased. An observing
    program resolves identically on every telescope because every telescope's ``paths:`` uses
    these names for these purposes. Config may add extra functions freely."""

    OBJECT = "object"
    SNAP = "snap"
    FOCUS = "focus"
    SKYFLAT = "skyflat"
    DOMEFLAT = "domeflat"
    DARK = "dark"
    ZERO = "zero"


class VerdictKind(StrEnum):
    """Outcome of ``check(detector, function)``."""

    ACTIVE = "active"  #: the detector already sees the goal
    SETTABLE = "settable"  #: not now, but a legal set of selector moves gets there
    COLLISION = "collision"  #: a required selector is held in a contradictory position
    IMPOSSIBLE = "impossible"  #: no source can provide the goal now (e.g. sky.science by day)
    INVALID = "invalid"  #: config error — caught at load time, never at 3 a.m.


class PortOwner(StrEnum):
    """Who owns the port an edge is labelled with. Encodes the one edge-grammar invariant:
    *an edge label always names a port of the switch-owning component; the edge is live iff that
    owner currently emits on that port.*"""

    UPSTREAM = "upstream"  #: ``from: {X: port}`` — the port belongs to X
    SELF = "self"  #: ``inputs: {my_pos: X}`` — the position belongs to the declaring component
