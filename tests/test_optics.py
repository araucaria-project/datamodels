import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from datamodels.optics import (
    Active,
    CheckResult,
    Collision,
    ConfigError,
    Conflict,
    ConformanceSuite,
    ConformanceVector,
    CoreFunction,
    DARK,
    DetectorPaths,
    DisplayHint,
    EdgeRef,
    Environment,
    GoalSpec,
    Invalid,
    light_family,
    light_state,
    OpticalComponentSpec,
    OpticsCompiled,
    OpticsEdges,
    PortOwner,
    PositionSpec,
    PositionsSpec,
    Route,
    RouteKey,
    SeesRecord,
    SelectorState,
    Settable,
    split_state_key,
    state_key,
    TelescopeCompiled,
    TelescopeOpticsSpec,
    UNDEFINED,
    Verdict,
    VerdictKind,
)
from datamodels.optics.schema import DEFAULT_OUT_DIR, EXPORTED, json_schemas, render
from jsonschema import Draft202012Validator

EXAMPLE_PATH = Path(__file__).parent.parent / "examples" / "optics_jk15_example.json"
SCHEMAS_DIR = Path(__file__).parent.parent / DEFAULT_OUT_DIR


class TestVocabulary:
    def test_core_functions_are_the_obsplan_verbs(self):
        assert {f.value for f in CoreFunction} == {"object", "snap", "focus", "flat", "skyflat", "domeflat", "arc", "dark", "zero"}

    def test_light_class_helpers(self):
        assert light_family("sky.science") == "sky"
        assert light_state("sky.science") == "science"
        assert light_family("lamp") == "lamp"
        assert light_state("lamp") is None

    def test_state_key_names_a_selector_or_one_aspect_of_it(self):
        assert state_key("covercalibrator", "calibrator") == "covercalibrator.calibrator"
        assert state_key("tertiary") == "tertiary"
        assert split_state_key("covercalibrator.calibrator") == ("covercalibrator", "calibrator")
        assert split_state_key("tertiary") == ("tertiary", None)
        adapter = TypeAdapter(Settable)
        settable = adapter.validate_python(
            {"kind": "settable", "see": "sky.science", "positions": {"covercalibrator": "open", "covercalibrator.calibrator": "off"},
             "moves": {"covercalibrator.calibrator": "off"}}
        )
        assert settable.moves == {"covercalibrator.calibrator": "off"}
        with pytest.raises(ValidationError):
            adapter.validate_python({"kind": "settable", "see": "dark", "positions": {"a.b.c": "x"}, "moves": {}})

    def test_reserved_words_share_the_light_class_shape(self):
        adapter = TypeAdapter(SeesRecord)
        for word in (DARK, UNDEFINED):
            assert adapter.validate_python({"class": word, "terminal": "tertiary", "via": []}).light_class == word


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
            ({"from": {"a": "p", "b": "q"}}, "at most 1 item"),
            ({"from": {"a": []}}, "at least 1 item"),
            ({"inputs": {}}, "at least 1 item"),
            ({"from": "dark"}, "reserved word"),
            ({"from": {"tertiary": "undefined"}}, "reserved word"),
            ({"from": {"dark": "p"}}, "reserved word"),
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
            ({"object": []}, "at least 1 item"),
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

    def test_presets_are_shape_checked_only(self, raw):
        # cross-component truth (does the detector exist, does it declare the path) is the solver's
        spec = TelescopeOpticsSpec.model_validate({**raw, "presets": {"x": {"beso": "spectroscopy"}}})
        assert spec.presets == {"x": {"beso": "spectroscopy"}}
        with pytest.raises(ValidationError):
            TelescopeOpticsSpec.model_validate({**raw, "presets": {"x": {"dark": "object"}}})

    def test_component_without_optics_is_fine(self):
        assert OpticalComponentSpec.model_validate({"kind": "switch", "address": "x"}).optics is None


