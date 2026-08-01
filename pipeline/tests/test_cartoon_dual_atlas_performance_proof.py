from __future__ import annotations

import inspect
from pathlib import Path
import unittest

import cv2
import numpy as np

from pipeline.cartoon_dual_atlas_performance_proof import (
    DualAtlasRenderer,
    TRANSITION_FRAMES,
    _transition_weight,
    load_seated_atlas_contract,
    render_dual_atlas_performance_proof,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "concept/characters/june_oxley_puppet_atlas_seated_v1.json"
SAMPLE_FRAMES = (1, 64, 70, 71, 78, 79, 83, 95, 96, 100)


class CartoonDualAtlasPerformanceProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.components, cls.component_count = load_seated_atlas_contract(CONTRACT)
        cls.images: dict[int, np.ndarray] = {}
        cls.details: dict[int, dict[str, object]] = {}
        with DualAtlasRenderer(CONTRACT) as renderer:
            cls.interface_ids = set(renderer.seated_by_id)
            cls.standing_ids = set(renderer.standing_by_id)
            for frame in SAMPLE_FRAMES:
                image, detail = renderer.render_frame(frame)
                cls.images[frame] = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
                cls.details[frame] = detail
                image.close()

    def test_seated_atlas_is_exactly_fourteen_one_to_one_components(self) -> None:
        self.assertEqual(self.component_count, 14)
        self.assertEqual(len(self.components), 14)
        self.assertEqual(len(self.interface_ids), 14)
        self.assertEqual(self.interface_ids, self.standing_ids)
        self.assertIn("right_hand_mug", self.interface_ids)
        self.assertNotIn("right_hand", self.interface_ids)
        self.assertNotIn("mug", self.interface_ids)

    def test_torso_center_mask_excludes_sleeves(self) -> None:
        torso = next(component for component in self.components if component.identifier == "torso")
        row = next(row for row in self.contract["components"] if row["id"] == "torso")
        self.assertEqual(len(row["center_mask_polygon"]), 8)
        self.assertGreater(np.count_nonzero(torso.rgba[:, :, 3]), 0)
        self.assertEqual(int(torso.rgba[0, 0, 3]), 0)
        self.assertEqual(int(torso.rgba[-1, -1, 3]), 0)

    def test_topology_repairs_are_bounded_to_the_failed_interfaces(self) -> None:
        repair = self.contract["topology_repairs"]
        self.assertEqual(repair["largest_component_source_cleanup"], ["right_forearm"])
        self.assertEqual(set(repair["joint_socket_extensions"]), {"left_upper_arm", "right_upper_arm"})
        right_forearm = next(component for component in self.components if component.identifier == "right_forearm")
        self.assertTrue(next(row for row in self.contract["components"] if row["id"] == "right_forearm")["retain_largest_alpha_component"])
        count, _, _, _ = cv2.connectedComponentsWithStats(
            np.asarray(right_forearm.rgba[:, :, 3] > 8, dtype=np.uint8), 8
        )
        self.assertEqual(count - 1, 1)

    def test_transition_weights_are_bounded_to_the_declared_action(self) -> None:
        self.assertEqual(_transition_weight(self.contract, 1), 0.0)
        self.assertEqual(_transition_weight(self.contract, 64), 0.0)
        self.assertEqual(_transition_weight(self.contract, 70), 0.0)
        self.assertGreater(_transition_weight(self.contract, 71), 0.0)
        self.assertLess(_transition_weight(self.contract, 95), 1.0)
        self.assertEqual(_transition_weight(self.contract, 96), 1.0)
        self.assertEqual(_transition_weight(self.contract, 100), 1.0)
        self.assertEqual(TRANSITION_FRAMES, tuple(range(64, 101)))

    def test_every_sample_renders_at_delivery_size_without_background_blending(self) -> None:
        for frame, image in self.images.items():
            with self.subTest(frame=frame):
                self.assertEqual(image.shape, (540, 960, 3))
                self.assertEqual(image.dtype, np.uint8)
                detail = self.details[frame]
                self.assertFalse(detail["background_blended"])
                self.assertTrue(detail["mug_hand_is_single_unit"])
                self.assertEqual(len(detail["aligned_alpha_iou"]), 14)
                self.assertEqual(len(detail["blended_part_components"]), 14)
                self.assertEqual(detail["blended_part_components"]["right_forearm"], 1)

    def test_chair_context_tracks_seat_and_hand_release(self) -> None:
        self.assertEqual(self.details[1]["chair_context"], {"arm_patch": True, "seat_patch": True})
        self.assertEqual(self.details[70]["chair_context"], {"arm_patch": True, "seat_patch": True})
        self.assertEqual(self.details[71]["chair_context"], {"arm_patch": True, "seat_patch": False})
        self.assertEqual(self.details[78]["chair_context"], {"arm_patch": True, "seat_patch": False})
        self.assertEqual(self.details[79]["chair_context"], {"arm_patch": False, "seat_patch": False})

    def test_mechanics_and_contacts_are_measured_from_rendered_parts(self) -> None:
        expected_contacts = {"left_boot", "right_boot", "chair_hand", "mug_hand", "mug_center"}
        for frame, detail in self.details.items():
            with self.subTest(frame=frame):
                self.assertGreater(detail["minimum_normalized_determinant"], 0.0)
                self.assertTrue(np.isfinite(max(detail["shoulder_knee_gaps_px"].values())))
                self.assertLessEqual(max(detail["shoulder_knee_gaps_px"].values()), self.contract["gates"]["maximum_shoulder_or_knee_gap_preview_px"])
                self.assertTrue(np.isfinite(max(detail["ankle_gaps_px"].values())))
                self.assertLessEqual(max(detail["ankle_gaps_px"].values()), self.contract["gates"]["maximum_ankle_gap_preview_px"])
                self.assertEqual(set(detail["contact_evidence"]), expected_contacts)
                self.assertGreater(np.count_nonzero(detail["character_alpha"]), 0)

    def test_render_entrypoint_has_explicit_ffmpeg_boundary(self) -> None:
        signature = inspect.signature(render_dual_atlas_performance_proof)
        self.assertEqual(list(signature.parameters)[:2], ["seated_contract_path", "output_dir"])
        self.assertEqual(signature.parameters["ffmpeg"].default, "ffmpeg")
        with DualAtlasRenderer(CONTRACT) as renderer:
            with self.assertRaisesRegex(ValueError, "frame 1 and frames 64 through 100"):
                renderer.render_frame(63)
            with self.assertRaisesRegex(ValueError, "frame 1 and frames 64 through 100"):
                renderer.render_frame(101)


if __name__ == "__main__":
    unittest.main()
