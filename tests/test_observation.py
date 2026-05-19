from datetime import datetime, timezone

import pytest

from datamodels.observation import File, Info, Measurement, Observation


def make_info(**kwargs):
    defaults = {
        "obs_id": "zb08c_1021_34234",
        "date_obs": "2026-05-12T01:23:21.234Z",
        "oca_jd": 1021,
    }
    defaults.update(kwargs)
    return Info(**defaults)


class TestInfo:
    def test_basic_creation(self):
        info = make_info()
        assert info.obs_id == "zb08c_1021_34234"
        assert info.oca_jd == 1021
        assert isinstance(info.date_obs, datetime)

    def test_extra_fields_allowed(self):
        info = make_info(field_name="Oph_V", uobi="213eq2")
        assert info.field_name == "Oph_V"  # type: ignore[attr-defined]
        assert info.uobi == "213eq2"  # type: ignore[attr-defined]

    def test_date_obs_parsing(self):
        info = make_info(date_obs="2026-05-12T01:23:21.234Z")
        assert info.date_obs.year == 2026
        assert info.date_obs.month == 5
        assert info.date_obs.day == 12


class TestMeasurement:
    def test_basic_creation(self):
        m = Measurement(category="wcs")
        assert m.category == "wcs"
        assert m.result is None

    def test_result_any_type(self):
        m_scalar = Measurement(category="fwhm", result=3.14)
        assert m_scalar.result == 3.14

        m_dict = Measurement(category="pointing_error", result={"dx": 11.4, "dy": 23.8})
        assert m_dict.result == {"dx": 11.4, "dy": 23.8}

        m_list = Measurement(category="qmap", result=[1, 2, 3])
        assert m_list.result == [1, 2, 3]

    def test_extra_fields_allowed(self):
        m = Measurement(category="fwhm", method="gaussian", pxl_dx=16)
        assert m.method == "gaussian"  # type: ignore[attr-defined]
        assert m.pxl_dx == 16  # type: ignore[attr-defined]


class TestFile:
    def test_basic_creation(self):
        f = File(category="raw")
        assert f.category == "raw"
        assert f.file_name is None
        assert f.header is None
        assert f.measurements == []

    def test_with_measurements(self):
        m = Measurement(category="fwhm", result=3.5)
        f = File(category="raw", measurements=[m])
        assert len(f.measurements) == 1
        assert f.measurements[0].category == "fwhm"

    def test_with_header(self):
        f = File(category="raw", header={"EXPTIME": 120, "FILTER": "V"})
        assert f.header == {"EXPTIME": 120, "FILTER": "V"}

    def test_extra_fields_allowed(self):
        f = File(category="master_z", file_name="master_z.fits", min=0.0, max=65535.0)
        assert f.min == 0.0  # type: ignore[attr-defined]
        assert f.max == 65535.0  # type: ignore[attr-defined]


class TestObservation:
    def test_basic_creation(self):
        obs = Observation(info=make_info())
        assert obs.info.obs_id == "zb08c_1021_34234"
        assert obs.quality_checks == {}
        assert obs.objects == {}
        assert obs.files == []
        assert obs.measurements == []

    def test_full_observation(self):
        info = make_info(field_name="Oph_V", uobi="213eq2")
        files = [
            File(category="raw", measurements=[Measurement(category="fwhm", result=3.5)]),
            File(category="zdf"),
            File(category="master_z", file_name="master_z.fits"),
        ]
        measurements = [
            Measurement(
                category="wcs",
                result=(123.56, -32.05),
                number_of_stars_used=450,
            ),
            Measurement(
                category="fwhm",
                method="gaussian",
                result={"dx": 12.4, "dy": 23.8},
            ),
            Measurement(category="pointing_error", result={"dx": 11.4, "dy": 23.8}),
            Measurement(category="photometry", result={"V": 11.4, "V_err": 0.2}),
        ]
        obs = Observation(
            info=info,
            quality_checks={"passed": True},
            files=files,
            measurements=measurements,
        )

        assert obs.info.field_name == "Oph_V"  # type: ignore[attr-defined]
        assert len(obs.files) == 3
        assert obs.files[0].category == "raw"
        assert len(obs.measurements) == 4
        assert obs.measurements[1].method == "gaussian"  # type: ignore[attr-defined]
        assert obs.quality_checks == {"passed": True}

    def test_serialization_roundtrip(self):
        obs = Observation(
            info=make_info(),
            files=[File(category="raw")],
            measurements=[Measurement(category="wcs", result={"ra": 123.56, "dec": -32.05})],
        )
        data = obs.model_dump()
        obs2 = Observation.model_validate(data)
        assert obs2.info.obs_id == obs.info.obs_id
        assert obs2.measurements[0].result == {"ra": 123.56, "dec": -32.05}

    def test_json_roundtrip(self):
        obs = Observation(info=make_info())
        json_str = obs.model_dump_json()
        obs2 = Observation.model_validate_json(json_str)
        assert obs2.info.oca_jd == 1021
