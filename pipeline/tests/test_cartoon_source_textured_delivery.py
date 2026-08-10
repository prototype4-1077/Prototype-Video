from __future__ import annotations

import inspect
import json
from pathlib import Path
import tempfile
import types
import unittest

import pipeline.cartoon_source_textured_delivery as delivery


class SourceTexturedDeliveryTests(unittest.TestCase):
    def test_receipt_is_exactly_bound_to_contract_and_claude_approval(self) -> None:
        contract = delivery.phase34.load_contract()
        receipt_path = delivery.REPO_ROOT / delivery.RECEIPT_RELATIVE_PATH
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["phase"], contract["phase"])
        self.assertEqual(delivery._sha256(receipt_path), delivery.EXPECTED_RECEIPT_RAW_SHA256)
        self.assertEqual(receipt["manifest_lf_normalized_sha256"], delivery.EXPECTED_MANIFEST_LF_SHA256)
        self.assertEqual(receipt["archive_sha256"], delivery.EXPECTED_ARCHIVE_SHA256)
        self.assertEqual(receipt["contract_canonical_sha256"], delivery.EXPECTED_CONTRACT_CANONICAL_SHA256)
        self.assertEqual(receipt["renderer_sha256"], delivery.EXPECTED_RENDERER_SHA256)
        self.assertTrue(receipt["encode_authorization"]["source_must_be_exact_archived_rgb_frames"])
        self.assertEqual(receipt["encode_authorization"]["maximum_video_encoder_processes"], 1)
        self.assertFalse(receipt["encode_authorization"]["automatic_retry_allowed"])
        self.assertFalse(receipt["encode_authorization"]["audio_allowed"])

    def test_authorized_archive_is_exact_candidate08_and_all_frames_match(self) -> None:
        authorized = delivery.load_authorized_archive()
        self.assertEqual(authorized.archive_header["frame_count"], 96)
        self.assertEqual(len(authorized.frames), 96)
        self.assertEqual(
            [delivery._raw_frame_hash(frame) for frame in authorized.frames],
            [entry["rgb_sha256"] for entry in authorized.manifest["frames"]],
        )
        self.assertTrue(all(gate["passed"] for gate in authorized.manifest["preflight_gates"]))

    def test_delivery_never_invokes_renderer_and_exposes_no_output_or_retry_override(self) -> None:
        source = inspect.getsource(delivery)
        self.assertNotIn("compose_source_textured_frame", source)
        self.assertNotIn("prepare_source_textured_face", source)
        self.assertNotIn("_native_frame", source)
        self.assertEqual(source.count("subprocess.Popen("), 1)
        signature = inspect.signature(delivery.render_authorized_proof)
        self.assertEqual(set(signature.parameters), {"ffmpeg", "ffprobe"})
        self.assertTrue(all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in signature.parameters.values()))

    def test_contract_pins_immutable_attempt_one_destination(self) -> None:
        contract = delivery.phase34.load_contract()
        path = delivery._delivery_output_path(contract)
        self.assertEqual(path.name, "phase34-source-textured-visemes-proof-v1")
        self.assertEqual(contract["delivery"]["attempt_version"], 1)
        self.assertTrue(contract["delivery"]["one_video_encode_without_retry"])
        self.assertFalse(contract["failure_policy"]["automatic_reencode_allowed"])

    def test_attempt_claim_is_exclusive_and_durable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt = root / "receipt.json"
            receipt.write_text("{}\n", encoding="utf-8")
            authorized = types.SimpleNamespace(receipt_path=receipt)
            output = root / "proof-v1"
            claim = delivery._claim_attempt(output, authorized)
            self.assertTrue(claim.is_file())
            with self.assertRaises(delivery.SourceTexturedDeliveryError):
                delivery._claim_attempt(output, authorized)
            self.assertTrue(claim.is_file())
        render_source = inspect.getsource(delivery.render_authorized_proof)
        self.assertIn("claim_created = False", render_source)
        self.assertIn("claim_created = True", render_source)
        self.assertIn("if claim_created:", render_source)
        self.assertIn("except BaseException as exc:", render_source)

    def test_interrupted_claimed_attempt_is_preserved_as_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "partial"
            rejected = root / "rejected"
            stage.mkdir()
            (stage / "ffmpeg-stderr-v1.txt").write_text("interrupted\n", encoding="utf-8")
            delivery._preserve_rejected(
                stage,
                rejected,
                KeyboardInterrupt(),
                True,
                {"encoding_process_count": 1, "encoder_return_code": None},
            )
            self.assertFalse(stage.exists())
            self.assertTrue(rejected.is_dir())
            failure = json.loads((rejected / "failure-v1.json").read_text(encoding="utf-8"))
            self.assertEqual(failure["status"], "single_encode_attempt_rejected_no_retry_allowed")
            self.assertEqual(failure["error_type"], "KeyboardInterrupt")
            self.assertEqual(failure["attempt"]["encoding_process_count"], 1)

    def test_decoded_gates_accept_exact_delivery_and_reject_a_failed_metric(self) -> None:
        contract = delivery.phase34.load_contract()
        metrics = {
            "decoded_frame_count": 96,
            "worst_full_frame_psnr_db": 40.0,
            "worst_face_psnr_db": 39.0,
            "worst_face_ssim": 0.98,
            "worst_eye_psnr_db": 39.0,
            "worst_mouth_psnr_db": 39.0,
            "minimum_encoded_laplacian_variance": 81.0,
            "maximum_decoded_adjacent_face_8x8_mean_delta": 149.0,
        }
        probe = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "pix_fmt": "yuv420p",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "24/1",
                "avg_frame_rate": "24/1",
                "nb_frames": "96",
                "nb_read_frames": "96",
                "start_time": "0.000000",
                "duration": "4.000000",
            }],
            "format": {"duration": "4.000000"},
        }
        gates = delivery._decoded_gates(contract, metrics, probe)
        self.assertEqual(len(gates), 22)
        self.assertTrue(all(gate["passed"] for gate in gates))
        failed = dict(metrics)
        failed["worst_mouth_psnr_db"] = 37.99
        failed_gates = delivery._decoded_gates(contract, failed, probe)
        self.assertFalse(next(gate for gate in failed_gates if gate["name"] == "all_frame_mouth_psnr")["passed"])

    def test_decoded_gates_reject_nonfinite_and_extra_streams(self) -> None:
        contract = delivery.phase34.load_contract()
        metrics = {
            "decoded_frame_count": 96,
            "worst_full_frame_psnr_db": float("nan"),
            "worst_face_psnr_db": 39.0,
            "worst_face_ssim": 0.98,
            "worst_eye_psnr_db": 39.0,
            "worst_mouth_psnr_db": 39.0,
            "minimum_encoded_laplacian_variance": 81.0,
            "maximum_decoded_adjacent_face_8x8_mean_delta": 149.0,
        }
        probe = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p", "width": 1920, "height": 1080, "r_frame_rate": "24/1", "avg_frame_rate": "24/1", "nb_frames": "96", "nb_read_frames": "96", "start_time": "0", "duration": "4"},
                {"codec_type": "subtitle"},
            ],
            "format": {"duration": "4"},
        }
        gates = delivery._decoded_gates(contract, metrics, probe)
        self.assertFalse(next(gate for gate in gates if gate["name"] == "all_frame_full_psnr")["passed"])
        self.assertFalse(next(gate for gate in gates if gate["name"] == "no_other_streams")["passed"])


if __name__ == "__main__":
    unittest.main()
