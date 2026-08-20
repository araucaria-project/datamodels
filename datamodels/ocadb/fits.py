"""Shared FITS-file / OcaDB data-transport models.

These are plain pydantic models only — no ODM (Beanie/Mongo) or web-framework
(FastAPI) dependencies. Consumers that need persistence (e.g. ocadb) should
subclass FITSFile together with their own Document base class locally, rather
than extending this module with storage-specific behavior.
"""
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, BeforeValidator, Field


class StorageStatusType(str, Enum):
    """Status types for file storage operations."""
    NOT_STORED = "not_stored"
    DELETED = "deleted"
    STORED = "stored"
    CORRUPTED = "corrupted"
    REQUESTED = "requested"
    SCHEDULED = "scheduled"
    ON_DEMAND = "on_demand"
    QUEUED = "queued"
    STORING = "storing"


class FileClassification(str, Enum):
    """FITS file classification types."""
    RAW = "raw"
    ZDF = "zdf"
    MASTER = "master"
    SOURCE = "source"
    TMP = "tmp"
    TEST = "test"
    ZERO = "zero"

    @classmethod
    def from_suffix(cls, suffix: str | None) -> "FileClassification":
        """Map an ocafitsfiles filename suffix to a FileClassification."""
        if suffix is None:
            return cls.RAW
        s = suffix.lower()
        if s == "zdf":
            return cls.ZDF
        if s.startswith("master"):
            return cls.MASTER
        return cls.RAW


DigestStr = Annotated[
    str,
    Field(
        pattern=r"^(sha-256|sha-512|md5)=[A-Za-z0-9+/]+={0,2}$",
        description="Content digest per RFC 3230/8240 (e.g., 'sha-256=<base64>')",
    ),
]


def _coerce_int(value):
    if isinstance(value, str):
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    return value


def _coerce_float(value):
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return value


def _coerce_str(value):
    if value is None or isinstance(value, str):
        return value
    return str(value)


# FITS header keywords are frequently the "wrong" type (e.g. a numeric
# keyword serialized as a string). These annotated types coerce leniently
# (falling back to None on bad input) instead of raising a validation error.
LenientInt = Annotated[Optional[int], BeforeValidator(_coerce_int)]
LenientFloat = Annotated[Optional[float], BeforeValidator(_coerce_float)]
LenientStr = Annotated[Optional[str], BeforeValidator(_coerce_str)]


class FitsHeader(BaseModel):
    """Direct mapping of FITS header keywords (exact field names)."""
    SIMPLE: Optional[bool] = None
    BITPIX: LenientInt = None
    NAXIS: LenientInt = None
    NAXIS1: LenientInt = None
    NAXIS2: LenientInt = None
    OCASTD: LenientStr = None
    OBSERVAT: LenientStr = None
    OBS_LAT: LenientFloat = Field(None, alias="OBS-LAT")
    OBS_LONG: LenientFloat = Field(None, alias="OBS-LONG")
    OBS_ELEV: LenientInt = Field(None, alias="OBS-ELEV")
    ORIGIN: LenientStr = None
    TELESCOP: LenientStr = None
    DATE_OBS: LenientStr = Field(None, alias="DATE-OBS")
    JD: LenientFloat = None
    RA: LenientFloat = None
    DEC: LenientFloat = None
    EQUINOX: LenientStr = None
    RA_OBJ: LenientStr = None
    DEC_OBJ: LenientStr = None
    RA_TEL: LenientFloat = None
    DEC_TEL: LenientFloat = None
    ALT_TEL: LenientFloat = None
    AZ_TEL: LenientFloat = None
    AIRMASS: LenientFloat = None
    OBSMODE: LenientStr = None
    FOCUS: LenientInt = None
    ROTATOR: LenientFloat = None
    OBSERVER: LenientStr = None
    IMAGETYP: LenientStr = None
    OBSTYPE: LenientStr = None
    OBJECT: LenientStr = None
    OBS_PROG: LenientStr = Field(None, alias="OBS-PROG")
    NLOOPS: LenientInt = None
    LOOP: LenientInt = None
    FILTER: LenientStr = None
    EXPTIME: LenientFloat = None
    INSTRUME: LenientStr = None
    CCD_TEMP: LenientFloat = Field(None, alias="CCD-TEMP")
    SET_TEMP: LenientStr = Field(None, alias="SET-TEMP")
    XBINNING: LenientInt = None
    YBINNING: LenientInt = None
    READ_MOD: LenientInt = Field(None, alias="READ-MOD")
    GAIN_MOD: LenientInt = Field(None, alias="GAIN-MOD")
    GAIN: LenientFloat = None
    RON: LenientFloat = None
    SUBRASTR: LenientStr = None
    SCALE: LenientFloat = None
    SATURATE: LenientStr = None
    PIERSIDE: LenientInt = None
    FLAT_ERA: LenientInt = None
    ZERO_ERA: LenientInt = None
    DARK_ERA: LenientInt = None
    TEST: LenientInt = None
    CCD_BLCL: LenientStr = Field(None, alias="CCD-BLCL")
    CCD_SCMP: LenientStr = Field(None, alias="CCD-SCMP")
    CCD_PORT: LenientStr = Field(None, alias="CCD-PORT")
    CCD_VSSP: LenientStr = Field(None, alias="CCD-VSSP")
    BZERO: LenientInt = None
    PI: LenientStr = None

    model_config = {"extra": "allow", "populate_by_name": True}


