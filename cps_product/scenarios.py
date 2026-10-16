"""Scenario parameter sets for cps_product.

A scenario is a machine-readable JSON document that pins the forces, environment,
and high-level mission goals for a run.

Schema version 1.0 format:
{
  "schema_version": "1.0",
  "name": "string",
  "forces": {
    "hunters": [entity],
    "moving_targets": [entity],
    "static_targets": [entity]
  },
  "environment": {
    "area": positive_number,
    "duration": positive_number
  },
  "mission_goals": ["string", ...]
}

entity:
{
  "name": "string",
  "kinematics": {
    "position": {"x": number, "y": number},
    "velocity": {"x": number, "y": number},
    "acceleration": {"x": number, "y": number}
  }
}

Defaults and conventions:
- Units for position, velocity, acceleration, area, and duration are arbitrary but
  must be consistent within a scenario.
- Names must start with an ASCII letter and contain only ASCII letters, digits,
  underscores, or hyphens (maximum 64 characters).
- Static targets must have zero velocity and acceleration.
- Mission goals are free-form non-empty strings.
- All three force categories are required; their lists may be empty.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Tuple

SCHEMA_VERSION = "1.0"
NAME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")

TOP_LEVEL_FIELDS = ("schema_version", "name", "forces", "environment", "mission_goals")
FORCES_FIELDS = ("hunters", "moving_targets", "static_targets")
ENTITY_FIELDS = ("name", "kinematics")
KINEMATICS_FIELDS = ("position", "velocity", "acceleration")
VECTOR_FIELDS = ("x", "y")
ENVIRONMENT_FIELDS = ("area", "duration")

EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"
EXAMPLE_SCENARIOS = (
    EXAMPLES_DIR / "coastal_patrol.json",
    EXAMPLES_DIR / "urban_search.json",
)


class ScenarioValidationError(ValueError):
    """Raised when a scenario document is invalid."""

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"field '{field}': {reason}")


@dataclass(frozen=True)
class Vector2:
    x: float
    y: float


@dataclass(frozen=True)
class Kinematics:
    position: Vector2
    velocity: Vector2
    acceleration: Vector2


@dataclass(frozen=True)
class Entity:
    name: str
    kinematics: Kinematics


@dataclass(frozen=True)
class Forces:
    hunters: Tuple[Entity, ...]
    moving_targets: Tuple[Entity, ...]
    static_targets: Tuple[Entity, ...]


@dataclass(frozen=True)
class Environment:
    area: float
    duration: float


@dataclass(frozen=True)
class Scenario:
    schema_version: str
    name: str
    forces: Forces
    environment: Environment
    mission_goals: Tuple[str, ...]


def _fail(field: str, reason: str) -> None:
    raise ScenarioValidationError(field, reason)


def _as_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(field, "must be a finite number")
    try:
        number = float(value)
    except (OverflowError, ValueError):
        _fail(field, "must be a finite number")
    if not math.isfinite(number):
        _fail(field, "must be a finite number")
    return number


def _validate_name(value: Any, field: str) -> str:
    if not isinstance(value, str):
        _fail(field, "must be a string")
    if not NAME_PATTERN.fullmatch(value):
        _fail(field, "must be a name matching [A-Za-z][A-Za-z0-9_-]{0,63}")
    return value


def _check_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(field, "must be an object")
    return value


def _check_list(value: Any, field: str) -> list:
    if not isinstance(value, list):
        _fail(field, "must be an array")
    return value


def _check_no_unknown(value: Mapping[str, Any], allowed: tuple, field: str) -> None:
    for key in value:
        if key not in allowed:
            _fail(f"{field}.{key}" if field else str(key), "unknown field")


def _require(mapping: Mapping[str, Any], key: str, field: str) -> Any:
    if key not in mapping:
        _fail(f"{field}.{key}" if field else str(key), "missing required field")
    return mapping[key]


def _parse_vector(value: Any, field: str) -> Vector2:
    value = _check_mapping(value, field)
    _check_no_unknown(value, VECTOR_FIELDS, field)
    x = _require(value, "x", field)
    y = _require(value, "y", field)
    return Vector2(_as_number(x, f"{field}.x"), _as_number(y, f"{field}.y"))


def _parse_kinematics(value: Any, field: str, static: bool = False) -> Kinematics:
    value = _check_mapping(value, field)
    _check_no_unknown(value, KINEMATICS_FIELDS, field)
    position = _parse_vector(_require(value, "position", field), f"{field}.position")
    velocity = _parse_vector(_require(value, "velocity", field), f"{field}.velocity")
    acceleration = _parse_vector(_require(value, "acceleration", field), f"{field}.acceleration")
    if static:
        for vector_name, vector in (("velocity", velocity), ("acceleration", acceleration)):
            if vector.x != 0.0 or vector.y != 0.0:
                _fail(f"{field}.{vector_name}", "static target must have a zero vector")
    return Kinematics(position, velocity, acceleration)


def _parse_entity(value: Any, field: str, static: bool = False) -> Entity:
    value = _check_mapping(value, field)
    _check_no_unknown(value, ENTITY_FIELDS, field)
    name = _validate_name(_require(value, "name", field), f"{field}.name")
    kinematics = _parse_kinematics(
        _require(value, "kinematics", field),
        f"{field}.kinematics",
        static=static,
    )
    return Entity(name, kinematics)


def _parse_entity_list(value: Any, field: str, static: bool = False) -> Tuple[Entity, ...]:
    value = _check_list(value, field)
    return tuple(
        _parse_entity(item, f"{field}[{index}]", static=static)
        for index, item in enumerate(value)
    )


def _parse_forces(value: Any, field: str) -> Forces:
    value = _check_mapping(value, field)
    _check_no_unknown(value, FORCES_FIELDS, field)
    return Forces(
        hunters=_parse_entity_list(_require(value, "hunters", field), f"{field}.hunters", static=False),
        moving_targets=_parse_entity_list(_require(value, "moving_targets", field), f"{field}.moving_targets", static=False),
        static_targets=_parse_entity_list(_require(value, "static_targets", field), f"{field}.static_targets", static=True),
    )


def _parse_environment(value: Any, field: str) -> Environment:
    value = _check_mapping(value, field)
    _check_no_unknown(value, ENVIRONMENT_FIELDS, field)
    area = _as_number(_require(value, "area", field), f"{field}.area")
    duration = _as_number(_require(value, "duration", field), f"{field}.duration")
    if area <= 0.0:
        _fail(f"{field}.area", "must be positive")
    if duration <= 0.0:
        _fail(f"{field}.duration", "must be positive")
    return Environment(area, duration)


def _parse_mission_goals(value: Any, field: str) -> Tuple[str, ...]:
    value = _check_list(value, field)
    goals = []
    for index, goal in enumerate(value):
        goal_field = f"{field}[{index}]"
        if not isinstance(goal, str):
            _fail(goal_field, "must be a string")
        if not goal.strip():
            _fail(goal_field, "must be a non-empty string")
        goals.append(goal)
    return tuple(goals)


def parse_scenario(data: Any) -> Scenario:
    """Parse and validate a scenario mapping into typed in-memory structures."""
    if not isinstance(data, Mapping):
        _fail("$", "scenario must be an object")
    _check_no_unknown(data, TOP_LEVEL_FIELDS, "")
    for key in TOP_LEVEL_FIELDS:
        _require(data, key, "")

    schema_version = data["schema_version"]
    if not isinstance(schema_version, str) or schema_version != SCHEMA_VERSION:
        _fail("schema_version", f"must be '{SCHEMA_VERSION}'")

    name = _validate_name(data["name"], "name")
    forces = _parse_forces(data["forces"], "forces")
    environment = _parse_environment(data["environment"], "environment")
    mission_goals = _parse_mission_goals(data["mission_goals"], "mission_goals")

    return Scenario(schema_version, name, forces, environment, mission_goals)


def validate_scenario(data: Any) -> Scenario:
    """Validate a scenario mapping and return the typed in-memory scenario."""
    return parse_scenario(data)


def load_scenario(path: Any) -> Scenario:
    """Load and validate a scenario JSON file."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        _fail(str(path), f"cannot read file: {exc.strerror or exc}")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        _fail(str(path), f"invalid JSON: {exc}")
    return parse_scenario(data)
