from __future__ import annotations

import inspect
from pathlib import Path
import unittest

import numpy as np

from pipeline.cartoon_puppet_atlas_performance import (
    AtlasPerformanceRenderer,
    FPS,
    FRAME_COUNT,
    OUTPUT_SIZE,
    REVIEW_FRAMES,
    render_puppet_atlas_performance,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "concept/characters/june_oxley_puppet_atlas_v1.json"
SAMPLE_FRAMES = (1, 57, 70, 71, 78, 79, 95, 96, 109, 171)


class CartoonPuppetAtlasPerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.images = {}
        cls.details = {}
        with AtlasPerformanceRenderer(CONTRACT) as renderer:
            for frame in SAMPLE_FRAMES:
                image, detail = renderer.render_frame(frame)
                cls.images[frame] = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
                cls.details[frame] = detail
                image.close()

    def test_preview_delivery_clock_is_exact_and_half_resolution(self) -> None:
        self.assertEqual((FRAME_COUNT, FPS, OUTPUT_SIZE), (171, 30, (960, 540)))
        self.assertEqual(len(REVIEW_FRAMES), 24)
        for frame in SAMPLE_FRAMES:
            self.assertEqual(self.images[frame].shape, (540, 960, 3))
            self.assertEqual(self.images[frame].dtype, np.uint8)

    def test_every_sample_uses_the_phase29_semantic_interface_and_one_atlas(self) -> None:
        expected = {"body_pose", "root_contact", "hand_contact", "prop_pose", "camera", "atmosphere"}
        for detail in self.details.values():
            self.assertEqual(set(detail["semantic_channels"]), expected)
            self.assertEqual(detail["component_source_policy"], "immutable_atlas_only_no_corrective_swaps")
            self.assertEqual(len(detail["normalized_determinants"]), 14)
            self.assertEqual(len(detail["mapping_residuals_px"]), 14)

    def test_chair_occlusion_tracks_declared_seat_and_hand_release_frames(self) -> None:
        self.assertEqual(self.details[1]["chair_occlusion"], {"arm_applied": True, "seat_applied": True})
        self.assertEqual(self.details[70]["chair_occlusion"], {"arm_applied": True, "seat_applied": True})
        self.assertEqual(self.details[71]["chair_occlusion"], {"arm_applied": True, "seat_applied": False})
        self.assertEqual(self.details[78]["chair_occlusion"], {"arm_applied": True, "seat_applied": False})
        self.assertEqual(self.details[79]["chair_occlusion"], {"arm_applied": False, "seat_applied": False})

    def test_actual_rendered_contacts_include_feet_chair_hand_and_mug(self) -> None:
        expected = {"left_boot", "right_boot", "chair_hand", "mug_hand", "mug_center"}
        for frame, detail in self.details.items():
            evidence = detail["contact_evidence"]
            self.assertEqual(set(evidence), expected)
            for identifier in ("left_boot", "right_boot", "mug_hand", "mug_center"):
                self.assertTrue(evidence[identifier]["active"])
                self.assertIsNotNone(evidence[identifier]["rendered_centroid"])
                self.assertGreater(evidence[identifier]["roi_alpha_presence"], 0.0)
            self.assertEqual(evidence["chair_hand"]["active"], frame <= 78)

    def test_sampled_geometry_stays_positive_joined_and_single_component(self) -> None:
        for detail in self.details.values():
            self.assertGreater(min(detail["normalized_determinants"].values()), 0.0)
            self.assertTrue(np.isfinite(max(detail["joint_gaps_px"].values())))
            for metric in detail["contact_components"].values():
                self.assertEqual(metric["significant_count"], 1)
                self.assertGreaterEqual(metric["dominant_fraction"], 0.95)

    def test_phase22_compose_effects_and_camera_share_the_original_frame_clock(self) -> None:
        first = self.details[1]["compose_clock"]
        final = self.details[171]["compose_clock"]
        self.assertTrue(first["contact_shadow"])
        self.assertEqual(first["steam_time_seconds"], 0.0)
        self.assertEqual(first["light_breathe_time_seconds"], 0.0)
        self.assertEqual(first["camera_amount"], 0.0)
        self.assertEqual(final["steam_time_seconds"], 170 / 30)
        self.assertEqual(final["light_breathe_time_seconds"], 170 / 30)
        self.assertEqual(final["camera_amount"], 1.0)

    def test_render_entrypoint_has_explicit_output_and_ffmpeg_boundary(self) -> None:
        signature = inspect.signature(render_puppet_atlas_performance)
        self.assertEqual(list(signature.parameters)[:2], ["atlas_contract_path", "output_dir"])
        self.assertEqual(signature.parameters["ffmpeg"].default, "ffmpeg")
        with AtlasPerformanceRenderer(CONTRACT) as renderer:
            with self.assertRaisesRegex(ValueError, "1 through 171"):
                renderer.render_frame(0)
            with self.assertRaisesRegex(ValueError, "1 through 171"):
                renderer.render_frame(172)


if __name__ == "__main__":
    unittest.main()
