import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from datamodels.optics import (
    DARK,
    UNDEFINED,
    Active,
    CheckResult,
    Collision,
    ConfigError,
    ConformanceSuite,
    ConformanceVector,
    CoreFunction,
    DetectorPaths,
    EdgeRef,
    GoalSpec,
    Invalid,
    OpticalComponentSpec,
    OpticsCompiled,
    OpticsEdges,
    PortOwner,
    PositionsSpec,
    Route,
    RouteKey,
    Conflict,
    SeesRecord,
    SelectorState,
    Settable,
    TelescopeCompiled,
    TelescopeOpticsSpec,
    Verdict,
    light_family,
    light_state,
)
from datamodels.optics.schema import DEFAULT_OUT_DIR, json_schemas, render

EXAMPLE_PATH = Path(__file__).parent.parent / "examples" / "optics_jk15_example.json"
SCHEMAS_DIR = Path(__file__).parent.parent / DEFAULT_OUT_DIR


class TestVocabulary:
    def test_core_functions_are_the_obsplan_verbs(self):
        assert {f.value for f in CoreFunction} == {"object", "snap", "focus", "skyflat", "domeflat", "dark", "zero"}

    def test_light_class_helpers(self):
        assert light_family("sky.science") == "sky"
        assert light_state("sky.science") == "science"
        assert light_family("lamp") == "lamp"
        assert light_state("lamp") is None

    def test_reserved_words_share_the_light_class_shape(self):
        adapter = TypeAdapter(SeesRecord)
        for word in (DARK, UNDEFINED):
            assert adapter.validate_python({"class": word, "terminal": "tertiary"}).light_class == word


class TestPositionsSpec:
    def test_shipped_jk15_shape_round_trips(self):
        raw = {"beso": {"port": 1, "autoslew-name": "ADR6"}, "andor": {"port": 2, "autoslew-name": "ADR10"}}
        spec = PositionsSpec.model_validate(raw)
        assert list(spec) == ["beso", "andor"]
        assert "beso" in spec and spec["beso"].port == 1
        assert spec.model_dump(by_alias=True) == raw

    def test_reserved_symbol_rejected(self):
        with pytest.raises(ValidationError, match="reserved word"):
            PositionsSpec.model_validate({"dark": {"port": 3}})

    def test_symbol_shape_enforced(self):
        with pytest.raises(ValidationError):
            PositionsSpec.model_validate({"ADR6": {"port": 1}})


class TestOpticsEdges:
    def test_passive_edge(self):
        assert OpticsEdges.model_validate({"from": "dome"}).edges() == [EdgeRef(component="dome")]

    def test_upstream_port_edge(self):
        edges = OpticsEdges.model_validate({"from": {"tertiary": "andor"}}).edges()
        assert edges == [EdgeRef(component="tertiary", port="andor", port_owner=PortOwner.UPSTREAM)]

    def test_multiple_live_positions(self):
        edges = OpticsEdges.model_validate({"from": {"pickoff": ["main", "guide"]}}).edges()
        assert [e.port for e in edges] == ["main", "guide"]
        assert {e.port_owner for e in edges} == {PortOwner.UPSTREAM}

    def test_fan_in_selector_owns_its_positions(self):
        spec = OpticsEdges.model_validate({"inputs": {"open": "sky", "flat": "flatscreen"}})
        assert spec.is_fan_in
        assert spec.edges() == [
            EdgeRef(component="sky", port="open", port_owner=PortOwner.SELF),
            EdgeRef(component="flatscreen", port="flat", port_owner=PortOwner.SELF),
        ]

    @pytest.mark.parametrize(
        "raw, match",
        [
            ({}, "exactly one of"),
            ({"from": "a", "inputs": {"x": "b"}}, "exactly one of"),
            ({"from": ["a", "b"]}, "reserved and not implemented"),
            ({"from": {"a": "p", "b": "q"}}, "exactly one upstream"),
            ({"from": {"a": []}}, "must not be empty"),
            ({"inputs": {}}, "at least one input"),
            ({"from": "dark"}, "reserved word"),
            ({"from": {"tertiary": "undefined"}}, "reserved word"),
            ({"from": "a", "colour": "red"}, "Extra inputs are not permitted"),
        ],
    )
    def test_grammar_errors_fail_at_load(self, raw, match):
        with pytest.raises(ValidationError, match=match):
            OpticsEdges.model_validate(raw)

    def test_round_trip_keeps_the_yaml_sugar(self):
        raw = {"from": {"tertiary": "andor"}}
        assert OpticsEdges.model_validate(raw).model_dump(by_alias=True, exclude_none=True) == raw


