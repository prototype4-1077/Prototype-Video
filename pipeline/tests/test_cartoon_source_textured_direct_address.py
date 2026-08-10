from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path
import unittest

import numpy as np

from pipeline import cartoon_source_textured_direct_address as direct
from pipeline import cartoon_source_textured_face as phase34


class SourceTexturedDirectAddressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = direct.prepare_direct_address()

    def test_contract_is_canonical_hash_locked_to_candidate08(self) -> None:
        contract, path = direct.load_contract()
        self.assertEqual(
            direct._canonical_hash(contract),
            direct.EXPECTED_CONTRACT_CANONICAL_SHA256,
        )
        self.assertEqual(contract["locks"]["phase34_renderer"]["sha256"], phase34._sha256(phase34.REPO_ROOT / phase34.IMPLEMENTATION_RELATIVE_PATH))
        self.assertIn("candidate08", json.dumps(contract).lower())
        self.assertNotIn("candidate09", json.dumps(contract).lower())
        self.assertEqual(path, direct.REPO_ROOT / direct.CONTRACT_RELATIVE_PATH)

    def test_exact_clock_audio_and_semantic_tracks(self) -> None:
        prepared = self.prepared
        self.assertEqual(len(prepared.visemes), 228)
        self.assertEqual(len(prepared.expressions), 228)
        self.assertEqual(len(prepared.motion), 228)
        self.assertEqual(prepared.viseme_metadata["shapes"], list("ABCEFGHX"))
        self.assertEqual(direct._wave_probe(prepared.dialogue_path)["sample_count"], 364800)
        self.assertEqual(direct._wave_probe(prepared.mix_path)["channels"], 2)
        self.assertEqual(len(direct._blink_intervals(prepared.contract)), 2)

    def test_adapter_reproduces_accepted_phase34_key_pixels(self) -> None:
        prepared = self.prepared
        for shape, reference_frame in (("A", 22), ("F", 62), ("X", 16)):
            index = next(
                index
                for index, (viseme, expression) in enumerate(zip(prepared.visemes, prepared.expressions))
                if viseme["to_shape"] == shape
                and float(viseme["blend"]) >= 1.0
                and direct.production_blink_closure(prepared.contract, index + 1) == 0.0
            )
            actual, _ = direct.controlled_native_frame(
                prepared, prepared.visemes[index], 0.0,
            )
            expected, _ = phase34._native_frame(prepared.face, reference_frame)
            self.assertTrue(np.array_equal(actual, expected), shape)

        blink_index = next(
            index
            for index, (viseme, expression) in enumerate(zip(prepared.visemes, prepared.expressions))
            if viseme["to_shape"] == "X"
            and float(viseme["blend"]) >= 1.0
            and direct.production_blink_closure(prepared.contract, index + 1) == 1.0
        )
        actual, evidence = direct.controlled_native_frame(
            prepared,
            prepared.visemes[blink_index],
            1.0,
        )
        expected, _ = phase34._native_frame(prepared.face, 8)
        self.assertTrue(np.array_equal(actual, expected))
        self.assertEqual(evidence.blink_closure, 1.0)

    def test_adapter_rejects_unrepresentable_timing(self) -> None:
        with self.assertRaisesRegex(direct.SourceTexturedDirectAddressError, "not representable"):
            direct._synthetic_viseme_schedule(
                {"from_shape": "A", "to_shape": "B", "blend": 0.3},
                10,
            )

    def test_all_228_control_schedules_are_representable(self) -> None:
        for frame_number, viseme in enumerate(self.prepared.visemes, start=1):
            closure = direct.production_blink_closure(self.prepared.contract, frame_number)
            render_frame, _, _ = direct._synthetic_blink_schedule(closure)
            schedule = direct._synthetic_viseme_schedule(viseme, render_frame)
            self.assertLessEqual(schedule[0]["frame"], render_frame)
            self.assertGreaterEqual(schedule[-1]["frame"], render_frame)

    def test_composition_protects_face_from_shoulder_warp(self) -> None:
        source = inspect.getsource(direct.compose_direct_address_frame)
        shoulder = source.index('regions["shoulders"]')
        feature_overlay = source.index("frame.paste(face_frame")
        head = source.index('regions["head"]')
        camera = source.index("_camera_frame")
        self.assertLess(shoulder, feature_overlay)
        self.assertLess(feature_overlay, head)
        self.assertLess(head, camera)

    def test_preview_is_fail_closed_immutable_and_encode_free(self) -> None:
        contract = self.prepared.contract
        self.assertTrue(contract["failure_policy"]["immutable_output"])
        self.assertFalse(contract["failure_policy"]["encode_on_preview_pass_allowed"])
        self.assertNotIn("video_filename", contract["preview"])
        source = inspect.getsource(direct)
        tree = ast.parse(source)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertNotIn("subprocess", imported)
        self.assertNotIn("ffmpeg", source.lower())
        self.assertNotIn("Popen", source)
        preview_source = inspect.getsource(direct.write_unencoded_preview)
        self.assertLess(preview_source.index("if failed:"), preview_source.index("stage.replace(output)"))
        self.assertIn("verify_lossless_archive", preview_source)

    def test_measurement_domains_and_thresholds_are_preregistered(self) -> None:
        gates = self.prepared.contract["preencode_gates"]
        self.assertEqual(gates["accepted_candidate08_same_domain_maximum_source_pop"], 152.9947967529297)
        self.assertEqual(gates["maximum_native_face_temporal_excess_over_accepted_candidate08"], 0.01)
        self.assertEqual(gates["maximum_final_composed_face_adjacent_8x8_mean_delta"], 170.0)
        self.assertEqual(gates["required_audio_samples_per_frame"], 1600)
        self.assertEqual(gates["required_lossless_rgb_archive_verified_frames"], 228)
        source = inspect.getsource(direct.write_unencoded_preview)
        self.assertIn("phase34_lanczos_resampled_1920x1080_rgb_before_body_head_camera_or_atmosphere", source)
        self.assertIn("final_composed_1920x1080_rgb_before_encode", source)


if __name__ == "__main__":
    unittest.main()
