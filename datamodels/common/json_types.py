"""Scalar types that mean the same thing in Python and in the exported JSON Schema.

JSON has one number type and a Boolean; the schema says ``number`` / ``integer`` / ``boolean``.
Pydantic's lax mode would also accept ``"1"`` or ``true`` for a number and ``1`` or ``"false"``
for a Boolean, so these are strict: what validates in Python validates in a TypeScript client.
Use them for every scalar field of a cross-runtime contract.
"""

from typing import Annotated

from annotated_types import Ge
from pydantic import AllowInfNan, BeforeValidator, Strict


def _integral(value):
    """JSON Schema defines ``integer`` by value: ``1.0`` is an integer. Python floats with an integral
    value become ints; everything else is left to the strict int validator (which rejects bool, str)."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value

#: A JSON number (integer or float); never a string, a Boolean, NaN or an infinity (JSON has none).
JsonNumber = Annotated[float, Strict(), AllowInfNan(False)]
#: A JSON integer by value (``1`` and ``1.0`` alike, as JSON Schema reads ``integer``); never a Boolean
#: (Python's bool is an int), a numeric string or a fractional number.
JsonInteger = Annotated[int, BeforeValidator(_integral), Strict()]
#: A JSON Boolean; never 0/1 or "false".
JsonBool = Annotated[bool, Strict()]
#: A 0-based ordinal. The bound sits on the inner ``int`` so that it reaches the schema as ``minimum``
#: (a constraint outside the before-validator would be emitted as an unknown ``ge`` keyword).
Index = Annotated[int, Ge(0), BeforeValidator(_integral), Strict()]

__all__ = ["JsonNumber", "JsonInteger", "JsonBool", "Index"]
