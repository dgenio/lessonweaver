import json
from pathlib import Path
from typing import Any

from lessonweaver.models import (
    RiskLevel,
    Scope,
    SensitivityLevel,
    SkillCard,
    SkillStatus,
    TraceEventType,
)
from lessonweaver.traces import validate_trace_dict

ROOT = Path(__file__).resolve().parents[1]


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def _resolve_ref(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return schema
    if not ref.startswith("#/$defs/"):
        raise AssertionError(f"unsupported schema ref: {ref}")
    return root["$defs"][ref.removeprefix("#/$defs/")]


def _type_matches(expected: str | list[str], value: object) -> bool:
    candidates = [expected] if isinstance(expected, str) else expected
    for candidate in candidates:
        if candidate == "null" and value is None:
            return True
        if candidate == "object" and isinstance(value, dict):
            return True
        if candidate == "array" and isinstance(value, list):
            return True
        if candidate == "string" and isinstance(value, str):
            return True
        if candidate == "boolean" and isinstance(value, bool):
            return True
        if candidate == "number" and isinstance(value, int | float) and not isinstance(value, bool):
            return True
    return False


def _schema_errors(
    schema: dict[str, Any],
    value: object,
    *,
    root: dict[str, Any] | None = None,
    path: str = "",
) -> list[str]:
    root = schema if root is None else root
    schema = _resolve_ref(schema, root)
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type is not None and not _type_matches(expected_type, value):
        return [f"{path or '/'}: expected {expected_type}"]
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        errors.append(f"{path or '/'}: expected one of {enum}")
    if isinstance(value, str) and value == "" and schema.get("minLength", 0) > 0:
        errors.append(f"{path or '/'}: must be non-empty")
    if isinstance(value, list):
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f"{path or '/'}: expected at least {min_items} item(s)")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(_schema_errors(item_schema, item, root=root, path=f"{path}/{index}"))
    if isinstance(value, dict):
        for field in schema.get("required", []):
            if field not in value:
                errors.append(f"{path}/{field}: missing required property")
        properties = schema.get("properties", {})
        for field, property_schema in properties.items():
            if field in value:
                errors.extend(
                    _schema_errors(property_schema, value[field], root=root, path=f"{path}/{field}")
                )
    return errors


def test_trace_schema_event_enum_matches_model() -> None:
    schema = _load_schema("trace.schema.json")
    assert schema["$defs"]["traceEvent"]["properties"]["type"]["enum"] == [
        item.value for item in TraceEventType
    ]


def test_skill_schema_enums_match_models() -> None:
    schema = _load_schema("skill-card.schema.json")
    properties = schema["properties"]
    assert properties["risk_level"]["enum"] == [item.value for item in RiskLevel]
    assert properties["scope"]["enum"] == [item.value for item in Scope]
    assert properties["status"]["enum"] == [item.value for item in SkillStatus]
    assert properties["sensitivity"]["enum"] == [item.value for item in SensitivityLevel]


def test_trace_schema_accepts_example_traces() -> None:
    schema = _load_schema("trace.schema.json")
    trace_paths = sorted(ROOT.glob("examples/**/traces/*.json"))
    assert trace_paths
    for path in trace_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert _schema_errors(schema, payload) == []
        assert validate_trace_dict(payload) == []


def test_skill_card_schema_accepts_example_skills() -> None:
    schema = _load_schema("skill-card.schema.json")
    skill_paths = sorted(ROOT.glob("examples/**/skills/*.json")) + [
        ROOT / "examples/coding_agent_pr_review/skill.json"
    ]
    assert skill_paths
    for path in skill_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert _schema_errors(schema, payload) == []
        assert SkillCard.from_dict(payload).id
