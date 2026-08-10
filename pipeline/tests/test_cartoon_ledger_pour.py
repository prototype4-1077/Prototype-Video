from __future__ import annotations

import ast
import copy
import gzip
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_ledger_pour as ledger


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / ledger.CONTRACT_RELATIVE_PATH


def _phase35_archive(path: Path, frames: list[np.ndarray], hashes: list[dict[str, object]]) -> dict[str, object]:
    shape = frames[0].shape
    header = {
        "format": ledger.PHASE35_ARCHIVE_FORMAT,
        "width": shape[1],
        "height": shape[0],
        "channels": shape[2],
        "frame_count": len(frames),
        "frame_bytes": int(np.prod(shape)),
        "xor_seed": "all_zero_rgb24_frame",
    }
    previous = np.zeros(shape, dtype=np.uint8)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as archive:
            archive.write(json.dumps(header, sort_keys=True, separators=(",", ":")).encode() + b"\n")
            for frame in frames:
                archive.write(np.bitwise_xor(frame, previous).tobytes())
                previous = frame
    return header


def _phase36_archive(path: Path, frames: list[np.ndarray]) -> list[dict[str, object]]:
    shape = frames[0].shape
    header = {
        "format": ledger.ARCHIVE_FORMAT,
        "width": shape[1],
        "height": shape[0],
        "channels": shape[2],
        "frame_count": len(frames),
        "frame_bytes": int(np.prod(shape)),
        "xor_seed": "all_zero_rgb24_frame",
        "contract_canonical_sha256": "test-contract",
        "hard_cut_output_frames": [2],
    }
    hashes = [
        {"frame": index, "rgb_sha256": ledger._raw_frame_hash(frame)}
        for index, frame in enumerate(frames, start=1)
    ]
    previous = np.zeros(shape, dtype=np.uint8)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as archive:
            archive.write(json.dumps(header, sort_keys=True, separators=(",", ":")).encode() + b"\n")
            for frame in frames:
                archive.write(np.bitwise_xor(frame, previous).tobytes())
                previous = frame
    return hashes