class StorageLocationStatus(BaseModel):
    """Storage status at a specific location (observatory, hub, or cloud)."""
    ready: bool = Field(..., description="Whether the file exists at this location")
    check_needed: bool = Field(..., description="Whether file existence needs verification")
    status: StorageStatusType = Field(..., description="Current storage status")
    expected_time: Optional[datetime] = Field(None, description="Expected completion time for pending operations")

    @classmethod
    def stored(cls) -> "StorageLocationStatus":
        return cls(ready=True, check_needed=False, status=StorageStatusType.STORED)

    @classmethod
    def not_stored(cls) -> "StorageLocationStatus":
        return cls(ready=False, check_needed=False, status=StorageStatusType.NOT_STORED)

    @classmethod
    def storing(cls) -> "StorageLocationStatus":
        return cls(ready=False, check_needed=False, status=StorageStatusType.STORING)

    @classmethod
    def scheduled(cls) -> "StorageLocationStatus":
        return cls(ready=False, check_needed=False, status=StorageStatusType.SCHEDULED)

    @classmethod
    def on_demand(cls) -> "StorageLocationStatus":
        return cls(ready=False, check_needed=False, status=StorageStatusType.ON_DEMAND)


class StorageStatus(BaseModel):
    """Aggregated storage status across all storage locations."""
    observatory: StorageLocationStatus = Field(..., description="Observatory storage status")
    hub: StorageLocationStatus = Field(..., description="Hub storage status")
    cloud: StorageLocationStatus = Field(..., description="Cloud storage status")

    @classmethod
    def on_arrival(cls) -> "StorageStatus":
        """Initial status for a file that just arrived at the observatory."""
        return cls(
            observatory=StorageLocationStatus.stored(),
            hub=StorageLocationStatus.stored(),
            cloud=StorageLocationStatus.not_stored(),
        )


class FITSFile(BaseModel):
    """FITS file model with header metadata and storage status.

    Plain data contract shared between producers (e.g. sroca) and the OcaDB
    API. Persistence-layer concerns (Beanie Document, indexes, DB-only
    fields) belong in a local subclass on the consumer side, not here.
    """

    # Core identification
    filename: str = Field(..., description="FITS filename")
    file_class: FileClassification = Field(..., description="File classification type")
    path: Optional[Path] = Field(None, description="Path to the file")

    # File metadata
    filesize: Optional[int] = Field(None, description="File size in bytes")
    mtime: Optional[datetime] = Field(None, description="Source file modification time (UTC preferred)")
    digest: Optional[DigestStr] = None

    # Relations
    observation_id: Optional[str] = Field(None, description="Parent observation reference")
    obs_name: str = Field(..., description="Parent observation name")

    source_filenames: List[str] = Field(
        default_factory=list,
        description="Source file references (by filename)"
    )

    # FITS metadata
    fits_header: Optional[FitsHeader] = Field(None, description="Complete FITS header")

    # Storage tracking
    file_status: StorageStatus = Field(..., description="Storage status across all locations")

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record creation time"
    )
    updated_at: Optional[datetime] = Field(None, description="Last update time")

    # Flexible metadata container
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Observation metadata (quality checks, processing info, etc.)"
    )

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict for the OcaDB API."""
        return self.model_dump(mode="json", by_alias=True, exclude={"created_at", "updated_at"})
