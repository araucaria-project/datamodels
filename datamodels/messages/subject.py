"""The subject grammar ``<class>.<realm>.<scope>.<element>.<item>`` (oca_nats_config#2).

Exactly five tokens, each ``[a-z0-9_]+``, each position with one meaning:

- **class** — what kind of message; selects the payload model, the stream and its retention
- **realm** — the system that owns the vocabulary (``tic``, ``env``, ``fac``, or a service such as ``optics``)
- **scope** — where it applies, as an absolute id: a telescope id, ``oca``, ``camk``, ``global``
- **element** — a configured entity of the scope with a scope-unique name; ``self`` is the scope itself
- **item** — what about it; one token, defined by the realm

``svc.>`` belongs to the ocabox-tcs library and keeps its own schema, so it is not a class here.
"""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

#: One subject token.
Token = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]+$")]

#: The element that stands for the scope as a whole.
SELF = "self"


class MessageClass(StrEnum):
    """First token of a subject. ``svc`` is reserved for the TCS library and deliberately absent."""

    STATUS = "status"  #: state of a component or service, on change plus keepalive
    TELEMETRY = "telemetry"  #: numeric measurement (time series)
    EVENT = "event"  #: something happened
    JOURNAL = "journal"  #: timestamped log record for humans
    DATA = "data"  #: pipeline or analysis product
    MESSAGE = "message"  #: operator notice
    CFG = "cfg"  #: configuration document
    RPC = "rpc"  #: request/reply on core NATS
    CMD = "cmd"  #: fire-and-forget command


class Subject(BaseModel):
    """A parsed subject. ``str(subject)`` is the wire form; :meth:`parse` is its inverse."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    message_class: MessageClass = Field(alias="class")
    realm: Token
    scope: Token
    element: Token
    item: Token

    @classmethod
    def parse(cls, subject: str) -> Self:
        """Parse a five-token subject; raises ``ValueError`` for any other shape."""
        tokens = subject.split(".")
        if len(tokens) != 5:
            raise ValueError(f"{subject!r}: a subject has exactly five tokens <class>.<realm>.<scope>.<element>.<item>")
        message_class, realm, scope, element, item = tokens
        return cls(message_class=message_class, realm=realm, scope=scope, element=element, item=item)

    def __str__(self) -> str:
        return f"{self.message_class}.{self.realm}.{self.scope}.{self.element}.{self.item}"
