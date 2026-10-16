import unittest

from cps_product.scenarios import (
    EXAMPLE_SCENARIOS,
    Scenario,
    ScenarioValidationError,
    load_scenario,
    parse_scenario,
)


def _vector(x=0.0, y=0.0):
    return {"x": x, "y": y}


def _kinematics(static=False):
    return {
        "position": _vector(1.0, 2.0),
        "velocity": _vector(0.0, 0.0) if static else _vector(0.1, 0.2),
        "acceleration": _vector(0.0, 0.0),
    }


def _entity(name, static=False):
    return {"name": name, "kinematics": _kinematics(static=static)}


def _valid_scenario():
    return {
        "schema_version": "1.0",
        "name": "test_scenario",
        "forces": {
            "hunters": [_entity("hunter_1")],
            "moving_targets": [_entity("moving_1")],
            "static_targets": [_entity("static_1", static=True)],
        },
        "environment": {"area": 10.0, "duration": 20.0},
        "mission_goals": ["goal_1"],
    }


class ScenarioModuleTests(unittest.TestCase):
    def test_example_scenarios_load_and_validate(self):
        for path in EXAMPLE_SCENARIOS:
            with self.subTest(path=path):
                scenario = load_scenario(path)
                self.assertIsInstance(scenario, Scenario)
                self.assertEqual(scenario.schema_version, "1.0")
                self.assertTrue(scenario.name)
                self.assertTrue(scenario.forces.hunters)
                self.assertTrue(scenario.forces.moving_targets)
                self.assertTrue(scenario.forces.static_targets)
                self.assertGreater(scenario.environment.area, 0.0)
                self.assertGreater(scenario.environment.duration, 0.0)
                self.assertTrue(scenario.mission_goals)
                for entity in (
                    scenario.forces.hunters
                    + scenario.forces.moving_targets
                    + scenario.forces.static_targets
                ):
                    self.assertIsInstance(entity.name, str)
                    self.assertIsInstance(entity.kinematics.position.x, float)
                    self.assertIsInstance(entity.kinematics.position.y, float)

    def test_valid_scenario_parses_to_typed_structures(self):
        scenario = parse_scenario(_valid_scenario())
        self.assertIsInstance(scenario, Scenario)
        self.assertEqual(scenario.name, "test_scenario")
        self.assertEqual(len(scenario.forces.hunters), 1)
        self.assertEqual(scenario.forces.hunters[0].kinematics.velocity.x, 0.1)
        self.assertEqual(scenario.environment.area, 10.0)
        self.assertEqual(scenario.mission_goals, ("goal_1",))

    def _assert_validation_error(self, data, field, reason_fragment):
        with self.assertRaises(ScenarioValidationError) as ctx:
            parse_scenario(data)
        self.assertEqual(ctx.exception.field, field)
        self.assertIn(reason_fragment, ctx.exception.reason)

    def test_missing_field_is_rejected(self):
        data = _valid_scenario()
        del data["environment"]
        self._assert_validation_error(data, "environment", "missing required field")

    def test_unknown_field_is_rejected(self):
        data = _valid_scenario()
        data["extra"] = 1
        self._assert_validation_error(data, "extra", "unknown field")

    def test_wrong_type_is_rejected(self):
        data = _valid_scenario()
        data["environment"]["area"] = "10"
        self._assert_validation_error(data, "environment.area", "finite number")

    def test_invalid_name_is_rejected(self):
        data = _valid_scenario()
        data["name"] = "bad name!"
        self._assert_validation_error(data, "name", "name")

    def test_non_positive_area_is_rejected(self):
        data = _valid_scenario()
        data["environment"]["area"] = 0
        self._assert_validation_error(data, "environment.area", "positive")

    def test_non_positive_duration_is_rejected(self):
        data = _valid_scenario()
        data["environment"]["duration"] = -1
        self._assert_validation_error(data, "environment.duration", "positive")

    def test_missing_nested_field_is_rejected(self):
        data = _valid_scenario()
        del data["forces"]["hunters"][0]["kinematics"]["velocity"]
        self._assert_validation_error(
            data,
            "forces.hunters[0].kinematics.velocity",
            "missing required field",
        )

    def test_unknown_nested_field_is_rejected(self):
        data = _valid_scenario()
        data["forces"]["static_targets"][0]["kinematics"]["position"]["z"] = 0
        self._assert_validation_error(
            data,
            "forces.static_targets[0].kinematics.position.z",
            "unknown field",
        )

    def test_wrong_type_vector_component_is_rejected(self):
        data = _valid_scenario()
        data["forces"]["moving_targets"][0]["kinematics"]["position"]["x"] = "1"
        self._assert_validation_error(
            data,
            "forces.moving_targets[0].kinematics.position.x",
            "finite number",
        )

    def test_invalid_entity_name_is_rejected(self):
        data = _valid_scenario()
        data["forces"]["hunters"][0]["name"] = "1hunter"
        self._assert_validation_error(data, "forces.hunters[0].name", "name")

    def test_static_target_nonzero_velocity_is_rejected(self):
        data = _valid_scenario()
        data["forces"]["static_targets"][0]["kinematics"]["velocity"] = _vector(1.0, 0.0)
        self._assert_validation_error(
            data,
            "forces.static_targets[0].kinematics.velocity",
            "zero vector",
        )


if __name__ == "__main__":
    unittest.main()
