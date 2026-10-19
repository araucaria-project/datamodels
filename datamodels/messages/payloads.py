"""The ``data`` of messages per subject class. The serverish envelope stays ``{data, meta}``.

Two times, never confused: ``meta.ts`` (added by serverish) is when the *message* was sent;
``data.ts`` is when the *thing* happened or was established. Consumers that fall back from the
second to the first must know they did.
"""

from enum import StrEnum
from typing import Annotated, Literal

from annotated_types import Gt
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from datamodels.common import JsonInteger, JsonNumber, Timestamp


class StatusValue(BaseModel):
    """``data`` of ``status.*``: one element's item, one value per subject, published on change and
    repeated as keepalive. ``ts`` is when the state was established, not when it was last repeated."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: JsonValue
    ts: Timestamp


class Caller(BaseModel):
    """On whose behalf a request is made. Authorisation happens before the request reaches the
    service (TIC's blocker); the service uses this for its log and audit, never to grant access."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    id: str


class RpcRequest(BaseModel):
    """``data`` of an ``rpc.*`` request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    caller: Caller | None = None
    timeout: Annotated[JsonNumber, Gt(0)] | None = None  #: seconds the caller waits; relative, so host clocks never matter


class Severity(StrEnum):
    """Error severity, as in the obcom error model."""

    TEMPORARY = "TEMPORARY"  #: retrying soon may succeed
    NORMAL = "NORMAL"  #: this request failed
    CRITICAL = "CRITICAL"  #: asking again will fail the same way


class RpcOk(BaseModel):
    """A successful reply. For a long operation it means *accepted*; the outcome follows as status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ok"] = "ok"
    result: JsonValue = None


class RpcError(BaseModel):
    """A refused or failed request, with an obcom error code (ocabox-server ``doc/errors.md``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["error"] = "error"
    code: JsonInteger
    severity: Severity
    message: str


#: ``data`` of an ``rpc.*`` reply.
RpcReply = Annotated[RpcOk | RpcError, Field(discriminator="status")]
