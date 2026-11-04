import json
from datetime import datetime
from pathlib import Path

import pytest

from datamodels.projects_overview import (
    LcInfo,
    LcMeasurement,
    LcModel,
    LightCurve,
    ObjectOverview,
    ProjectOverview,
    ProjectsOverview,
    Status,
)

EXAMPLE_PATH = Path(__file__).parent.parent / "examples" / "projects_overview_example.json"


class TestStatus:
    def test_values(self):
        assert Status.ONGOING == "ongoing"
        assert Status.PAUSED == "paused"
        assert Status.HALTED == "halted"
        assert Status.WAITING == "waiting"
        assert Status.FINISHED == "finished"
        assert Status.OMITTED == "omitted"


class TestLightCurve:
    def test_basic_creation(self):
        lc = LightCurve(
            name="V",
            display_name="V",
            status="ongoing",
            file_name="asassn-14cc_zb08_V_diff_ap_lc.png",
        )
        assert lc.name == "V"
        assert lc.display_name == "V"
        assert lc.status == Status.ONGOING
        assert lc.file_name == "asassn-14cc_zb08_V_diff_ap_lc.png"

    def test_status_optional(self):
        lc = LightCurve(name="V", display_name="V")
        assert lc.status is None

    def test_file_name_optional(self):
        lc = LightCurve(name="V", display_name="V")
        assert lc.file_name is None

    def test_status_omitted(self):
        lc = LightCurve(name="V", display_name="V", status="omitted")
        assert lc.status == Status.OMITTED

    def test_name_required(self):
        with pytest.raises(ValueError):
            LightCurve(display_name="V")

    def test_extra_fields_allowed(self):
        lc = LightCurve(name="V", display_name="V", n_obs=12)
        assert lc.n_obs == 12  # type: ignore[attr-defined]


class TestObjectOverview:
    def test_basic_creation(self):
        obj = ObjectOverview(name="asassn-14cc", display_name="asassn-14cc", status="ongoing")
        assert obj.name == "asassn-14cc"
        assert obj.display_name == "asassn-14cc"
        assert obj.status == Status.ONGOING
        assert obj.lc == {}

    def test_status_required(self):
        with pytest.raises(ValueError):
            ObjectOverview(name="fairall9", display_name="fairall9")

    def test_name_required(self):
        with pytest.raises(ValueError):
            ObjectOverview(display_name="fairall9", status="halted")

    def test_status_omitted(self):
        obj = ObjectOverview(name="ngc1566", display_name="ngc1566", status="omitted")
        assert obj.status == Status.OMITTED
        assert obj.lc == {}

    def test_with_lc(self):
        obj = ObjectOverview(
            name="asassn-14cc",
            display_name="asassn-14cc",
            status="ongoing",
            lc={
                "u_s": {
                    "name": "u_s",
                    "display_name": "u_s",
                    "status": "ongoing",
                    "file_name": "asassn-14cc_zb08_u_s_diff_ap_lc.png",
                },
                "v_s": {"name": "v_s", "display_name": "v_s"},
            },
        )
        assert obj.lc["u_s"].status == Status.ONGOING
        assert obj.lc["u_s"].file_name == "asassn-14cc_zb08_u_s_diff_ap_lc.png"
        assert obj.lc["v_s"].status is None
        assert obj.lc["v_s"].file_name is None

    def test_extra_fields_allowed(self):
        obj = ObjectOverview(name="fairall9", display_name="fairall9", status="waiting", ra=10.5)
        assert obj.ra == 10.5  # type: ignore[attr-defined]


class TestProjectOverview:
    def test_basic_creation(self):
        project = ProjectOverview(
            name="amcvn",
            display_name="Project:amcvn PI:kbakowska",
            pi="kbakowska",
            sciprog="amcvn",
            status="ongoing",
        )
        assert project.pi == "kbakowska"
        assert project.objects == {}

    def test_pi_and_sciprog_optional(self):
        project = ProjectOverview(name="amcvn", display_name="Project:amcvn", status="ongoing")
        assert project.pi is None
        assert project.sciprog is None

    def test_status_required(self):
        with pytest.raises(ValueError):
            ProjectOverview(name="amcvn", display_name="Project:amcvn")

    def test_name_required(self):
        with pytest.raises(ValueError):
            ProjectOverview(display_name="Project:amcvn", status="ongoing")

    def test_with_objects(self):
        project = ProjectOverview(
            name="amcvn",
            display_name="Project:amcvn PI:kbakowska",
            pi="kbakowska",
            sciprog="amcvn",
            status="ongoing",
            objects={
                "asassn-14cc": {"name": "asassn-14cc", "display_name": "asassn-14cc", "status": "ongoing"}
            },
        )
        assert project.objects["asassn-14cc"].status == Status.ONGOING


