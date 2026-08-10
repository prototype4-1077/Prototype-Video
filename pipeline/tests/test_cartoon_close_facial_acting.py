from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from PIL import ImageChops

import pipeline.cartoon_close_facial_acting as phase33


class CloseFacialActingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_path = phase33.REPO_ROOT / phase33.CONTRACT_RELATIVE_PATH
        cls.contract = phase33.load_close_facial_acting_contract(cls.contract_path)
        cls.prepared = phase33.prepare_close_facial_acting(cls.contract_path)

    def test_complete_contract_and_every_dependency_are_hash_locked(self) -> None:
        self.assertEqual(
            phase33._canonical_hash(self.contract),
            "19c44426ec0caebe6d24fdafcd4f3092820391b469e95a49363e84c1443435ad",
        )
        for name, reference in self.contract["locks"].items():
            with self.subTest(name=name):
                path = (phase33.REPO_ROOT / reference["path"]).resolve()
                self.assertEqual(phase33._sha256(path), reference["sha256"])

    def test_phase32_machine_only_receipt_forbids_acceptance_promotion(self) -> None:
        promotion = self.contract["promotion_policy"]
        self.assertFalse(promotion["phase32_current_human_review_completed"])
        self.assertFalse(promotion["phase32_current_facial_performance_promotion_allowed"])
        self.assertFalse(promotion["accepted_delivery_publication_allowed"])
        self.assertEqual(
            promotion["audience_status"],
            "prototype_candidate_human_review_required",
        )

    def test_cross_view_face_paste_and_phase32_reconstruction_claim_are_forbidden(self) -> None:
        policy = self.contract["representation_policy"]
        self.assertFalse(policy["cross_view_face_paste_allowed"])
        self.assertFalse(policy["straight_on_atlas_pixels_allowed_in_phase32_head"])
        self.assertFalse(policy["close_view_adapter_is_phase32_face_reconstruction"])

    def test_contract_mutations_fail_closed_before_asset_preparation(self) -> None:
        for section, key, value in (
            ("promotion_policy", "accepted_delivery_publication_allowed", True),
            ("representation_policy", "cross_view_face_paste_allowed", True),
            ("delivery", "one_video_encode_without_retry", False),
            ("failure_policy", "automatic_reencode_allowed", True),
        ):
            changed = deepcopy(self.contract)
            changed[section][key] = value
            with self.subTest(section=section, key=key):
                with self.assertRaisesRegex(phase33.CloseFacialActingError, "complete Phase33 contract"):
                    phase33._validate_contract(changed)

    def test_audio_and_picture_share_exact_integer_sample_clock(self) -> None:
        clock = self.contract["clock"]
        self.assertEqual(clock["audio_samples_per_frame"], 1600)
        self.assertEqual(clock["audio_sample_count"], 228 * 1600)
        dialogue = phase33._wave_probe(
            phase33.REPO_ROOT / self.contract["locks"]["dialogue_audio"]["path"]
        )
        mix = phase33._wave_probe(
            phase33.REPO_ROOT / self.contract["locks"]["delivery_mix"]["path"]
        )
        self.assertEqual(dialogue["sample_count"], 364800)
        self.assertEqual(mix["sample_count"], 364800)
        self.assertEqual((dialogue["channels"], mix["channels"]), (1, 2))

    def test_cue_past_locked_audio_end_is_rejected_not_extended(self) -> None:
        source = phase33.REPO_ROOT / self.contract["locks"]["viseme_cues"]["path"]
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["mouthCues"][-1]["end"] = 7.61
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad-cues.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(phase33.CloseFacialActingError, "locked audio clock"):
                phase33._strict_viseme_plan(path, self.contract)

    def test_feature_scope_is_nonvacuous_and_preserves_stable_pixels(self) -> None:
        metrics = self.prepared.preflight_measurements
        self.assertGreaterEqual(metrics["stable_identity_pixel_count"], 150000)
        self.assertGreaterEqual(metrics["mouth_feature_mask_pixel_count"], 10000)
        self.assertGreaterEqual(metrics["expression_feature_mask_pixel_count"], 10000)
        self.assertEqual(
            metrics["maximum_changed_pixels_outside_declared_feature_support"],
            0,
        )

    def test_actual_patch_pixels_prove_bilateral_blink_and_mouth_motion(self) -> None:
        metrics = self.prepared.preflight_measurements
        self.assertGreater(metrics["left_blink_mean_absolute_delta"], 1.0)
        self.assertGreater(metrics["right_blink_mean_absolute_delta"], 1.0)
        self.assertGreaterEqual(metrics["distinct_registered_viseme_count"], 9)
        self.assertGreaterEqual(metrics["non_x_observed_frame_count"], 40)
        self.assertGreaterEqual(metrics["settled_x_frame_count"], 60)

    def test_two_authored_blinks_reopen_and_final_mouth_is_closed(self) -> None:
        states = [entry["to_state"] for entry in self.prepared.expressions]
        blink_runs = []
        in_run = False
        for index, state in enumerate(states, start=1):
            if state == "blink" and not in_run:
                blink_runs.append(index)
                in_run = True
            elif state != "blink":
                in_run = False
        self.assertEqual(len(blink_runs), 2)
        self.assertTrue(all(entry["to_shape"] == "X" for entry in self.prepared.visemes[167:]))

    def test_final_hold_locks_body_while_secondary_motion_remains_live(self) -> None:
        channels = ("head_x_px", "head_y_px", "head_tilt_deg", "shoulder_x_px", "breath_y_px")
        for entry in self.prepared.motion[201:]:
            self.assertTrue(all(entry[channel] == 0.0 for channel in channels))
        self.assertGreater(
            self.prepared.motion_metadata["secondary_motion"]["wind_chime"]["amplitude_px"],
            0.0,
        )

    def test_first_frame_uses_close_plate_not_old_mug_insert(self) -> None:
        frame = phase33.compose_close_facial_acting_frame(self.prepared, 1)
        old_contract = deepcopy(self.prepared.sources["contract"])
        old_contract["sequence"]["offer_insert_end_frame"] = 45
        sources = dict(self.prepared.sources)
        sources["contract"] = old_contract
        insert_frame = phase33.compose_resolution_frame(
            sources,
            self.prepared.visemes[0],
            self.prepared.expressions[0],
            self.prepared.motion[0],
            frame_index=1,
            fps=30,
            secondary=self.prepared.motion_metadata["secondary_motion"],
        )
        self.assertIsNotNone(ImageChops.difference(frame, insert_frame).getbbox())

    def test_nan_gate_measurement_fails_closed(self) -> None:
        row = phase33._gate("adversarial.nan", float("nan"), ">=", 0.0)
        self.assertFalse(row["passed"])

    def test_preflight_failure_never_calls_video_encoder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate"
            with mock.patch.object(
                phase33,
                "prepare_close_facial_acting",
                side_effect=phase33.CloseFacialActingError("preflight"),
            ), mock.patch.object(phase33, "_encode_once") as encoder:
                with self.assertRaisesRegex(phase33.CloseFacialActingError, "preflight"):
                    phase33.render_close_facial_acting(self.contract_path, output)
                encoder.assert_not_called()
                self.assertFalse(output.exists())

    def test_decoded_failure_does_not_retry_or_publish_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate"
            dummy_prepared = SimpleNamespace(
                contract=self.contract,
                audio_path=Path("mix.wav"),
            )

            def fake_encode(_prepared, stage, *, ffmpeg):
                video = stage / self.contract["delivery"]["video_filename"]
                video.write_bytes(b"encoded-once")
                return video, {}

            failed_metrics = {
                "full_decode": False,
                "decoded_frame_count": 0,
                "review_frame_count": 0,
                "minimum_full_frame_psnr_db": 0.0,
                "minimum_face_psnr_db": 0.0,
                "minimum_face_ssim": 0.0,
                "minimum_eye_psnr_db": 0.0,
                "minimum_mouth_psnr_db": 0.0,
                "minimum_encoded_laplacian_variance": 0.0,
                "width": 0,
                "height": 0,
                "fps": 0.0,
                "video_codec": None,
                "pixel_format": None,
                "video_stream_count": 0,
                "audio_stream_count": 0,
                "audio_codec": None,
                "audio_sample_rate": 0,
                "audio_channels": 0,
                "duration_seconds": 0.0,
            }
            with mock.patch.object(phase33, "prepare_close_facial_acting", return_value=dummy_prepared), mock.patch.object(
                phase33, "_executable", return_value="tool"
            ), mock.patch.object(phase33, "_encode_once", side_effect=fake_encode) as encoder, mock.patch.object(
                phase33, "_decode_and_audit", return_value=(failed_metrics, {})
            ):
                with self.assertRaisesRegex(phase33.CloseFacialActingError, "decoded delivery gates"):
                    phase33.render_close_facial_acting(self.contract_path, output)
            self.assertEqual(encoder.call_count, 1)
            self.assertFalse(output.exists())
            self.assertTrue((Path(directory) / "candidate-rejected").exists())


if __name__ == "__main__":
    unittest.main()
