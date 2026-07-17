from datamodels.fits import (
    FileClassification,
    FITSFile,
    FitsHeader,
    StorageLocationStatus,
    StorageStatus,
    StorageStatusType,
)


class TestFitsHeaderCoercion:
    def test_int_fields_coerce_from_string(self):
        header = FitsHeader.model_validate({"BITPIX": "-32", "NAXIS": "2", "XBINNING": "1"})
        assert header.BITPIX == -32
        assert header.NAXIS == 2
        assert header.XBINNING == 1

    def test_int_field_invalid_string_becomes_none(self):
        header = FitsHeader.model_validate({"BITPIX": ""})
        assert header.BITPIX is None

    def test_float_fields_coerce_from_string(self):
        # Regression coverage: these fields previously had no coercion at all
        # (only ROTATOR/RA/DEC were hand-listed), so a blank/string value from
        # a real FITS header would raise instead of validating.
        header = FitsHeader.model_validate({
            "JD": "2460901.123",
            "OBS-LAT": "-24.59806",
            "OBS-LONG": "-70.19638",
            "RA_TEL": "123.4",
            "DEC_TEL": "-32.1",
            "ALT_TEL": "60.86",
            "AZ_TEL": "290.03",
            "AIRMASS": "1.14",
            "EXPTIME": "30.0",
            "CCD-TEMP": "-59.13",
            "GAIN": "0.97",
            "RON": "10.4",
            "SCALE": "0.5",
        })
        assert header.JD == 2460901.123
        assert header.OBS_LAT == -24.59806
        assert header.OBS_LONG == -70.19638
        assert header.RA_TEL == 123.4
        assert header.DEC_TEL == -32.1
        assert header.ALT_TEL == 60.86
        assert header.AZ_TEL == 290.03
        assert header.AIRMASS == 1.14
        assert header.EXPTIME == 30.0
        assert header.CCD_TEMP == -59.13
        assert header.GAIN == 0.97
        assert header.RON == 10.4
        assert header.SCALE == 0.5

    def test_float_field_invalid_string_becomes_none(self):
        header = FitsHeader.model_validate({"AIRMASS": ""})
        assert header.AIRMASS is None

    def test_str_fields_coerce_from_non_string(self):
        header = FitsHeader.model_validate({"OBJECT": 123, "FILTER": 4.5})
        assert header.OBJECT == "123"
        assert header.FILTER == "4.5"

    def test_native_types_pass_through_unchanged(self):
        header = FitsHeader.model_validate({
            "SIMPLE": True, "BITPIX": -32, "JD": 2460901.5, "OBJECT": "M31",
        })
        assert header.SIMPLE is True
        assert header.BITPIX == -32
        assert header.JD == 2460901.5
        assert header.OBJECT == "M31"

    def test_hyphenated_alias_fields_accepted(self):
        header = FitsHeader.model_validate({"DATE-OBS": "2026-05-12T01:23:21"})
        assert header.DATE_OBS == "2026-05-12T01:23:21"

    def test_populate_by_name_accepts_field_name_too(self):
        header = FitsHeader(OBS_LAT=-24.6)
        assert header.OBS_LAT == -24.6

    def test_extra_fields_allowed(self):
        header = FitsHeader.model_validate({"SOME_NEW_KEYWORD": "value"})
        assert header.SOME_NEW_KEYWORD == "value"  # type: ignore[attr-defined]

    def test_pi_field(self):
        header = FitsHeader.model_validate({"PI": "Smith"})
        assert header.PI == "Smith"


class TestFileClassification:
    def test_from_suffix_zdf(self):
        assert FileClassification.from_suffix("zdf") == FileClassification.ZDF

    def test_from_suffix_master(self):
        assert FileClassification.from_suffix("master_zero") == FileClassification.MASTER

    def test_from_suffix_none_defaults_to_raw(self):
        assert FileClassification.from_suffix(None) == FileClassification.RAW

    def test_zero_member_exists(self):
        assert FileClassification.ZERO.value == "zero"


class TestStorageStatus:
    def test_on_arrival(self):
        status = StorageStatus.on_arrival()
        assert status.observatory.status == StorageStatusType.STORED
        assert status.hub.status == StorageStatusType.STORED
        assert status.cloud.status == StorageStatusType.NOT_STORED

    def test_location_status_factories(self):
        assert StorageLocationStatus.storing().status == StorageStatusType.STORING
        assert StorageLocationStatus.scheduled().status == StorageStatusType.SCHEDULED


class TestFITSFile:
    def _make(self, **overrides):
        defaults = dict(
            filename="zb08c_0901_63900.fits",
            obs_name="zb08c_0901_63900",
            file_class=FileClassification.RAW,
            file_status=StorageStatus.on_arrival(),
        )
        defaults.update(overrides)
        return FITSFile(**defaults)

    def test_basic_creation(self):
        f = self._make()
        assert f.filename == "zb08c_0901_63900.fits"
        assert f.source_filenames == []
        assert f.fits_header is None

    def test_to_dict_excludes_path_and_timestamps(self):
        f = self._make(path="/fits/zb08c_0901_63900.fits")
        data = f.to_dict()
        assert "path" not in data
        assert "created_at" not in data
        assert "updated_at" not in data
        assert data["filename"] == "zb08c_0901_63900.fits"

    def test_to_dict_uses_aliases_for_header(self):
        f = self._make(fits_header=FitsHeader.model_validate({"OBS-LAT": "-24.6"}))
        data = f.to_dict()
        assert data["fits_header"]["OBS-LAT"] == -24.6
