from pipeline.cartoon_motion import (
    BLENDER_BACKEND,
    apply_motion_defaults,
    normalize_motion_plan,
    validate_motion_plan,
    validate_script_motion,
)


def test_existing_scene_is_untouched_without_opt_in():
    script = {"scenes": [{"text": "hello", "duration": 4}]}
    assert apply_motion_defaults(script) is False
    assert "motion_plan" not in script["scenes"][0]


def test_top_level_backend_populates_vertical_plan():
    script = {
        "cartoon_motion_backend": BLENDER_BACKEND,
        "scenes": [{"text": "hello", "duration": 4}],
    }
    assert apply_motion_defaults(script) is True
    plan = script["scenes"][0]["motion_plan"]
    assert plan["render"]["width"] == 1080
    assert plan["render"]["height"] == 1920
    assert plan["render"]["fps"] == 24
    assert plan["duration_seconds"] == 4.0
    assert validate_script_motion(script) == []


def test_character_scene_defaults_to_rigged_character():
    scene = {"animation_character_required": True}
    plan = normalize_motion_plan(scene)
    assert plan["strategy"] == "rigged_character"


def test_object_scene_defaults_to_layered_parallax():
    plan = normalize_motion_plan({})
    assert plan["strategy"] == "layered_parallax"


def test_partial_nested_values_merge_with_defaults():
    scene = {
        "motion_plan": {
            "camera": {"move": "push_in", "intensity": 0.4},
            "atmosphere": {"dust": True},
        }
    }
    plan = normalize_motion_plan(scene)
    assert plan["camera"]["move"] == "push_in"
    assert plan["camera"]["lens_mm"] == 50.0
    assert plan["atmosphere"]["dust"] is True
    assert plan["atmosphere"]["fog"] is False


def test_invalid_strategy_and_camera_are_reported():
    plan = normalize_motion_plan({})
    plan["strategy"] = "magic"
    plan["camera"]["move"] = "teleport"
    errors = validate_motion_plan(plan, 2)
    assert any("scene 2 unknown motion strategy" in error for error in errors)
    assert any("scene 2 unknown camera move" in error for error in errors)


def test_apply_defaults_is_idempotent():
    script = {"cartoon_motion_backend": BLENDER_BACKEND, "scenes": [{}]}
    assert apply_motion_defaults(script) is True
    assert apply_motion_defaults(script) is False
