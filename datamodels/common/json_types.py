"""Scalar types that mean the same thing in Python and in the exported JSON Schema.

JSON has one number type and a Boolean; the schema says ``number`` / ``integer`` / ``boolean``.
Pydantic's lax mode would also accept ``"1"`` or ``true`` for a number and ``1`` or ``"false"``
for a Boolean, so these are strict: what validates in Python validates in a TypeScript client.
Use them for every scalar field of a cross-runtime contract.
"""

from typing import Annotated

from annotated_types import Ge
from pydantic import AllowInfNan, Strict

#: A JSON number (integer or float); never a string, a Boolean, NaN or an infinity (JSON has none).
JsonNumber = Annotated[float, Strict(), AllowInfNan(False)]
#: A JSON integer; never a Boolean (Python's bool is an int) or a numeric string.
JsonInteger = Annotated[int, Strict()]
#: A JSON Boolean; never 0/1 or "false".
JsonBool = Annotated[bool, Strict()]
#: A 0-based ordinal.
Index = Annotated[JsonInteger, Ge(0)]

__all__ = ["JsonNumber", "JsonInteger", "JsonBool", "Index"]
