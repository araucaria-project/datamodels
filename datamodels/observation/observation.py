from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class Info(BaseModel):
    model_config = ConfigDict(extra="allow")

    obs_id: str
    date_obs: datetime
    jd_date_obs: float
    oca_night: int


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

    async def get_measurement(self, category: str) -> Optional[Measurement]:
        for measurement in self.measurements:
            if measurement.category == category:
                return measurement
        return None


class Observation(BaseModel):
    model_config = ConfigDict(extra="allow")

    info: Info
    quality_checks: dict[str, Any] = Field(default_factory=dict)
    objects: dict[str, Any] = Field(default_factory=dict)
    files: list[File] = Field(default_factory=list)
    measurements: list[Measurement] = Field(default_factory=list)

    async def get_measurement(self, category: str) -> Optional[Measurement]:
        for measurement in self.measurements:
            if measurement.category == category:
                return measurement
        return None

    async def get_file(self, category: str) -> Optional[File]:
        for file in self.files:
            if file.category == category:
                return file
        return None