class TestResults:
    def test_sees_record_uses_class_on_the_wire(self):
        rec = SeesRecord(light_class="dark", terminal="tertiary", via=("covercalibrator",))
        assert rec.model_dump(by_alias=True) == {"class": "dark", "terminal": "tertiary", "via": ("covercalibrator",)}
        assert SeesRecord.model_validate({"class": "sky.science", "terminal": "sky", "via": []}).via == ()

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

    def test_verdict_invariants(self):
        adapter = TypeAdapter(Verdict)
        with pytest.raises(ValidationError):  # nothing to move ⇒ that would be `active`
            adapter.validate_python({"kind": "settable", "see": "dark", "positions": {"tertiary": "beso"}, "moves": {}})
        with pytest.raises(ValidationError):  # an invalid verdict always says why
            adapter.validate_python({"kind": "invalid", "errors": []})
        for kind in ("active", "settable"):
            with pytest.raises(ValidationError):  # a satisfied or reachable goal is never `undefined`
                adapter.validate_python({"kind": kind, "see": "undefined", "positions": {"a": "b"}, "moves": {"a": "b"}})
        with pytest.raises(ValidationError):
            Route(detector="camera", function="object", alternative=0, see="undefined", positions={})

    def test_check_result_round_trip(self):
        res = CheckResult(detector="camera", function="object", verdict=Active(kind=VerdictKind.ACTIVE, see="sky.science"))
        assert CheckResult.model_validate_json(res.model_dump_json()) == res


class TestCompiled:
    def test_round_trip(self):
        key_a = RouteKey(detector="camera", function="object", alternative=0, realization=0)
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
            state={
                "tertiary": SelectorState(position=None, raw=2),
                "covercalibrator": SelectorState(position="open"),
                "covercalibrator.calibrator": SelectorState(position="off"),
            },
            environment={"sun_alt_deg": -30.0, "dome_shutter_open": True},
            expected_sees={"camera": [SeesRecord(light_class="undefined", terminal="tertiary", via=("derotator", "pickoff", "filterwheel"))]},
        )
        suite = ConformanceSuite(generated_from="ocabox-common 1.5.0", vectors=[vector])
        again = ConformanceSuite.model_validate_json(suite.model_dump_json(by_alias=True))
        assert again == suite
        assert again.vectors[0].state["tertiary"].position is None


class TestVersionedContracts:
    def test_other_versions_and_duplicate_sees_are_rejected(self):
        raw = json.loads(EXAMPLE_PATH.read_text())
        rec = {"class": "dark", "terminal": "tertiary", "via": []}
        good = {"generated_from": "x", "vectors": [{"name": "v", "components": raw["components"], "expected_sees": {"camera": [rec]}}]}
        ConformanceSuite.model_validate(good)
        with pytest.raises(ValidationError):
            ConformanceSuite.model_validate({**good, "schema_version": 2})
        with pytest.raises(ValidationError, match="duplicate"):
            ConformanceSuite.model_validate({**good, "vectors": [{**good["vectors"][0], "expected_sees": {"camera": [rec, rec]}}]})
        with pytest.raises(ValidationError):
            OpticsCompiled.model_validate({"schema_version": 2, "generated_from": "x"})
        schema = json_schemas()["ConformanceSuite"]
        assert schema["properties"]["schema_version"]["const"] == 1
        assert "uniqueItems" in json.dumps(schema)


