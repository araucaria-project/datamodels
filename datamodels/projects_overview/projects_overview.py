from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Status(StrEnum):
    ONGOING = "ongoing"
    PAUSED = "paused"
    HALTED = "halted"
    WAITING = "waiting"
    FINISHED = "finished"


class LightCurve(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str # same as dict key
    display_name: str
    status: Status | None = None
    file_name: str | None = None


class ObjectOverview(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str # same as dict key
    display_name: str
    status: Status
    lc: dict[str, LightCurve] = Field(default_factory=dict)
    # skymap: dict[str, Any] = Field(default_factory=dict)
    # info: dict[str, Any] = Field(default_factory=dict)


class ProjectOverview(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str # same as dict key
    display_name: str
    pi: str | None = None
    sciprog: str | None = None
    status: Status
    objects: dict[str, ObjectOverview] = Field(default_factory=dict)


class ProjectsOverview(BaseModel):
    model_config = ConfigDict(extra="allow")

    processed_date: datetime
    processed_folder: str
    telescope: str
    projects: dict[str, ProjectOverview] = Field(default_factory=dict)
