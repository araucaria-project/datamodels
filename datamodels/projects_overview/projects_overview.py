from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class Status(StrEnum):
    ONGOING = "ongoing"
    PAUSED = "paused"
    HALTED = "halted"
    WAITING = "waiting"
    FINISHED = "finished"
    OMITTED = "omitted"


class LcInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    telescope: str
    object: str
    filter: str
    prefix: str | None = None
    mag_type: str | None = None
    lc_type: str | None = None
    method: str | None = None
    period: float | None = None
    hjd0: float | None = None
    re_rendered: datetime | None = None


class LcMeasurement(BaseModel):
    model_config = ConfigDict(extra="allow")

    category: str
    result: Any = None


class LcModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    category: str
    result: Any = None


class LightCurve(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str # same as dict key
    display_name: str
    status: Status | None = None
    file_name: str | None = None
    info: LcInfo | None = None
    measurements: list[LcMeasurement] = Field(default_factory=list)
    models: list[LcModel] = Field(default_factory=list)

    async def get_measurement(self, category: str) -> Optional[LcMeasurement]:
        for measurement in self.measurements:
            if measurement.category == category:
                return measurement
        return None

    async def get_model(self, category: str) -> Optional[LcModel]:
        for model in self.models:
            if model.category == category:
                return model
        return None


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