class TestJsonSchemaExport:
    def test_committed_schemas_match_a_fresh_export(self):
        fresh = json_schemas()
        committed = {p.stem.removesuffix(".schema"): p for p in SCHEMAS_DIR.glob("*.schema.json")}
        assert set(committed) == set(fresh), "run `uv run datamodels-export-schemas` and commit the result"
        for name, schema in fresh.items():
            assert committed[name].read_text(encoding="utf-8") == render(schema), (
                f"{committed[name]} is stale — run `uv run datamodels-export-schemas` and commit the result"
            )

    def test_every_public_contract_is_exported(self):
        names = set(EXPORTED)
        for required in ("EdgeRef", "OpticsEdges", "PositionsSpec", "PositionSpec", "DisplayHint", "GoalSpec",
                         "SelectorState", "Environment", "Route", "RouteKey", "Conflict", "ConfigError",
                         "Active", "Settable", "Collision", "Impossible", "Invalid", "Verdict",
                         "Archetype", "CoreFunction", "VerdictKind", "PortOwner"):
            assert required in names
        import datamodels.optics as optics
        from enum import Enum
        from pydantic import BaseModel
        public = {n for n in optics.__all__ if isinstance(getattr(optics, n), type)
                  and (issubclass(getattr(optics, n), BaseModel) or issubclass(getattr(optics, n), Enum))}
        assert public <= names

    def test_wire_names_survive_in_schema(self):
        sees = json_schemas()["SeesRecord"]
        assert set(sees["properties"]) == {"class", "terminal", "via"}
        verdict = json_schemas()["Verdict"]
        assert set(verdict["discriminator"]["mapping"]) == {"active", "settable", "collision", "impossible", "invalid"}