class TestDetectorPaths:
    def test_dark_is_a_function_name_and_a_light_class(self):
        paths = DetectorPaths.model_validate({"dark": "dark", "zero": "dark"})
        assert paths.alternatives("dark") == [GoalSpec(see=DARK)]

    def test_bare_goal_and_alternatives_normalize(self):
        paths = DetectorPaths.model_validate(
            {
                "object": "sky.science",
                "flat": ["sky.flat", "flatscreen"],
                "dark_strict": [
                    {"see": "dark", "via": {"covercalibrator": "close"}, "when": "sky.science"},
                    {"see": "dark", "via": {"tertiary": "beso"}},
                ],
            }
        )
        assert paths.alternatives("object") == [GoalSpec(see="sky.science")]
        assert [a.see for a in paths.alternatives("flat")] == ["sky.flat", "flatscreen"]
        strict = paths.alternatives("dark_strict")
        assert strict[0].via == {"covercalibrator": "close"} and strict[0].when == "sky.science"
        assert strict[1].via == {"tertiary": "beso"}

    @pytest.mark.parametrize(
        "raw, match",
        [
            ({"object": "undefined"}, "never be 'undefined'"),
            ({"object": {"see": "undefined"}}, "never be 'undefined'"),
            ({"object": []}, "must not be empty"),
            ({"object": {"see": "sky.science", "through": {}}}, "Extra inputs are not permitted"),
        ],
    )
    def test_goal_errors(self, raw, match):
        with pytest.raises(ValidationError, match=match):
            DetectorPaths.model_validate(raw)


@pytest.fixture(scope="module")
def raw():
    return json.loads(EXAMPLE_PATH.read_text())


class TestTelescopeOpticsSpec:

    def test_from_example_file(self, raw):
        spec = TelescopeOpticsSpec.model_validate(raw)
        assert spec.components["tertiary"].positions is not None
        assert "beso" in spec.components["tertiary"].positions
        assert spec.components["dome"].optics.is_fan_in
        assert spec.components["camera"].paths.alternatives("object") == [GoalSpec(see="sky.science")]
        # device fields ride along untouched
        assert spec.components["tertiary"].model_extra == {"device_number": 0}
        assert spec.components["dome"].model_extra == {"domeflat_az": 49.0}

    def test_json_roundtrip(self, raw):
        spec = TelescopeOpticsSpec.model_validate(raw)
        again = TelescopeOpticsSpec.model_validate_json(spec.model_dump_json(by_alias=True, exclude_none=True))
        assert again == spec
        assert json.loads(spec.model_dump_json(by_alias=True, exclude_none=True)) == raw

    def test_reserved_component_name(self):
        with pytest.raises(ValidationError, match="reserved word"):
            TelescopeOpticsSpec.model_validate({"components": {"dark": {"kind": "beamdump"}}})

    def test_presets_must_reference_declared_paths(self, raw):
        bad = {**raw, "presets": {"x": {"camera": "spectroscopy"}}}
        with pytest.raises(ValidationError, match="declares no path 'spectroscopy'"):
            TelescopeOpticsSpec.model_validate(bad)
        bad = {**raw, "presets": {"x": {"beso": "object"}}}
        with pytest.raises(ValidationError, match="unknown detector 'beso'"):
            TelescopeOpticsSpec.model_validate(bad)

    def test_component_without_optics_is_fine(self):
        assert OpticalComponentSpec.model_validate({"kind": "switch", "address": "x"}).optics is None


