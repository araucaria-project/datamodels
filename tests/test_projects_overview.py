import json
from datetime import datetime
from pathlib import Path

import pytest

from datamodels.projects_overview import (
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


class TestLightCurve:
    def test_basic_creation(self):
        lc = LightCurve(name="V", display_name="V", status="ongoing")
        assert lc.name == "V"
        assert lc.display_name == "V"
        assert lc.status == Status.ONGOING

    def test_status_optional(self):
        lc = LightCurve(name="V", display_name="V")
        assert lc.status is None

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

    def test_with_lc(self):
        obj = ObjectOverview(
            name="asassn-14cc",
            display_name="asassn-14cc",
            status="ongoing",
            lc={
                "u_s": {"name": "u_s", "display_name": "u_s", "status": "ongoing"},
                "v_s": {"name": "v_s", "display_name": "v_s"},
            },
        )
        assert obj.lc["u_s"].status == Status.ONGOING
        assert obj.lc["v_s"].status is None

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
        assert obj.lc["v_s"].status is None

        fairall9 = project.objects["fairall9"]
        assert fairall9.lc == {}

    def test_serialization_roundtrip(self):
        data = json.loads(EXAMPLE_PATH.read_text())
        overview = ProjectsOverview.model_validate(data)
        dumped = overview.model_dump()
        overview2 = ProjectsOverview.model_validate(dumped)
        assert overview2 == overview

    def test_json_roundtrip(self):
        data = json.loads(EXAMPLE_PATH.read_text())
        overview = ProjectsOverview.model_validate(data)
        json_str = overview.model_dump_json()
        overview2 = ProjectsOverview.model_validate_json(json_str)
        assert overview2.projects["amcvn"].objects["asassn-14cc"].status == Status.ONGOING


if __name__ == "__main__":
    pytest.main([__file__])