class TestProjectsOverview:
    def test_basic_creation(self):
        overview = ProjectsOverview(
            processed_date="2026-07-28T21:05:12.123456+00:00",
            processed_folder="0987",
            telescope="zb08",
        )
        assert isinstance(overview.processed_date, datetime)
        assert overview.processed_folder == "0987"
        assert overview.telescope == "zb08"
        assert overview.projects == {}

    def test_from_example_file(self):
        data = json.loads(EXAMPLE_PATH.read_text())
        overview = ProjectsOverview.model_validate(data)

        project = overview.projects["amcvn"]
        assert project.pi == "kbakowska"

        obj = project.objects["asassn-14cc"]
        assert obj.status == Status.ONGOING
        assert obj.lc["u_s"].status == Status.ONGOING
        assert obj.lc["u_s"].file_name == "asassn-14cc_zb08_u_s_diff_ap_lc.png"
        assert obj.lc["v_s"].status is None
        assert obj.lc["v_s"].file_name is None
        assert obj.lc["i_s"].status == Status.OMITTED
        assert obj.lc["i_s"].file_name is None

        fairall9 = project.objects["fairall9"]
        assert fairall9.lc == {}

        ngc1566 = project.objects["ngc1566"]
        assert ngc1566.status == Status.OMITTED
        assert ngc1566.lc == {}

    def test_serialization_roundtrip(self):
        data = json.loads(EXAMPLE_PATH.read_text())
        overview = ProjectsOverview.model_validate(data)
        dumped = overview.model_dump()
        overview2 = ProjectsOverview.model_validate(dumped)
        assert overview2 == overview

    def test_file_name_survives_roundtrip(self):
        data = json.loads(EXAMPLE_PATH.read_text())
        overview = ProjectsOverview.model_validate(data)
        overview2 = ProjectsOverview.model_validate_json(overview.model_dump_json())
        assert overview2 == overview
        lc = overview2.projects["amcvn"].objects["asassn-14cc"].lc["u_s"]
        assert lc.file_name == "asassn-14cc_zb08_u_s_diff_ap_lc.png"

    def test_json_roundtrip(self):
        data = json.loads(EXAMPLE_PATH.read_text())
        overview = ProjectsOverview.model_validate(data)
        json_str = overview.model_dump_json()
        overview2 = ProjectsOverview.model_validate_json(json_str)
        assert overview2.projects["amcvn"].objects["asassn-14cc"].status == Status.ONGOING


def _example_lc_data() -> dict:
    """The light curve with full data (info / measurements / models) from the example file."""
    data = json.loads(EXAMPLE_PATH.read_text())
    return data["projects"]["binaries"]["objects"]["cs_eri"]["lc"]["r"]


class TestLcInfo:
    def test_basic_creation(self):
        info = LcInfo(
            telescope="zb08",
            object="cs_eri",
            filter="r",
            prefix="ap-diff",
            lc_type="diff",
            method="ap",
            mag_type="std",
            period=0.311331,
            hjd0=2460000.0,
            re_rendered="2026-11-04T14:12:05Z",
        )
        assert info.object == "cs_eri"
        assert info.lc_type == "diff"
        assert info.method == "ap"
        assert info.mag_type == "std"
        assert isinstance(info.re_rendered, datetime)
        assert info.re_rendered.tzinfo is not None

    def test_optional_fields(self):
        info = LcInfo(telescope="zb08", object="cs_eri", filter="r")
        assert info.prefix is None
        assert info.lc_type is None
        assert info.method is None
        assert info.mag_type is None
        assert info.period is None
        assert info.hjd0 is None
        assert info.re_rendered is None

    def test_required_fields(self):
        with pytest.raises(ValueError):
            LcInfo(object="cs_eri", filter="r")
        with pytest.raises(ValueError):
            LcInfo(telescope="zb08", filter="r")
        with pytest.raises(ValueError):
            LcInfo(telescope="zb08", object="cs_eri")

    def test_extra_fields_allowed(self):
        info = LcInfo(telescope="zb08", object="cs_eri", filter="r", instrument="zb08c")
        assert info.instrument == "zb08c"  # type: ignore[attr-defined]


