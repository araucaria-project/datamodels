import pytest
from pydantic import TypeAdapter, ValidationError

from datamodels.messages import Caller, MessageClass, RpcError, RpcOk, RpcReply, RpcRequest, Severity, StatusValue, Subject

TS = [2026, 10, 19, 3, 15, 0, 123456]


class TestSubject:
    def test_round_trip(self):
        s = Subject.parse("status.optics.jk15.camera.sees")
        assert (s.message_class, s.realm, s.scope, s.element, s.item) == (MessageClass.STATUS, "optics", "jk15", "camera", "sees")
        assert str(s) == "status.optics.jk15.camera.sees"

    def test_wire_alias(self):
        s = Subject.model_validate({"class": "rpc", "realm": "optics", "scope": "jk15", "element": "camera", "item": "setpath"})
        assert str(s) == "rpc.optics.jk15.camera.setpath"

    @pytest.mark.parametrize(
        "subject",
        [
            "status.optics.jk15.camera",  # four tokens
            "status.optics.jk15.camera.sees.extra",  # six tokens
            "svc.heartbeat.optics.jk15.x",  # svc belongs to the TCS library
            "status.optics.jk15-beso.camera.sees",  # hyphen
            "status.Optics.jk15.camera.sees",  # upper case
            "status.optics..camera.sees",  # empty token
        ],
    )
    def test_rejects(self, subject):
        with pytest.raises(ValueError):
            Subject.parse(subject)


class TestStatusValue:
    def test_any_json_value(self):
        for value in ("andor", 1.5, True, None, [{"class": "sky.science", "terminal": "sky", "via": []}]):
            assert StatusValue(value=value, ts=TS).value == value

    def test_ts_is_a_serverish_timestamp(self):
        assert StatusValue.model_validate({"value": 1, "ts": TS}).ts == tuple(TS)
        with pytest.raises(ValidationError):
            StatusValue.model_validate({"value": 1, "ts": TS[:6]})
        with pytest.raises(ValidationError):
            StatusValue.model_validate({"value": 1, "ts": [str(x) for x in TS]})

    def test_ts_required_and_extra_forbidden(self):
        with pytest.raises(ValidationError):
            StatusValue.model_validate({"value": 1})
        with pytest.raises(ValidationError):
            StatusValue.model_validate({"value": 1, "ts": TS, "quality": "ok"})


class TestRpc:
    def test_request_defaults(self):
        r = RpcRequest()
        assert r.parameters == {} and r.caller is None and r.timeout is None

    def test_request_full(self):
        r = RpcRequest.model_validate({"parameters": {"function": "object"}, "caller": {"name": "observer", "id": "a1"}, "timeout": 8.0})
        assert r.caller == Caller(name="observer", id="a1") and r.parameters["function"] == "object"

    @pytest.mark.parametrize("timeout", [0, -1, "8"])
    def test_request_timeout_positive_number(self, timeout):
        with pytest.raises(ValidationError):
            RpcRequest.model_validate({"timeout": timeout})

    def test_reply_discriminates(self):
        reply = TypeAdapter(RpcReply)
        assert reply.validate_python({"status": "ok", "result": {"accepted": True}}) == RpcOk(result={"accepted": True})
        err = reply.validate_python({"status": "error", "code": 4009, "severity": "NORMAL", "message": "covercalibrator: not enabled for automatic actuation"})
        assert isinstance(err, RpcError) and err.severity is Severity.NORMAL and err.code == 4009

    @pytest.mark.parametrize(
        "raw",
        [
            {"status": "maybe"},
            {"status": "error", "code": 4009, "severity": "FATAL", "message": "x"},
            {"status": "error", "code": "4009", "severity": "NORMAL", "message": "x"},
            {"status": "error", "severity": "NORMAL", "message": "x"},
        ],
    )
    def test_reply_rejects(self, raw):
        with pytest.raises(ValidationError):
            TypeAdapter(RpcReply).validate_python(raw)