class TestResults:
    def test_sees_record_uses_class_on_the_wire(self):
        rec = SeesRecord(light_class="dark", terminal="tertiary", via=("covercalibrator",))
        assert rec.model_dump(by_alias=True) == {"class": "dark", "terminal": "tertiary", "via": ("covercalibrator",)}
        assert SeesRecord.model_validate({"class": "sky.science", "terminal": "sky"}).via == ()

    def test_sees_records_are_set_members(self):
        a = SeesRecord(light_class="sky.science", terminal="sky", via=("dome", "covercalibrator"))
        b = SeesRecord.model_validate({"class": "sky.science", "terminal": "sky", "via": ["dome", "covercalibrator"]})
        assert {a, b} == {a}

    def test_verdict_union_discriminates_on_kind(self):
        adapter = TypeAdapter(Verdict)
        assert isinstance(adapter.validate_python({"kind": "active", "see": "sky.science"}), Active)
        settable = adapter.validate_python(
            {"kind": "settable", "see": "dark", "positions": {"tertiary": "beso"}, "moves": {"tertiary": "beso"}}
        )
        assert isinstance(settable, Settable)
        collision = adapter.validate_python(
            {"kind": "collision", "selector": "tertiary", "required": "andor", "held": "beso", "holder": "beso-run", "reason": "M3 held at beso by beso-run"}
        )
        assert isinstance(collision, Collision)
        invalid = adapter.validate_python(
            {"kind": "invalid", "errors": [{"code": "undeclared_port", "message": "tertiary has no port 'nasmyth3'", "component": "derotator"}]}
        )
        assert isinstance(invalid, Invalid) and invalid.errors[0] == ConfigError(
            code="undeclared_port", message="tertiary has no port 'nasmyth3'", component="derotator"
        )
        with pytest.raises(ValidationError):
            adapter.validate_python({"kind": "maybe"})

    def test_check_result_round_trip(self):
        res = CheckResult(detector="camera", function="object", verdict=Active(see="sky.science"))
        assert CheckResult.model_validate_json(res.model_dump_json()) == res


class TestCompiled:
    def test_round_trip(self):
        key_a = RouteKey(detector="camera", function="object", alternative=0)
        key_b = RouteKey(detector="guider_beso", function="object", alternative=0)
        compiled = OpticsCompiled(
            generated_from="sha256:abc",
            generator="ocabox-common 1.5.0",
            telescopes={
                "jk15": TelescopeCompiled(
                    selectors=["dome", "covercalibrator", "tertiary"],
                    detectors=["camera", "guider", "guider_beso"],
                    routes=[
                        Route(detector="camera", function="object", alternative=0, see="sky.science",
                              positions={"dome": "open", "covercalibrator": "open", "tertiary": "andor"}),
                        Route(detector="guider_beso", function="object", alternative=0, see="sky.science",
                              positions={"dome": "open", "covercalibrator": "open", "tertiary": "beso"}),
                    ],
                    conflicts=[
                        Conflict(selector="tertiary", a=key_a, b=key_b, a_requires="andor", b_requires="beso",
                                 reason="camera.object needs tertiary=andor, guider_beso.object needs tertiary=beso"),
                    ],
                )
            },
        )
        assert OpticsCompiled.model_validate_json(compiled.model_dump_json()) == compiled
        assert compiled.schema_version == 1


class TestConformance:
    def test_vector_round_trip(self):
        raw = json.loads(EXAMPLE_PATH.read_text())
        vector = ConformanceVector(
            name="jk15 M3 readback 2 is unmapped",
            description="oca-problems#107: the operator most needs an answer exactly here",
            components=raw["components"],
            state={"tertiary": SelectorState(position=None, raw=2), "covercalibrator": SelectorState(position="open")},
            environment={"sun_alt_deg": -30.0},
            expected_sees={"camera": [SeesRecord(light_class="undefined", terminal="tertiary", via=("derotator", "pickoff", "filterwheel"))]},
        )
        suite = ConformanceSuite(generated_from="ocabox-common 1.5.0", vectors=[vector])
        again = ConformanceSuite.model_validate_json(suite.model_dump_json(by_alias=True))
        assert again == suite
        assert again.vectors[0].state["tertiary"].position is None


class TestJsonSchemaExport:
    def test_committed_schemas_match_a_fresh_export(self):
        fresh = json_schemas()
        committed = {p.stem.removesuffix(".schema"): p for p in SCHEMAS_DIR.glob("*.schema.json")}
        assert set(committed) == set(fresh), "run `uv run datamodels-export-schemas` and commit the result"
        for name, schema in fresh.items():
            assert committed[name].read_text(encoding="utf-8") == render(schema), (
                f"{committed[name]} is stale — run `uv run datamodels-export-schemas` and commit the result"
            )

    def test_wire_names_survive_in_schema(self):
        sees = json_schemas()["SeesRecord"]
        assert set(sees["properties"]) == {"class", "terminal", "via"}
        verdict = json_schemas()["Verdict"]
        assert set(verdict["discriminator"]["mapping"]) == {"active", "settable", "collision", "impossible", "invalid"}


if __name__ == "__main__":
    pytest.main([__file__])