class TestLcMeasurement:
    def test_basic_creation(self):
        m = LcMeasurement(category="snr", result={"median": 412, "min": 95, "max": 780})
        assert m.category == "snr"
        assert m.result["median"] == 412

    def test_result_optional(self):
        assert LcMeasurement(category="snr").result is None

    def test_category_required(self):
        with pytest.raises(ValueError):
            LcMeasurement(result=1)

    def test_extra_fields_allowed(self):
        m = LcMeasurement(category="snr", unit="")
        assert m.unit == ""  # type: ignore[attr-defined]


class TestLcModel:
    def test_basic_creation(self):
        m = LcModel(category="GaussianProcessLightCurve", result={"reliable": True})
        assert m.category == "GaussianProcessLightCurve"
        assert m.result["reliable"] is True

    def test_result_optional(self):
        assert LcModel(category="GaussianProcessLightCurve").result is None

    def test_category_required(self):
        with pytest.raises(ValueError):
            LcModel(result={})

    def test_extra_fields_allowed(self):
        m = LcModel(category="GaussianProcessLightCurve", version=1)
        assert m.version == 1  # type: ignore[attr-defined]


class TestLightCurveData:
    def test_old_style_has_empty_data(self):
        lc = LightCurve(name="V", display_name="V")
        assert lc.info is None
        assert lc.measurements == []
        assert lc.models == []

    def test_from_example_file(self):
        lc = LightCurve.model_validate(_example_lc_data())
        assert lc.name == "r"
        assert lc.status == Status.ONGOING
        assert lc.file_name == "cs_eri_zb08c_r_ap-diff.lc.png"
        assert lc.info.object == "cs_eri"
        assert lc.info.filter == lc.name
        assert lc.info.prefix == "ap-diff"
        assert lc.info.lc_type == "diff"
        assert lc.info.method == "ap"
        assert lc.info.mag_type == "std"
        assert [m.category for m in lc.measurements] == ["snr", "std", "points", "compare_stars"]
        assert [m.category for m in lc.models] == ["GaussianProcessLightCurve"]

    def test_model_result(self):
        lc = LightCurve.model_validate(_example_lc_data())
        result = lc.models[0].result
        assert result["reliable"] is True
        assert set(result["stats"]) == {"max", "mean", "min", "amplitude"}
        assert set(result["params"]) == {"constant", "length_scale", "noise_level"}
        curve = result["curve"]
        assert curve[0][0] == 0.0 and curve[-1][0] == 1.0
        assert curve[0][1] == curve[-1][1]
        assert all(len(point) == 2 for point in curve)

    def test_get_measurement(self):
        import asyncio
        lc = LightCurve.model_validate(_example_lc_data())
        snr = asyncio.run(lc.get_measurement("snr"))
        assert snr.result == {"median": 412, "min": 95, "max": 780}
        compare = asyncio.run(lc.get_measurement("compare_stars"))
        assert compare.result["quantity"] == 12
        assert asyncio.run(lc.get_measurement("missing")) is None

    def test_get_model(self):
        import asyncio
        lc = LightCurve.model_validate(_example_lc_data())
        model = asyncio.run(lc.get_model("GaussianProcessLightCurve"))
        assert model.result["n_points"] == 199
        assert asyncio.run(lc.get_model("missing")) is None

    def test_json_roundtrip(self):
        lc = LightCurve.model_validate(_example_lc_data())
        lc2 = LightCurve.model_validate_json(lc.model_dump_json())
        assert lc2 == lc

    def test_dump_matches_example(self):
        data = _example_lc_data()
        dumped = LightCurve.model_validate(data).model_dump(mode="json")
        assert dumped["measurements"] == data["measurements"]
        assert dumped["models"] == data["models"]
        assert dumped["info"]["re_rendered"] == data["info"]["re_rendered"]

    def test_in_projects_overview(self):
        data = json.loads(EXAMPLE_PATH.read_text())
        overview = ProjectsOverview.model_validate(data)
        lc = overview.projects["binaries"].objects["cs_eri"].lc["r"]
        assert lc.info.telescope == overview.telescope
        assert lc.models[0].category == "GaussianProcessLightCurve"
        old = overview.projects["amcvn"].objects["asassn-14cc"].lc["u_s"]
        assert old.info is None
        assert old.measurements == []
        assert old.models == []


if __name__ == "__main__":
    pytest.main([__file__])
