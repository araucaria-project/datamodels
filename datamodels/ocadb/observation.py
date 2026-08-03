"""Shared Observation data-transport model.

This is a plain pydantic model only — no ODM (Beanie/Mongo) dependencies.
Consumers that need persistence (e.g. ocadb) should subclass ObservationBase
together with their own Document base class locally, rather than extending
this module with storage-specific behavior.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field, model_validator

from datamodels.ocadb.fits import FileClassification, FitsHeader


class ObservationBase(BaseModel):
    """Astronomical observation with FITS header and metadata.

    Plain data contract shared between producers (e.g. sroca) and the OcaDB
    API. Persistence-layer concerns (Beanie Document, indexes, linked
    FITSFile documents, DB-only event hooks) belong in a local subclass on
    the consumer side, not here.
    """

    # Core identification
    obs_name: str = Field(..., description="Observation name")
    file_name: Optional[str] = Field(None, description="FITS filename")
    object_id: Optional[str] = Field(None, description="Reference to observed Object document")
    canonized_object_name: Optional[str] = Field(None, description="Canonized astronomical object name")
    obs_tags: Set[str] = Field(default_factory=set, description="Set of observation tags")

    # files support
    filetypes: Set[FileClassification] = Field(default_factory=set)
    source_files: Set[str] = Field(default_factory=set)

    # Raw FITS header (flat structure, exact field names)
    fits_header: FitsHeader = Field(..., description="Complete FITS header")

    # Flexible metadata container (quality checks, processing info, etc.)
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Observation metadata (quality checks, processing info, etc.)"
    )

    # Access control
    access_tags: List[str] = Field(
        default_factory=list, description="tags for document access control", exclude=True
    )  # exclude field from json dump

    # observation date
    date_obs: datetime = Field(
        default_factory=datetime.utcnow, description="internal ISO Date to datetime conversion", exclude=True
    )  # exclude field from json dump
    oca_jd: Optional[int] = Field(None, description="OCM representation of observation date")

    # Processing timestamps
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Record creation time")
    updated_at: Optional[datetime] = Field(None, description="Last update time")

    def store_metadata(self, metadata: dict):
        self.metadata = metadata
        if self.metadata:
            self.obs_tags.add("metadata")
        else:
            self.obs_tags.discard("metadata")

    def store_fits_header(self, fits_header):
        self.fits_header = fits_header

    @model_validator(mode='after')
    def store_oca_jd(self):
        # workaround - pydantic bug?? similar to https://github.com/google/adk-python/issues/3633
        if isinstance(self.fits_header, dict):
            self.fits_header = FitsHeader.model_validate(self.fits_header)
        if self.fits_header.JD is not None:
            self.oca_jd = int(self.fits_header.JD) % 10000
        return self