class CartoonLedgerPourTests(unittest.TestCase):
    def test_contract_locks_exact_three_shot_picture_and_audio_clock(self) -> None:
        contract = ledger.load_contract()
        self.assertEqual(contract["clock"]["frame_count"], 303)
        self.assertEqual(contract["clock"]["audio_sample_count"], 484800)
        self.assertEqual(contract["clock"]["audio_samples_per_frame"], 1600)
        self.assertEqual(
            [(shot["output_frames"], shot["source_frames"]) for shot in contract["shots"]],
            [([1, 75], [112, 186]), ([76, 237], [1, 162]), ([238, 303], [163, 228])],
        )
        self.assertEqual(contract["edit"]["hard_cut_output_frames"], [76, 238])
        self.assertFalse(contract["failure_policy"]["encode_allowed"])

    def test_contract_canonical_hash_and_every_repository_lock_match(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(ledger._canonical_hash(contract), ledger.EXPECTED_CONTRACT_CANONICAL_SHA256)
        for reference in contract["locks"].values():
            self.assertEqual(ledger._lock_hash(reference), reference["sha256"])

    def test_contract_rejects_lock_drift(self) -> None:
        with patch("pipeline.cartoon_ledger_pour._lock_hash", return_value="0" * 64):
            with self.assertRaisesRegex(ledger.LedgerPourError, "locked phase23_contract"):
                ledger.load_contract()

    def test_phase35_attempt_review_requires_exact_locked_receipt_and_artifact_hashes(self) -> None:
        contract = copy.deepcopy(ledger.load_contract())
        gate = contract["phase35_attempt_review_gate"]
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            reviews = temporary_root / "collab"
            reviews.mkdir()
            review = reviews / "CLAUDE_REVIEW_TEST.md"
            attempt_directory = reviews / "phase35_candidate_03_encode_attempt_01"
            attempt_directory.mkdir()
            artifacts = {
                "video_filename": ("proof.mp4", b"video"),
                "failure_receipt_filename": ("failure.json", b"failure"),
                "attempt_claim_filename": ("claim.json", b"claim"),
            }
            for field, (name, payload) in artifacts.items():
                gate[field] = name
                (attempt_directory / name).write_bytes(payload)
            gate["attempt_directory"] = "collab/phase35_candidate_03_encode_attempt_01"
            gate["required_video_sha256"] = hashlib.sha256(b"video").hexdigest()
            gate["required_failure_receipt_sha256"] = hashlib.sha256(b"failure").hexdigest()
            gate["required_attempt_claim_sha256"] = hashlib.sha256(b"claim").hexdigest()
            contract["locks"]["phase35_attempt_review"] = {
                "path": "collab/CLAUDE_REVIEW_TEST.md",
                "hash_domain": "lf_normalized_text",
                "sha256": "",
            }

            def set_review(text: str) -> None:
                review.write_text(text, encoding="utf-8")
                normalized = review.read_bytes().replace(b"\r\n", b"\n")
                contract["locks"]["phase35_attempt_review"]["sha256"] = hashlib.sha256(normalized).hexdigest()

            set_review("Please provide " + gate["required_verdict"] + "\n")
            with patch.object(ledger, "REPO_ROOT", temporary_root):
                self.assertIsNone(ledger._phase35_attempt_review(contract))
                set_review("## Verdict: " + gate["required_verdict"] + "\n")
                self.assertIsNone(ledger._phase35_attempt_review(contract))
                set_review(
                    "## Verdict: " + gate["required_verdict"] + "\n"
                    + gate["required_integrity_attestations"][0] + "\n"
                    + gate["required_integrity_attestations"][1] + "\n"
                )
                receipt = ledger._phase35_attempt_review(contract)
                self.assertIsNotNone(receipt)
                self.assertEqual(receipt["path"], "collab/CLAUDE_REVIEW_TEST.md")
                self.assertEqual(receipt["sha256"], contract["locks"]["phase35_attempt_review"]["sha256"])
                snapshot = review.read_bytes()
                with patch.object(Path, "read_bytes", return_value=snapshot) as read_bytes:
                    same_snapshot_receipt = ledger._phase35_attempt_review(contract)
                self.assertEqual(same_snapshot_receipt, receipt)
                self.assertEqual(read_bytes.call_count, 1)
                review.write_text("mutated", encoding="utf-8")
                with self.assertRaisesRegex(ledger.LedgerPourError, "receipt SHA-256"):
                    ledger._phase35_attempt_review(contract)
                set_review(
                    gate["required_verdict_field"] + " " + gate["forbidden_verdict"] + "\n"
                    + gate["required_integrity_attestations"][0] + "\n"
                    + gate["required_integrity_attestations"][1] + "\n"
                )
                self.assertIsNone(ledger._phase35_attempt_review(contract))

    def test_builder_refuses_missing_attempt_review_before_resolving_output_or_stage(self) -> None:
        with patch("pipeline.cartoon_ledger_pour.load_contract", return_value={}), patch(
            "pipeline.cartoon_ledger_pour._phase36_candidate01_rejection", return_value=None
        ), patch(
            "pipeline.cartoon_ledger_pour._phase35_attempt_review", return_value=None
        ), patch("pipeline.cartoon_ledger_pour._output_path") as output_path:
            with self.assertRaisesRegex(ledger.LedgerPourError, "blocked pending Claude"):
                ledger.write_unencoded_preview()
        output_path.assert_not_called()

    def test_builder_refuses_rejected_candidate01_before_review_or_output_resolution(self) -> None:
        rejection = {
            "verdict": "PHASE36_CANDIDATE01_REJECTED_AUDIO_CONTINUITY_NEW_BINDING_REQUIRED",
        }
        with patch("pipeline.cartoon_ledger_pour.load_contract", return_value={}), patch(
            "pipeline.cartoon_ledger_pour._phase36_candidate01_rejection", return_value=rejection
        ), patch("pipeline.cartoon_ledger_pour._phase35_attempt_review") as attempt_review, patch(
            "pipeline.cartoon_ledger_pour._output_path"
        ) as output_path:
            with self.assertRaisesRegex(ledger.LedgerPourError, "immutable and promotion-rejected"):
                ledger.write_unencoded_preview(development_label="candidate-02")
        attempt_review.assert_not_called()
        output_path.assert_not_called()

    def test_builder_cleans_stage_when_a_production_path_step_fails(self) -> None:
        contract = ledger.load_contract()
        receipt = {"path": "collab/CLAUDE_REVIEW_TEST.md", "sha256": "a", "verdict": "allowed"}
        state = {
            "self": {
                "contract_raw_sha256": "raw",
                "contract_canonical_sha256": ledger.EXPECTED_CONTRACT_CANONICAL_SHA256,
                "implementation_sha256": "implementation",
            },
            "locked": {},
            "external": {},
            "phase23_runtime_assets": {},
            "phase35_attempt_review": receipt,
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "phase36-test"
            stage = output.parent / f".{output.name}.stage"
            with patch("pipeline.cartoon_ledger_pour.load_contract", return_value=contract), patch(
                "pipeline.cartoon_ledger_pour._phase36_candidate01_rejection", return_value=None
            ), patch(
                "pipeline.cartoon_ledger_pour._phase35_attempt_review", return_value=receipt
            ), patch("pipeline.cartoon_ledger_pour._output_path", return_value=output), patch(
                "pipeline.cartoon_ledger_pour._capture_execution_state", return_value=state
            ), patch("pipeline.cartoon_ledger_pour._phase35_manifest", return_value={}), patch(
                "pipeline.cartoon_ledger_pour._Sheet"
            ), patch("pipeline.cartoon_ledger_pour._CropSheet"), patch(
                "pipeline.cartoon_ledger_pour._prepare_pour",
                side_effect=ledger.LedgerPourError("injected production-path failure"),
            ):
                with self.assertRaisesRegex(ledger.LedgerPourError, "injected production-path failure"):
                    ledger.write_unencoded_preview()
            self.assertFalse(output.exists())
            self.assertFalse(stage.exists())

    def test_shot_validator_rejects_gap_retime_and_duplicate(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken = copy.deepcopy(contract)
        broken["shots"][1]["output_frames"][0] = 77
        with self.assertRaisesRegex(ledger.LedgerPourError, "ordered and contiguous"):
            ledger._validate_shots(broken)
        broken = copy.deepcopy(contract)
        broken["shots"][2]["source_frames"][0] = 162
        with self.assertRaisesRegex(ledger.LedgerPourError, "implicitly retimes"):
            ledger._validate_shots(broken)
        broken = copy.deepcopy(contract)
        broken["shots"][2]["source_frames"] = [97, 162]
        with self.assertRaisesRegex(ledger.LedgerPourError, "duplicated"):
            ledger._validate_shots(broken)

    def test_review_contract_covers_both_cuts_and_complete_magnified_blink(self) -> None:
        contract = ledger.load_contract()
        cuts = set(contract["review"]["cut_review_frames"])
        self.assertEqual(cuts, set(range(69, 83)) | set(range(232, 246)))
        compassion = set(contract["review"]["compassion_review_frames"])
        self.assertTrue(set(range(244, 253)).issubset(compassion))
        self.assertEqual(contract["review"]["full_resolution_review_frames"], [75, 76, 237, 238, 248])
        self.assertIn("blink_eye_stress_sheet_filename", contract["review"])

    def test_phase23_slice_retains_complete_liquid_envelope_and_stable_endpoints(self) -> None:
        contract, _, _ = ledger.pour.load_pour_layer_contract(
            REPO_ROOT / "concept/style_frames/june_golden_scene_gs060_layered_pour_v1.json"
        )
        first = ledger.pour.timeline_entry_for_frame(contract["timeline"], 112)
        entry_smear = ledger.pour.timeline_entry_for_frame(contract["timeline"], 127)
        exit_smear = ledger.pour.timeline_entry_for_frame(contract["timeline"], 185)
        last = ledger.pour.timeline_entry_for_frame(contract["timeline"], 186)
        self.assertEqual((first["type"], first["pose_id"]), ("pose", "POSE_55_PRE_POUR"))
        self.assertEqual((entry_smear["type"], exit_smear["type"]), ("smear", "smear"))
        self.assertEqual((last["type"], last["pose_id"]), ("pose", "POSE_55_PRE_POUR"))
        phases = [ledger.pour.liquid_state(contract["liquid"], frame)["phase"] for frame in range(112, 187)]
        self.assertEqual(phases[16:24], ["onset"] * 8)
        self.assertEqual(phases[24:65], ["continuous"] * 41)
        self.assertEqual(phases[65:73], ["taper"] * 8)

    def test_phase23_picture_slice_and_phase26_audio_slice_share_master_clock(self) -> None:
        contract = ledger.load_contract()
        picture_start, picture_end = contract["shots"][0]["source_frames"]
        audio_start, audio_end = contract["audio"]["pour_segment"]["global_source_frames"]
        self.assertEqual(audio_start - picture_start, 678)
        self.assertEqual(audio_end - picture_end, 678)
        self.assertEqual((picture_end - picture_start) + 1, 75)
        self.assertEqual((audio_end - audio_start) + 1, 75)

    def test_compassion_camera_inherits_phase21_motion_then_locks_27_frames(self) -> None:
        camera = ledger.load_contract()["shots"][2]["camera"]
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        frame[180:620, 500:870] = (111, 77, 43)
        start, start_meta = ledger.compassion_camera(frame, camera, 163)
        end, end_meta = ledger.compassion_camera(frame, camera, 201)
        locked, locked_meta = ledger.compassion_camera(frame, camera, 228)
        self.assertEqual(start.shape, frame.shape)
        self.assertAlmostEqual(start_meta["zoom"], 1.5)
        self.assertAlmostEqual(end_meta["zoom"], 1.58)
        self.assertEqual(end_meta["crop_xyxy"], locked_meta["crop_xyxy"])
        self.assertTrue(locked_meta["camera_locked"])
        self.assertGreaterEqual(locked_meta["minimum_face_edge_margin_px"], 90)
        self.assertTrue(np.array_equal(end, locked))

    def test_all_66_compassion_camera_states_are_monotonic_then_lock_with_safe_face_margin(self) -> None:
        camera = ledger.load_contract()["shots"][2]["camera"]
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        rows = [ledger.compassion_camera(frame, camera, source)[1] for source in range(163, 229)]
        zooms = [float(row["zoom"]) for row in rows]
        self.assertTrue(all(first <= second for first, second in zip(zooms, zooms[1:])))
        self.assertEqual(sum(bool(row["camera_locked"]) for row in rows), 27)
        self.assertEqual(len({tuple(row["crop_xyxy"]) for row in rows[39:]}), 1)
        self.assertGreaterEqual(min(int(row["minimum_face_edge_margin_px"]) for row in rows), 90)
        multishot = json.loads((REPO_ROOT / "concept/style_frames/june_golden_scene_multishot_v1.json").read_text())
        inherited = next(shot["camera"] for shot in multishot["shots"] if shot["id"].startswith("GS050_"))
        for key in ("start_zoom", "end_zoom", "focus_start", "focus_end", "easing"):
            self.assertEqual(camera[key], inherited[key])

    def test_compassion_camera_is_deterministic_and_rejects_wrong_geometry(self) -> None:
        camera = ledger.load_contract()["shots"][2]["camera"]
        frame = np.arange(1080 * 1920 * 3, dtype=np.uint32).astype(np.uint8).reshape(1080, 1920, 3)
        first, first_meta = ledger.compassion_camera(frame, camera, 177)
        second, second_meta = ledger.compassion_camera(frame, camera, 177)
        self.assertTrue(np.array_equal(first, second))
        self.assertEqual(first_meta, second_meta)
        with self.assertRaisesRegex(ledger.LedgerPourError, "1920x1080"):
            ledger.compassion_camera(frame[:100], camera, 177)

    def test_phase35_archive_iterator_round_trips_and_rejects_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "phase35.gz"
            full = np.zeros((1080, 1920, 3), dtype=np.uint8)
            full_hashes = [{"frame": 1, "rgb_sha256": ledger._raw_frame_hash(full)}]
            header = _phase35_archive(archive, [full], full_hashes)
            rows = list(ledger.iter_phase35_frames(archive, full_hashes, expected_header=header))
            self.assertEqual(len(rows), 1)
            broken = copy.deepcopy(full_hashes)
            broken[0]["rgb_sha256"] = "0" * 64
            with self.assertRaisesRegex(ledger.LedgerPourError, "RGB SHA-256"):
                list(ledger.iter_phase35_frames(archive, broken, expected_header=header))

    def test_phase35_archive_rejects_trailing_payload(self) -> None:
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        hashes = [{"frame": 1, "rgb_sha256": ledger._raw_frame_hash(frame)}]
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "phase35.gz"
            header = {
                "format": ledger.PHASE35_ARCHIVE_FORMAT, "width": 1920, "height": 1080,
                "channels": 3, "frame_count": 1, "frame_bytes": frame.size,
                "xor_seed": "all_zero_rgb24_frame",
            }
            with gzip.open(archive, "wb") as stream:
                stream.write(json.dumps(header).encode() + b"\n")
                stream.write(frame.tobytes())
                stream.write(b"x")
            with self.assertRaisesRegex(ledger.LedgerPourError, "trailing payload"):
                list(ledger.iter_phase35_frames(archive, hashes, expected_header=header))

    def test_output_archive_verifier_round_trips_and_rejects_trailing_payload(self) -> None:
        frames = [
            np.zeros((4, 6, 3), dtype=np.uint8),
            np.arange(72, dtype=np.uint8).reshape(4, 6, 3),
        ]
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "phase36.gz"
            hashes = _phase36_archive(archive, frames)
            self.assertEqual(ledger._verify_output_archive(
                archive,
                hashes,
                expected_shape=(4, 6, 3),
                expected_contract_sha256="test-contract",
                expected_hard_cuts=[2],
            ), 2)
            with gzip.open(archive, "ab") as stream:
                stream.write(b"x")
            with self.assertRaisesRegex(ledger.LedgerPourError, "trailing payload"):
                ledger._verify_output_archive(
                    archive,
                    hashes,
                    expected_shape=(4, 6, 3),
                    expected_contract_sha256="test-contract",
                    expected_hard_cuts=[2],
                )

    def test_output_archive_verifier_rejects_header_metadata_drift(self) -> None:
        frames = [np.zeros((4, 6, 3), dtype=np.uint8)]
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "phase36.gz"
            hashes = _phase36_archive(archive, frames)
            with gzip.open(archive, "rb") as source:
                header = json.loads(source.readline().decode("utf-8"))
                payload = source.read()
            header["xor_seed"] = "wrong"
            with gzip.open(archive, "wb") as destination:
                destination.write(json.dumps(header, sort_keys=True, separators=(",", ":")).encode() + b"\n")
                destination.write(payload)
            with self.assertRaisesRegex(ledger.LedgerPourError, "archive header"):
                ledger._verify_output_archive(
                    archive,
                    hashes,
                    expected_shape=(4, 6, 3),
                    expected_contract_sha256="test-contract",
                    expected_hard_cuts=[2],
                )

    def test_pcm24_round_trip_and_exact_audio_bridge(self) -> None:
        samples = np.array([[-8388607, 8388607], [-1, 1], [0, 0]], dtype=np.int32)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tiny.wav"
            ledger._write_pcm24_wave(path, samples, 48000)
            decoded, probe = ledger._read_pcm24_wave(path)
            self.assertTrue(np.array_equal(decoded, samples))
            self.assertEqual(probe["sample_count"], 3)
            mix_path = Path(directory) / "phase36.wav"
            report = ledger.build_exact_audio(ledger.load_contract(), mix_path)
            self.assertEqual(report["probe"]["sample_count"], 484800)
            self.assertEqual(report["phase36_bit_exact_scalar_samples"], 969600)
            self.assertEqual(report["phase33_bit_exact_scalar_samples"], 729600)
            self.assertEqual(report["phase26_stem_array_hash_mismatches"], 0)
            self.assertLessEqual(report["boundary_step"], 0.01)
            self.assertLessEqual(report["peak_dbfs"], -1.0)

    def test_pcm_readback_rejects_one_corrupted_pour_prefix_sample(self) -> None:
        intended = np.zeros((484800, 2), dtype=np.int32)
        decoded = intended.copy()
        decoded[1000, 0] = 1
        probe = {
            "sample_rate": 48000,
            "channels": 2,
            "bits_per_sample": 24,
            "sample_count": 484800,
            "data_bytes": 2908800,
            "data_sha256": "not-relevant-to-array-comparison",
        }
        with self.assertRaisesRegex(ledger.LedgerPourError, "exact channel values"):
            ledger._verify_pcm24_readback(decoded, intended, probe)

    def test_execution_state_diff_names_self_and_runtime_asset_mutations(self) -> None:
        initial = {
            "self": {"contract_raw_sha256": "a", "implementation_sha256": "b"},
            "phase23_runtime_assets": {"background": "c", "pose_POSE_55": "d"},
        }
        changed = copy.deepcopy(initial)
        changed["self"]["implementation_sha256"] = "changed"
        changed["phase23_runtime_assets"]["background"] = "changed"
        self.assertEqual(
            ledger._execution_state_mismatches(initial, changed),
            ["phase23_runtime_assets.background", "self.implementation_sha256"],
        )
        with self.assertRaisesRegex(ledger.LedgerPourError, "prepublication"):
            ledger._assert_execution_state(initial, changed, "prepublication")

    def test_execution_state_capture_reparses_and_rejects_stale_receipt(self) -> None:
        contract = ledger.load_contract()
        original = {"path": "collab/CLAUDE_REVIEW.md", "sha256": "original", "verdict": "allowed"}
        changed = {"path": "collab/CLAUDE_REVIEW.md", "sha256": "changed", "verdict": "allowed"}
        with patch("pipeline.cartoon_ledger_pour._phase35_attempt_review", return_value=changed):
            with self.assertRaisesRegex(ledger.LedgerPourError, "authorization receipt"):
                ledger._capture_execution_state(contract, CONTRACT_PATH, original)
        with patch("pipeline.cartoon_ledger_pour._phase35_attempt_review", return_value=None):
            with self.assertRaisesRegex(ledger.LedgerPourError, "disappeared or was blocked"):
                ledger._capture_execution_state(contract, CONTRACT_PATH, original)

    def test_phase35_manifest_binds_contract_archive_and_archived_implementation(self) -> None:
        contract = ledger.load_contract()
        manifest = ledger._phase35_manifest(contract)
        evidence = contract["source_evidence"]
        self.assertEqual(manifest["contract"]["raw_sha256"], contract["locks"]["phase35_source_contract"]["sha256"])
        self.assertEqual(manifest["contract"]["canonical_sha256"], evidence["phase35_manifest_contract_canonical_sha256"])
        self.assertEqual(manifest["implementation"]["sha256"], evidence["phase35_manifest_implementation_sha256"])
        self.assertEqual(manifest["artifacts"]["lossless_frame_archive"]["sha256"], evidence["phase35_archive_sha256"])

    def test_pcm_parser_accepts_wave_format_extensible_pcm24(self) -> None:
        values = np.array([[1, -1], [8388607, -8388607]], dtype=np.int32)
        unsigned = values.reshape(-1).astype(np.int64) & 0xFFFFFF
        packed = np.empty((unsigned.size, 3), dtype=np.uint8)
        packed[:, 0] = unsigned & 0xFF
        packed[:, 1] = (unsigned >> 8) & 0xFF
        packed[:, 2] = (unsigned >> 16) & 0xFF
        pcm_guid = bytes.fromhex("0100000000001000800000aa00389b71")
        fmt = struct.pack("<HHIIHHH", 0xFFFE, 2, 48000, 288000, 6, 24, 22)
        fmt += struct.pack("<HI", 24, 3) + pcm_guid
        payload = packed.tobytes()
        riff_size = 4 + 8 + len(fmt) + 8 + len(payload)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "extensible.wav"
            path.write_bytes(
                struct.pack("<4sI4s", b"RIFF", riff_size, b"WAVE")
                + struct.pack("<4sI", b"fmt ", len(fmt)) + fmt
                + struct.pack("<4sI", b"data", len(payload)) + payload
            )
            decoded, probe = ledger._read_pcm24_wave(path)
            self.assertTrue(np.array_equal(decoded, values))
            self.assertEqual(probe["data_sha256"], hashlib.sha256(payload).hexdigest())

    def test_preflight_validates_exact_archive_without_creating_output(self) -> None:
        contract = ledger.load_contract()
        output = ledger._output_path(contract, None)
        self.assertFalse(output.exists())
        with patch("pipeline.cartoon_ledger_pour._phase35_attempt_review", return_value=None):
            result = ledger.preflight()
        self.assertFalse(result["output_created"])
        self.assertFalse(result["encode_authorized"])
        self.assertEqual(result["phase35_decoded_frames"], 228)
        self.assertEqual(result["phase36_audio_samples"], 484800)
        self.assertEqual(result["phase26_stem_hash_mismatches"], 0)
        self.assertFalse(result["phase35_attempt_review_authorized"])
        self.assertFalse(result["build_authorized"])
        self.assertFalse(output.exists())

    def test_preflight_reports_rejected_candidate01_despite_exact_phase35_receipt(self) -> None:
        receipt = {
            "path": "collab/CLAUDE_REVIEW_FUTURE.md",
            "sha256": "future-review-hash",
            "verdict": "PHASE35_C03_ATTEMPT01_REJECTION_RATIFIED_REFERENCE_ONLY_PHASE36_UNENCODED_ALLOWED",
        }
        with patch("pipeline.cartoon_ledger_pour._phase35_attempt_review", return_value=receipt):
            result = ledger.preflight()
        self.assertTrue(result["phase35_attempt_review_authorized"])
        self.assertTrue(result["phase36_candidate01_rejected"])
        self.assertEqual(
            result["phase36_candidate01_rejection"]["verdict"],
            "PHASE36_CANDIDATE01_REJECTED_AUDIO_CONTINUITY_NEW_BINDING_REQUIRED",
        )
        self.assertFalse(result["build_authorized"])
        self.assertEqual(result["phase35_attempt_review"], receipt)
        self.assertFalse(result["output_created"])

    def test_builder_has_no_encoder_or_subprocess_dependency(self) -> None:
        source = (REPO_ROOT / "pipeline/cartoon_ledger_pour.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertNotIn("subprocess", imports)
        self.assertNotIn("pipeline.cartoon_source_textured_delivery_v2", imports)
        self.assertNotIn("Popen", source)
        contract = ledger.load_contract()
        self.assertFalse(contract["source_evidence"]["rejected_phase35_mp4_allowed_as_pixel_source"])
        self.assertFalse(contract["source_evidence"]["phase23_historical_encode_allowed_as_pixel_source"])


if __name__ == "__main__":
    unittest.main()
