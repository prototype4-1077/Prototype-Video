from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
import unittest

from pipeline.cartoon_deformable_performance_3q import (
    EXPECTED_SEMANTIC_CHANNELS,
    REQUIRED_TOPOLOGY_LAYERS,
    compile_performance_frame,
    load_deformable_performance_contract,
    render_deformable_performance_3q,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "concept/characters/june_oxley_deformable_performance_3q_v1.json"


class CartoonDeformablePerformance3QTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.assets = load_deformable_performance_contract(CONTRACT)

    def test_contract_locks_exact_phase27_stand_clock_and_zero_cash_boundary(self) -> None:
        output = self.contract["output"]
        self.assertEqual(
            (
                output["width"],
                output["height"],
                output["fps"],
                output["frame_count"],
                output["duration_seconds"],
            ),
            (1920, 1080, 30, 171, 5.7),
        )
        self.assertEqual(self.contract["adapter_id"], "deformable_performance_3q")
        self.assertEqual(self.contract["view_id"], "WIDE_BODY_3Q")
        self.assertEqual(self.contract["action_id"], "STAND_UP")
        self.assertEqual(self.contract["action"]["source_master_frames"], [226, 396])
        self.assertEqual(self.contract["cash_cost"], 0)
        self.assertFalse(self.contract["paid_runtime_dependency"])
        self.assertEqual(self.contract["promotion_state"], "gate_a_private_adapter_fixture")

    def test_adapter_is_a_strict_semantic_superset_of_phase27_wide_body(self) -> None:
        channels = {channel["id"] for channel in self.contract["semantic_interface"]["input_channels"]}
        self.assertEqual(channels, EXPECTED_SEMANTIC_CHANNELS)
        self.assertEqual(
            channels,
            {"body_pose", "root_contact", "hand_contact", "prop_pose", "camera", "atmosphere"},
        )
        phase27 = json.loads(
            (REPO_ROOT / "concept/characters/june_oxley_performance_rig_v1.json").read_text(encoding="utf-8")
        )
        wide = next(view for view in phase27["views"] if view["id"] == "WIDE_BODY_3Q")
        self.assertTrue(set(wide["channels"]).issubset(channels))
        self.assertEqual(channels - set(wide["channels"]), {"hand_contact"})
        self.assertEqual(self.contract["compatibility"]["preserved_actions"], ["POUR_COFFEE", "DIRECT_ADDRESS"])
        self.assertEqual(self.contract["compatibility"]["preserved_master_clock"]["cut_frames"], [172, 430])

    def test_all_accepted_sources_are_content_addressed_and_present(self) -> None:
        expected = {
            "canonical_identity",
            "phase27_interface",
            "phase28_deformation_reference",
            "gs030_control",
            "background",
            "neutral_3q_reference",
            "seated_endpoint",
            "leverage_corrective",
            "weight_transfer_corrective",
            "release_corrective",
            "standing_endpoint",
        }
        self.assertEqual(set(self.assets), expected)
        self.assertTrue(all(path.is_file() for path in self.assets.values()))
        for source in self.contract["accepted_sources"].values():
            self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            self.contract["accepted_sources"]["leverage_corrective"]["role"],
            "corrective_reference_not_full_frame_crossfade",
        )

    def test_declared_topology_names_hands_boots_prop_and_finishing_control_regions(self) -> None:
        layers = self.contract["topology"]["layers"]
        ids = {layer["id"] for layer in layers}
        self.assertEqual(ids, REQUIRED_TOPOLOGY_LAYERS)
        self.assertTrue(all(layer["required"] for layer in layers))
        self.assertEqual(len({layer["depth"] for layer in layers}), len(layers))
        self.assertTrue(
            {
                "head",
                "neck",
                "torso",
                "pelvis",
                "left_hand",
                "right_hand",
                "left_boot",
                "right_boot",
                "mug",
                "chair_grasp_corrective",
                "mug_grasp_corrective",
                "receiving_shadow",
                "light_wrap",
            }.issubset(ids)
        )
        self.assertFalse(self.contract["topology"]["runtime_cross_dissolve_allowed"])
        self.assertFalse(self.contract["topology"]["full_frame_optical_flow_allowed"])

    def test_action_segments_cover_every_frame_once_and_smears_are_local_only(self) -> None:
        segments = self.contract["action"]["segments"]
        expected_start = 1
        for segment in segments:
            self.assertEqual(segment["start_frame"], expected_start)
            self.assertGreaterEqual(segment["end_frame"], segment["start_frame"])
            expected_start = segment["end_frame"] + 1
        self.assertEqual(expected_start, 172)
        self.assertEqual(self.contract["action"]["declared_local_smear_frames"], [91])
        self.assertLessEqual(len(self.contract["action"]["declared_local_smear_frames"]), 1)
        self.assertLessEqual(self.contract["runtime_asset_pack"]["local_smear_travel_pixels"], 4)
        self.assertFalse(self.contract["action"]["full_frame_smear_allowed"])

    def test_frame_compiler_exposes_deterministic_semantics_on_exact_boundaries(self) -> None:
        first = compile_performance_frame(self.contract, 1)
        anticipation = compile_performance_frame(self.contract, 64)
        last_seated = compile_performance_frame(self.contract, 70)
        leverage = compile_performance_frame(self.contract, 78)
        almost_standing = compile_performance_frame(self.contract, 95)
        standing = compile_performance_frame(self.contract, 96)
        final = compile_performance_frame(self.contract, 171)

        for state in (first, anticipation, last_seated, leverage, almost_standing, standing, final):
            self.assertEqual(set(state["channels"]), EXPECTED_SEMANTIC_CHANNELS)
            self.assertEqual(state, compile_performance_frame(self.contract, state["frame"]))

        self.assertEqual(first["channels"]["body_pose"]["stand_progress"], 0.0)
        self.assertGreater(anticipation["channels"]["body_pose"]["anticipation"], 0.0)
        self.assertEqual(last_seated["channels"]["body_pose"]["anticipation"], 1.0)
        self.assertEqual(last_seated["channels"]["body_pose"]["stand_progress"], 0.0)
        self.assertEqual(leverage["channels"]["body_pose"]["stand_progress"], 0.25)
        self.assertEqual(almost_standing["channels"]["body_pose"]["stand_progress"], 0.93)
        self.assertEqual(standing["channels"]["body_pose"]["stand_progress"], 1.0)
        self.assertEqual(final["channels"]["body_pose"]["stand_progress"], 1.0)
        self.assertEqual(first["segment_id"], "SEATED_HOLD")
        self.assertEqual(standing["segment_id"], "SETTLE")
        self.assertTrue(compile_performance_frame(self.contract, 91)["smear_allowed"])
        self.assertFalse(compile_performance_frame(self.contract, 71)["smear_allowed"])
        self.assertFalse(compile_performance_frame(self.contract, 72)["smear_allowed"])

    def test_weight_staging_and_settle_are_authored_not_inferred(self) -> None:
        self.assertEqual(compile_performance_frame(self.contract, 57)["channels"]["body_pose"]["anticipation"], 0.0)
        self.assertEqual(compile_performance_frame(self.contract, 70)["channels"]["body_pose"]["anticipation"], 1.0)
        for frame in (71, 78, 86, 94, 95, 96):
            pose = compile_performance_frame(self.contract, frame)["channels"]["body_pose"]
            self.assertGreaterEqual(pose["pelvis_progress"], pose["torso_progress"])
        for frame in (78, 86, 94, 96):
            pose = compile_performance_frame(self.contract, frame)["channels"]["body_pose"]
            self.assertGreater(pose["pelvis_progress"], pose["torso_progress"])
        self.assertNotEqual(compile_performance_frame(self.contract, 100)["channels"]["body_pose"]["settle_y_px"], 0.0)
        self.assertNotEqual(compile_performance_frame(self.contract, 104)["channels"]["body_pose"]["settle_y_px"], 0.0)
        self.assertEqual(compile_performance_frame(self.contract, 108)["channels"]["body_pose"]["settle_y_px"], 0.0)
        self.assertEqual(compile_performance_frame(self.contract, 109)["segment_id"], "STANDING_HOLD")

        with self.assertRaisesRegex(ValueError, "1 through 171"):
            compile_performance_frame(self.contract, 0)
        with self.assertRaisesRegex(ValueError, "1 through 171"):
            compile_performance_frame(self.contract, 172)

    def test_stand_progress_is_monotone_after_liftoff_and_camera_is_cubic(self) -> None:
        progress = [
            compile_performance_frame(self.contract, frame)["channels"]["body_pose"]["stand_progress"]
            for frame in range(70, 172)
        ]
        self.assertTrue(all(a <= b for a, b in zip(progress, progress[1:])))
        for frame in (1, 55, 71, 83, 96, 130, 171):
            camera = compile_performance_frame(self.contract, frame)["channels"]["camera"]
            self.assertGreaterEqual(camera["zoom"], 1.0)
            self.assertLessEqual(camera["zoom"], 1.012)
            self.assertEqual(camera["interpolation"], "ease_in_out_cubic")

    def test_contacts_encode_real_release_grasp_and_heel_toe_mechanics(self) -> None:
        seated = compile_performance_frame(self.contract, 70)
        lift = compile_performance_frame(self.contract, 71)
        release = compile_performance_frame(self.contract, 79)
        result = compile_performance_frame(self.contract, 171)

        self.assertTrue(seated["contacts"]["chair_seat"]["active"])
        self.assertFalse(lift["contacts"]["chair_seat"]["active"])
        self.assertTrue(lift["contacts"]["chair_hand"]["active"])
        self.assertFalse(release["contacts"]["chair_hand"]["active"])
        self.assertTrue(all(
            compile_performance_frame(self.contract, frame)["contacts"]["mug_hand"]["active"]
            for frame in range(1, 172)
        ))
        self.assertEqual(lift["contacts"]["left_boot"]["mode"], "toe_pivot")
        self.assertEqual(lift["contacts"]["right_boot"]["mode"], "toe_pivot")
        self.assertEqual(result["contacts"]["left_boot"]["mode"], "flat_support")
        self.assertEqual(result["contacts"]["right_boot"]["mode"], "flat_support")
        self.assertGreater(lift["contacts"]["left_boot"]["maximum_heel_travel_px"], 0.0)
        self.assertGreater(lift["contacts"]["right_boot"]["maximum_heel_travel_px"], 0.0)

    def test_center_of_mass_proxy_remains_inside_declared_active_support_region(self) -> None:
        regions = self.contract["performance_tracks"]["root_contact"]["support_regions"]
        for frame in range(1, 172):
            root = compile_performance_frame(self.contract, frame)["channels"]["root_contact"]
            region = regions[root["support_phase"]]
            x, y = root["center_of_mass_proxy"]
            self.assertLessEqual(region["x_interval"][0], x)
            self.assertLessEqual(x, region["x_interval"][1])
            self.assertLessEqual(region["y_interval"][0], y)
            self.assertLessEqual(y, region["y_interval"][1])

    def test_delivery_mechanical_and_audience_gates_cannot_be_collapsed(self) -> None:
        declarations = self.contract["gate_declarations"]
        self.assertEqual(
            set(declarations),
            {"delivery_integrity", "mechanical_integrity", "audience_quality"},
        )
        self.assertTrue(declarations["delivery_integrity"]["required_for_gate_a"])
        self.assertTrue(declarations["mechanical_integrity"]["required_for_gate_a"])
        audience = declarations["audience_quality"]
        self.assertFalse(audience["required_for_gate_a"])
        self.assertEqual(audience["status_before_gate_b"], "unevaluated")
        self.assertFalse(audience["may_be_inferred_from_delivery_or_mechanics"])
        self.assertNotIn("passed", audience)
        report = self.contract["report_contract"]
        self.assertEqual(
            report["required_top_level_sections"],
            ["delivery_integrity", "mechanical_integrity", "audience_quality"],
        )
        self.assertFalse(report["aggregate_quality_pass_allowed"])

    def test_render_entrypoint_declares_gate_a_media_boundary(self) -> None:
        signature = inspect.signature(render_deformable_performance_3q)
        self.assertEqual(list(signature.parameters)[:2], ["contract_path", "output_dir"])
        self.assertIn("ffmpeg", signature.parameters)
        self.assertIn("render_scale", signature.parameters)
        self.assertEqual(signature.parameters["ffmpeg"].default, "ffmpeg")
        self.assertEqual(signature.parameters["render_scale"].default, 1.0)

    def test_loader_rejects_tampered_sources_clock_and_false_audience_evidence(self) -> None:
        path = REPO_ROOT / "build" / "broken-deformable-performance-3q.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            tampered = copy.deepcopy(self.contract)
            tampered["accepted_sources"]["standing_endpoint"]["sha256"] = "0" * 64
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                load_deformable_performance_contract(path)

            bad_clock = copy.deepcopy(self.contract)
            bad_clock["output"]["frame_count"] = 170
            path.write_text(json.dumps(bad_clock), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "171-frame"):
                load_deformable_performance_contract(path)

            false_claim = copy.deepcopy(self.contract)
            false_claim["gate_declarations"]["audience_quality"]["passed"] = True
            path.write_text(json.dumps(false_claim), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "audience"):
                load_deformable_performance_contract(path)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