class TestSchemaSemantics:
    """The exported schema must reject what Python rejects: a TypeScript validator gets the same
    grammar, not a looser shadow of it."""

    @staticmethod
    def _validator(name: str) -> Draft202012Validator:
        schema = json_schemas()[name]
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)

    @pytest.mark.parametrize(
        "raw, valid",
        [
            ({"from": "dome"}, True),
            ({"from": {"tertiary": "andor"}}, True),
            ({"from": {"pickoff": ["main", "guide"]}}, True),
            ({"inputs": {"open": "sky", "flat": "flatscreen"}}, True),
            ({}, False),
            ({"from": "a", "inputs": {"x": "b"}}, False),
            ({"from": ["a", "b"]}, False),
            ({"from": {"a": "p", "b": "q"}}, False),
            ({"from": {"a": []}}, False),
            ({"inputs": {}}, False),
            ({"from": "dark"}, False),
            ({"from": {"tertiary": "undefined"}}, False),
            ({"from": {"dark": "p"}}, False),
            ({"inputs": {"Open": "sky"}}, False),
            ({"from": "a", "colour": "red"}, False),
            ({"from": None}, False),
            ({"inputs": None}, False),
            ({"from": "a", "inputs": None}, True),
        ],
    )
    def test_optics_edges_schema_matches_python(self, raw, valid):
        assert self._validator("OpticsEdges").is_valid(raw) is valid
        try:
            OpticsEdges.model_validate(raw)
            python_valid = True
        except ValidationError:
            python_valid = False
        assert python_valid is valid

    @pytest.mark.parametrize(
        "raw, valid",
        [
            ({"beso": {"port": 1, "autoslew-name": "ADR6"}}, True),
            ({"beso": {"port": "ADR6"}}, True),
            ({"beso": {"port": True}}, False),
            ({"dark": {"port": 3}}, False),
            ({"ADR6": {"port": 1}}, False),
        ],
    )
    def test_positions_schema_rejects_reserved_and_malformed_symbols(self, raw, valid):
        assert self._validator("PositionsSpec").is_valid(raw) is valid
        try:
            PositionsSpec.model_validate(raw)
            python_valid = True
        except ValidationError:
            python_valid = False
        assert python_valid is valid

    @pytest.mark.parametrize(
        "raw, valid",
        [
            ({"component": "dome"}, True),
            ({"component": "tertiary", "port": "andor", "port_owner": "upstream"}, True),
            ({"component": "dome", "port": "open"}, False),
            ({"component": "dome", "port_owner": "self"}, False),
            ({"component": "dome", "port": "open", "port_owner": None}, False),
        ],
    )
    def test_edge_ref_port_and_owner_come_together(self, raw, valid):
        assert self._validator("EdgeRef").is_valid(raw) is valid
        try:
            EdgeRef.model_validate(raw)
            python_valid = True
        except ValidationError:
            python_valid = False
        assert python_valid is valid

    @pytest.mark.parametrize(
        "raw, valid",
        [
            ({"object": "sky.science", "dark": "dark"}, True),
            ({"object": "undefined"}, False),
            ({"object": {"see": "undefined"}}, False),
            ({"object": {"see": "dark", "when": "undefined"}}, False),
            ({"object": []}, False),
        ],
    )
    def test_goals_never_undefined_in_schema_and_python(self, raw, valid):
        assert self._validator("DetectorPaths").is_valid(raw) is valid
        try:
            DetectorPaths.model_validate(raw)
            python_valid = True
        except ValidationError:
            python_valid = False
        assert python_valid is valid

    def test_results_reject_reserved_component_references(self):
        sees = self._validator("SeesRecord")
        assert sees.is_valid({"class": "dark", "terminal": "tertiary", "via": []})
        assert not sees.is_valid({"class": "dark", "terminal": "tertiary"})  # provenance is part of the record, on the wire too
        assert not sees.is_valid({"class": "dark", "terminal": "dark", "via": []})
        with pytest.raises(ValidationError):
            SeesRecord.model_validate({"class": "dark", "terminal": "tertiary"})
        with pytest.raises(ValidationError, match="reserved word"):
            SeesRecord.model_validate({"class": "dark", "terminal": "dark", "via": []})
        check = self._validator("CheckResult")
        assert not check.is_valid({"detector": "undefined", "function": "object", "verdict": {"kind": "active", "see": "sky.science"}})
        with pytest.raises(ValidationError, match="reserved word"):
            CheckResult.model_validate({"detector": "undefined", "function": "object", "verdict": {"kind": "active", "see": "sky.science"}})

    def test_state_key_schema(self):
        settable = self._validator("Verdict")
        ok = {"kind": "settable", "see": "dark", "positions": {"covercalibrator.calibrator": "off"}, "moves": {"covercalibrator.calibrator": "off"}}
        assert settable.is_valid(ok)
        assert not settable.is_valid({**ok, "positions": {"dark.calibrator": "off"}})
        assert not settable.is_valid({**ok, "positions": {"covercalibrator.undefined": "off"}})
        assert not settable.is_valid({**ok, "positions": {"a.b.c": "off"}})

    @pytest.mark.parametrize(
        "name, model, raw, valid",
        [
            ("Environment", Environment, {"sun_alt_deg": -30}, True),
            ("Environment", Environment, {"sun_alt_deg": -30.5, "dome_az_deg": 49, "mount_alt_deg": 15.0}, True),
            ("Environment", Environment, {"sun_alt_deg": True}, False),
            ("Environment", Environment, {"sun_alt_deg": "-30"}, False),
            ("Environment", Environment, {"dome_az_deg": "49"}, False),
            ("DisplayHint", DisplayHint, {"x": 1, "y": 2.5}, True),
            ("DisplayHint", DisplayHint, {"x": True}, False),
            ("DisplayHint", DisplayHint, {"x": "1"}, False),
            ("SelectorState", SelectorState, {"position": None, "raw": 2}, True),
            ("SelectorState", SelectorState, {"position": None, "raw": 2.5}, True),
            ("SelectorState", SelectorState, {"position": None, "raw": "ADR6"}, True),
            ("SelectorState", SelectorState, {"position": "open", "raw": True}, True),
            ("SelectorState", SelectorState, {"position": "open", "moving": True, "stale": False}, True),
            ("SelectorState", SelectorState, {"position": "open", "moving": 1}, False),
            ("SelectorState", SelectorState, {"position": "open", "stale": "false"}, False),
            ("Environment", Environment, {"dome_shutter_open": True}, True),
            ("Environment", Environment, {"dome_shutter_open": 1}, False),
            ("Environment", Environment, {"dome_shutter_open": "true"}, False),
            ("RouteKey", RouteKey, {"detector": "camera", "function": "object", "alternative": 0}, True),
            ("RouteKey", RouteKey, {"detector": "camera", "function": "object", "alternative": True}, False),
            ("RouteKey", RouteKey, {"detector": "camera", "function": "object", "alternative": "1"}, False),
            ("RouteKey", RouteKey, {"detector": "camera", "function": "object", "alternative": -1}, False),
            ("RouteKey", RouteKey, {"detector": "camera", "function": "object", "alternative": 1.0}, True),
            ("RouteKey", RouteKey, {"detector": "camera", "function": "object", "alternative": 1.5}, False),
            ("PositionSpec", PositionSpec, {"port": 2.0}, True),
            ("PositionSpec", PositionSpec, {"port": 2.5}, False),
            ("PositionSpec", PositionSpec, {"port": True}, False),
        ],
    )
    def test_numbers_are_json_numbers_in_schema_and_python(self, name, model, raw, valid):
        assert self._validator(name).is_valid(raw) is valid
        try:
            model.model_validate(raw)
            python_valid = True
        except ValidationError:
            python_valid = False
        assert python_valid is valid

    def test_integral_floats_are_integers_as_in_json_schema(self):
        assert RouteKey.model_validate_json('{"detector": "camera", "function": "object", "alternative": 1.0}').alternative == 1
        assert PositionSpec.model_validate_json('{"port": 2.0}').port == 2
        with pytest.raises(ValidationError):
            RouteKey.model_validate_json('{"detector": "camera", "function": "object", "alternative": 1.5}')

    def test_json_numbers_are_finite(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with pytest.raises(ValidationError):
                Environment(sun_alt_deg=bad)
        with pytest.raises(ValidationError):
            Environment.model_validate_json('{"sun_alt_deg": NaN}')

    def test_boolean_readback_stays_boolean(self):
        assert SelectorState.model_validate({"position": "open", "raw": True}).raw is True
        assert SelectorState.model_validate({"position": None, "raw": 2}).raw == 2

    def test_verdict_tag_is_required_in_schema_and_python(self):
        verdict = self._validator("Verdict")
        untagged = {"see": "sky.science"}
        assert not verdict.is_valid(untagged)
        with pytest.raises(ValidationError):
            TypeAdapter(Verdict).validate_python(untagged)
        for name in ("Active", "Settable", "Collision", "Impossible", "Invalid"):
            assert "kind" in json_schemas()[name]["required"]

    def test_expected_sees_is_canonical_regardless_of_authored_order(self):
        raw = json.loads(EXAMPLE_PATH.read_text())
        a = {"class": "dark", "terminal": "tertiary", "via": []}
        b = {"class": "lamp", "terminal": "covercalibrator", "via": ["tertiary"]}
        vector = {"name": "v", "components": raw["components"], "expected_sees": {"camera": [a, b]}}
        forward = ConformanceVector.model_validate(vector)
        reversed_ = ConformanceVector.model_validate({**vector, "expected_sees": {"camera": [b, a]}})
        assert forward == reversed_
        assert forward.model_dump_json(by_alias=True) == reversed_.model_dump_json(by_alias=True)
        assert [r.light_class for r in forward.expected_sees["camera"]] == ["dark", "lamp"]

    def test_verdict_schema_carries_the_invariants(self):
        verdict = self._validator("Verdict")
        assert not verdict.is_valid({"kind": "settable", "see": "dark", "positions": {"tertiary": "beso"}, "moves": {}})
        assert not verdict.is_valid({"kind": "invalid", "errors": []})
        assert not verdict.is_valid({"kind": "active", "see": "undefined"})
        assert verdict.is_valid({"kind": "settable", "see": "dark", "positions": {"tertiary": "beso"}, "moves": {"tertiary": "beso"}})
        route = self._validator("Route")
        assert not route.is_valid({"detector": "camera", "function": "object", "alternative": 0, "see": "undefined", "positions": {}})

    def test_example_validates_against_the_exported_schema(self, ):
        raw = json.loads(EXAMPLE_PATH.read_text())
        assert self._validator("TelescopeOpticsSpec").is_valid(raw)
        assert not self._validator("TelescopeOpticsSpec").is_valid({**raw, "components": {**raw["components"], "dark": {"kind": "beamdump"}}})


if __name__ == "__main__":
    pytest.main([__file__])
