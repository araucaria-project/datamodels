"""Shared FITS-file / OcaDB data-transport models.

These are plain pydantic models only — no ODM (Beanie/Mongo) or web-framework
(FastAPI) dependencies. Consumers that need persistence (e.g. ocadb) should
subclass FITSFile together with their own Document base class locally, rather
than extending this module with storage-specific behavior.
"""
import types
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional, Union, get_args, get_origin

from pydantic import BaseModel, Field, model_validator


class StorageStatusType(str, Enum):
    """Status types for file storage operations."""
    NOT_STORED = "not_stored"
    DELETED = "deleted"
    STORED = "stored"
    CORRUPTED = "corrupted"
    REQUESTED = "requested"
    SCHEDULED = "scheduled"
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


def _unwrap_optional(annotation):
    """Strip an Optional[...] / X | None wrapper down to the inner type."""
    origin = get_origin(annotation)
    if origin is Union or origin is getattr(types, "UnionType", None):
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


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
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    return value


_COERCERS = {
    int: _coerce_int,
    float: _coerce_float,
    str: _coerce_str,
}


class FitsHeader(BaseModel):
    """Direct mapping of FITS header keywords (exact field names).

    Values coming from a raw FITS header are frequently the "wrong" type
    for their field (e.g. a numeric keyword serialized as a string). Rather
    than hand-maintaining separate lists of field names per target type,
    `_coerce_by_annotation` below coerces every field generically based on
    its own type annotation, so a field can never fall out of sync with its
    own declared type.
    """
    SIMPLE: Optional[bool] = None
    BITPIX: Optional[int] = None
    NAXIS: Optional[int] = None
    NAXIS1: Optional[int] = None
    NAXIS2: Optional[int] = None
    OCASTD: Optional[str] = None
    OBSERVAT: Optional[str] = None
    OBS_LAT: Optional[float] = Field(None, alias="OBS-LAT")
    OBS_LONG: Optional[float] = Field(None, alias="OBS-LONG")
    OBS_ELEV: Optional[int] = Field(None, alias="OBS-ELEV")
    ORIGIN: Optional[str] = None
    TELESCOP: Optional[str] = None
    DATE_OBS: Optional[str] = Field(None, alias="DATE-OBS")
    JD: Optional[float] = None
    RA: Optional[float] = None
    DEC: Optional[float] = None
    EQUINOX: Optional[str] = None
    RA_OBJ: Optional[str] = None
    DEC_OBJ: Optional[str] = None
    RA_TEL: Optional[float] = None
    DEC_TEL: Optional[float] = None
    ALT_TEL: Optional[float] = None
    AZ_TEL: Optional[float] = None
    AIRMASS: Optional[float] = None
    OBSMODE: Optional[str] = None
    FOCUS: Optional[int] = None
    ROTATOR: Optional[float] = None
    OBSERVER: Optional[str] = None
    IMAGETYP: Optional[str] = None
    OBSTYPE: Optional[str] = None
    OBJECT: Optional[str] = None
    OBS_PROG: Optional[str] = Field(None, alias="OBS-PROG")
    NLOOPS: Optional[int] = None
    LOOP: Optional[int] = None
    FILTER: Optional[str] = None
    EXPTIME: Optional[float] = None
    INSTRUME: Optional[str] = None
    CCD_TEMP: Optional[float] = Field(None, alias="CCD-TEMP")
    SET_TEMP: Optional[str] = Field(None, alias="SET-TEMP")
    XBINNING: Optional[int] = None
    YBINNING: Optional[int] = None
    READ_MOD: Optional[int] = Field(None, alias="READ-MOD")
    GAIN_MOD: Optional[int] = Field(None, alias="GAIN-MOD")
    GAIN: Optional[float] = None
    RON: Optional[float] = None
    SUBRASTR: Optional[str] = None
    SCALE: Optional[float] = None
    SATURATE: Optional[str] = None
    PIERSIDE: Optional[int] = None
    FLAT_ERA: Optional[int] = None
    ZERO_ERA: Optional[int] = None
    DARK_ERA: Optional[int] = None
    TEST: Optional[int] = None
    CCD_BLCL: Optional[str] = Field(None, alias="CCD-BLCL")
    CCD_SCMP: Optional[str] = Field(None, alias="CCD-SCMP")
    CCD_PORT: Optional[str] = Field(None, alias="CCD-PORT")
    CCD_VSSP: Optional[str] = Field(None, alias="CCD-VSSP")
    BZERO: Optional[int] = None
    PI: Optional[str] = None

    model_config = {"extra": "allow", "populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _coerce_by_annotation(cls, data):
        if not isinstance(data, dict):
            return data
        coerced = dict(data)
        for name, field in cls.model_fields.items():
            key = name
            if field.alias is not None and field.alias in coerced:
                key = field.alias
            elif name not in coerced:
                continue
            value = coerced[key]
            if value is None:
                continue
            target = _unwrap_optional(field.annotation)
            coercer = _COERCERS.get(target)
            if coercer is not None:
                coerced[key] = coercer(value)
        return coerced


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
        return self.model_dump(mode="json", by_alias=True, exclude={"path", "created_at", "updated_at"})
