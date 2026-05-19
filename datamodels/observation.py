from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Info(BaseModel):
    model_config = ConfigDict(extra="allow")

    obs_id: str
    date_obs: datetime
    oca_jd: int


class Measurement(BaseModel):
    model_config = ConfigDict(extra="allow")

    category: str
    result: Any = None


class File(BaseModel):
    model_config = ConfigDict(extra="allow")

    category: str
    file_name: str | None = None
    header: dict | None = None
    measurements: list[Measurement] = Field(default_factory=list)


class Observation(BaseModel):
    model_config = ConfigDict(extra="allow")

    info: Info
    quality_checks: dict[str, Any] = Field(default_factory=dict)
    objects: dict[str, Any] = Field(default_factory=dict)
    files: list[File] = Field(default_factory=list)
    measurements: list[Measurement] = Field(default_factory=list)
