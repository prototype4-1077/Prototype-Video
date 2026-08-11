import ast
import copy
import gzip
import hashlib
import inspect
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_source_textured_vui_probe as probe


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / probe.CONTRACT_RELATIVE_PATH


class CartoonSourceTexturedVuiProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = probe.load_contract()

    def test_authorization_subject_and_repository_locks_are_exact(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            probe._canonical_hash(probe._authorization_subject(contract)),
            "bfaffe5ad4cb8238d153766d677adc47fb69d1f8e0e5a2b9b2560132cd5ae594",
        )
        for reference in contract["locks"].values():
            self.assertEqual(probe._lock_hash(reference), reference["sha256"])

    def test_contract_is_free_video_only_diagnostic_and_nonpromotable(self) -> None:
        contract = self.contract
        self.assertEqual(contract["cash_cost"], 0)
        self.assertFalse(contract["paid_runtime_dependency"])
        self.assertFalse(contract["network_runtime_required"])
        self.assertFalse(contract["encoding"]["audio_allowed"])
        self.assertFalse(contract["encoding"]["h264_metadata_patch_allowed"])
        self.assertFalse(contract["encoding"]["setparams_filter_allowed"])
        self.assertFalse(contract["failure_policy"]["full_phase35_encode_allowed"])
        self.assertFalse(contract["failure_policy"]["phase36_encode_allowed"])
        self.assertFalse(contract["failure_policy"]["candidate02_audio_mux_allowed"])
        self.assertFalse(contract["failure_policy"]["promotion_allowed"])

    def test_selection_is_complete_blink_and_binds_worst_attempt01_pair(self) -> None:
        selection = self.contract["selection"]
        self.assertEqual(selection["source_frame_numbers"], list(range(77, 86)))
        self.assertEqual(selection["blink_closure_weights"], [0.0, 0.25, 0.5, 0.75, 1.0, 0.75, 0.5, 0.25, 0.0])
        self.assertEqual(selection["contains_attempt01_worst_codec_delta_pair"], [80, 81])
        self.assertEqual(selection["combined_rgb24_payload_bytes"], 55987200)
        self.assertEqual(
            selection["combined_rgb24_payload_sha256"],
            "a32e61dab0ab574727417e0ebf765e4ec06978d16190d1f4011525303de8d879",
        )

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_values(self) -> None:
        with self.assertRaisesRegex(probe.VuiProbeError, "duplicate key"):
            probe._strict_json_loads(b'{"a":1,"a":2}', "test")
        with self.assertRaisesRegex(probe.VuiProbeError, "non-finite"):
            probe._strict_json_loads(b'{"a":NaN}', "test")

    def test_unauthorized_run_refuses_before_tool_or_output_resolution(self) -> None:
        with patch.object(probe, "_authorization", return_value=None), patch.object(
            probe, "_resolved_tool", side_effect=AssertionError("tool resolved")
        ), patch.object(probe, "_output_path", side_effect=AssertionError("output resolved")):
            with self.assertRaisesRegex(probe.VuiProbeError, "refusing before output resolution"):
                probe.run_authorized_probe()

    def test_authorization_requires_exact_verdict_and_all_dynamic_bindings(self) -> None:
        contract = copy.deepcopy(self.contract)
        gate = contract["authorization"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            implementation = root / probe.IMPLEMENTATION_RELATIVE_PATH
            implementation.parent.mkdir(parents=True)
            implementation.write_text("fixed implementation\n", encoding="utf-8")
            review = root / "authorization.md"
            tokens = [
                probe.EXPECTED_AUTHORIZATION_SUBJECT_SHA256,
                hashlib.sha256(implementation.read_bytes()).hexdigest(),
                probe._command_template_hash(contract),
                contract["locks"]["source_manifest"]["sha256"],
                contract["source_evidence"]["archive_sha256"],
                contract["selection"]["frame_inventory_canonical_sha256"],
                contract["selection"]["combined_rgb24_payload_sha256"],
                contract["locks"]["attempt01_report"]["sha256"],
                contract["locks"]["attempt01_failure"]["sha256"],
                contract["toolchain"]["ffmpeg_sha256"],
                contract["toolchain"]["ffprobe_sha256"],
            ]
            review.write_text(
                f"## Verdict: {gate['required_verdict']}\n" + "\n".join(tokens) + "\n",
                encoding="utf-8",
            )
            gate["receipt"] = {
                "path": "authorization.md",
                "hash_domain": "lf_normalized_text",
                "sha256": hashlib.sha256(review.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
            }
            with patch.object(probe, "REPO_ROOT", root):
                authorization = probe._authorization(contract)
            self.assertEqual(authorization["verdict"], gate["required_verdict"])
            review.write_text(
                f"## Verdict: {gate['required_verdict']}\n" + "\n".join(tokens[:-1]) + "\n",
                encoding="utf-8",
            )
            gate["receipt"]["sha256"] = hashlib.sha256(review.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            with patch.object(probe, "REPO_ROOT", root), self.assertRaisesRegex(probe.VuiProbeError, "omits binding token"):
                probe._authorization(contract)

    def _synthetic_archive(self, root: Path, corrupt_frame: int | None = None, trailing: bool = False):
        shape = (1, 2, 3)
        frames = [np.full(shape, frame_number % 251, dtype=np.uint8) for frame_number in range(1, 229)]
        hashes = [
            {"frame": number, "rgb_sha256": hashlib.sha256(frame.tobytes()).hexdigest()}
            for number, frame in enumerate(frames, start=1)
        ]
        if corrupt_frame is not None:
            hashes[corrupt_frame - 1]["rgb_sha256"] = "0" * 64
        selected = frames[76:85]
        combined = b"".join(frame.tobytes() for frame in selected)
        contract = copy.deepcopy(self.contract)
        contract["source_evidence"]["archive_header"] = {
            "format": "synthetic",
            "width": 2,
            "height": 1,
            "channels": 3,
            "frame_count": 228,
            "frame_bytes": 6,
            "xor_seed": "all_zero_rgb24_frame",
        }
        contract["selection"]["combined_rgb24_payload_bytes"] = len(combined)
        contract["selection"]["combined_rgb24_payload_sha256"] = hashlib.sha256(combined).hexdigest()
        archive_path = root / "frames.gz"
        previous = np.zeros(shape, dtype=np.uint8)
        with gzip.open(archive_path, "wb") as archive:
            archive.write((json.dumps(contract["source_evidence"]["archive_header"], separators=(",", ":")) + "\n").encode())
            for frame in frames:
                archive.write(np.bitwise_xor(frame, previous).tobytes())
                previous = frame
            if trailing:
                archive.write(b"x")
        return archive_path, contract, hashes, selected

    def test_xor_archive_selector_verifies_full_chain_and_exact_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive, contract, hashes, expected = self._synthetic_archive(Path(directory))
            selected, audit = probe._reconstruct_selected_frames(archive, contract, hashes)
        self.assertEqual(audit["verified_archive_frames"], 228)
        self.assertEqual(audit["selected_frames"], list(range(77, 86)))
        self.assertTrue(all(np.array_equal(actual, wanted) for actual, wanted in zip(selected, expected)))

    def test_xor_archive_selector_rejects_inventory_corruption_and_trailing_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive, contract, hashes, _ = self._synthetic_archive(Path(directory), corrupt_frame=150)
            with self.assertRaisesRegex(probe.VuiProbeError, "source frame 150"):
                probe._reconstruct_selected_frames(archive, contract, hashes)
        with tempfile.TemporaryDirectory() as directory:
            archive, contract, hashes, _ = self._synthetic_archive(Path(directory), trailing=True)
            with self.assertRaisesRegex(probe.VuiProbeError, "trailing decompressed payload"):
                probe._reconstruct_selected_frames(archive, contract, hashes)

    def test_encoder_command_is_exact_video_only_direct_x264_vui_path(self) -> None:
        command = probe._command_template(self.contract)
        self.assertEqual(command[0], "$FFMPEG")
        self.assertEqual(command[-1], "$OUTPUT")
        self.assertIn("-an", command)
        self.assertEqual(command[command.index("-frames:v") + 1], "9")
        self.assertEqual(command[command.index("-pix_fmt") + 1], "yuv420p")
        self.assertEqual(
            command[command.index("-x264-params") + 1],
            "fullrange=off:colorprim=bt709:transfer=bt709:colormatrix=bt709",
        )
        self.assertEqual(command[command.index("-movflags") + 1], "+faststart+write_colr")
        self.assertNotIn("h264_metadata", command)
        self.assertNotIn("setparams", command)
        self.assertEqual(command.count("-i"), 1)

    def test_sps_parser_collects_repeated_values_and_exposes_conflicts(self) -> None:
        lines = []
        expected = {
            "video_signal_type_present_flag": 1,
            "video_full_range_flag": 0,
            "colour_description_present_flag": 1,
            "colour_primaries": 1,
            "transfer_characteristics": 1,
            "matrix_coefficients": 1,
        }
        for _ in range(2):
            lines.extend(f"[trace_headers] {name} = {value}" for name, value in expected.items())
        parsed = probe._parse_sps_trace("\n".join(lines))
        self.assertTrue(all(values == [expected[name], expected[name]] for name, values in parsed.items()))
        parsed["colour_primaries"].append(2)
        gates = self._passing_gates(sps=parsed)
        self.assertFalse(next(gate for gate in gates if gate["name"] == "sps_colour_primaries")["passed"])

    @staticmethod
    def _box(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I4s", len(payload) + 8, kind) + payload

    def test_mp4_parser_reads_hierarchical_nclx_colr(self) -> None:
        colr = self._box(b"colr", b"nclx" + struct.pack(">HHH", 1, 1, 1) + b"\x00")
        avc1 = self._box(b"avc1", b"\x00" * 78 + colr)
        stsd = self._box(b"stsd", b"\x00\x00\x00\x00" + struct.pack(">I", 1) + avc1)
        payload = self._box(b"moov", self._box(b"trak", self._box(b"mdia", self._box(b"minf", self._box(b"stbl", stsd)))))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.mp4"
            path.write_bytes(payload)
            records = probe._parse_mp4_colr(path)
        self.assertEqual(len(records), 1)
        self.assertEqual(
            {key: records[0][key] for key in ("path", "type", "payload_bytes", "primaries", "transfer", "matrix", "full_range_flag", "reserved_bits")},
            {"path": "moov/trak/mdia/minf/stbl/stsd/avc1/colr", "type": "nclx", "payload_bytes": 11, "primaries": 1, "transfer": 1, "matrix": 1, "full_range_flag": 0, "reserved_bits": 0},
        )

    def test_mp4_parser_records_wrong_type_and_rogue_location_as_gate_failures(self) -> None:
        nclc = self._box(b"colr", b"nclc" + struct.pack(">HHH", 1, 1, 1))
        rogue = self._box(b"colr", b"nclx" + struct.pack(">HHH", 1, 1, 1) + b"\x00")
        with tempfile.TemporaryDirectory() as directory:
            nclc_path = Path(directory) / "nclc.mp4"
            nclc_path.write_bytes(nclc)
            nclc_records = probe._parse_mp4_colr(nclc_path)
            rogue_path = Path(directory) / "rogue.mp4"
            rogue_path.write_bytes(rogue)
            rogue_records = probe._parse_mp4_colr(rogue_path)
        self.assertEqual(nclc_records, [{"path": "colr", "type": "nclc", "payload_bytes": 10}])
        self.assertEqual(rogue_records[0]["path"], "colr")
        gates = self._passing_gates(colr=rogue_records)
        self.assertFalse(next(gate for gate in gates if gate["name"] == "mp4_colr_nclx")["passed"])

    def _passing_gates(self, sps=None, colr=None):
        stream = {
            "streams": [{
                "index": 0, "codec_type": "video", "codec_name": "h264", "codec_tag_string": "avc1",
                "pix_fmt": "yuv420p", "width": 1920, "height": 1080, "nb_frames": "9",
                "nb_read_frames": "9", "r_frame_rate": "30/1", "avg_frame_rate": "30/1",
                "start_time": "0.000000", "duration": "0.300000", "color_range": "tv",
                "color_space": "bt709", "color_transfer": "bt709", "color_primaries": "bt709",
            }],
            "format": {"start_time": "0.000000", "duration": "0.300000"},
        }
        frames = {"frames": [{
            "best_effort_timestamp_time": f"{index / 30.0:.6f}", "color_range": "tv",
            "color_space": "bt709", "color_transfer": "bt709", "color_primaries": "bt709",
        } for index in range(9)]}
        expected_sps = sps or {
            "video_signal_type_present_flag": [1], "video_full_range_flag": [0],
            "colour_description_present_flag": [1], "colour_primaries": [1],
            "transfer_characteristics": [1], "matrix_coefficients": [1],
        }
        colr = colr or [{
            "path": "moov/trak/mdia/minf/stbl/stsd/avc1/colr", "type": "nclx",
            "payload_bytes": 11, "primaries": 1, "transfer": 1, "matrix": 1,
            "full_range_flag": 0, "reserved_bits": 0,
        }]
        decoded = {"decoded_frame_count": 9, "nearest_source_frame_order": list(range(77, 86)), "minimum_full_frame_psnr_db": 40.0}
        return probe._audit_gates(self.contract, stream, frames, expected_sps, colr, decoded)

    def test_complete_synthetic_metadata_audit_passes_and_missing_colr_fails(self) -> None:
        gates = self._passing_gates()
        self.assertTrue(all(gate["passed"] for gate in gates))
        colr_gate = next(gate for gate in gates if gate["name"] == "mp4_colr_nclx")
        self.assertTrue(colr_gate["passed"])

    def test_claim_is_exclusive_and_declares_no_retry_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            command = ["ffmpeg", "-n", "partial.mp4"]
            claim = probe._claim_attempt(output, {"fixed": True}, command)
            payload = json.loads(claim.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "CLAIMED_BEFORE_ENCODER_LAUNCH")
            self.assertTrue(payload["authorization_consumed"])
            self.assertFalse(payload["automatic_retry_allowed"])
            with self.assertRaisesRegex(probe.VuiProbeError, "already claimed"):
                probe._claim_attempt(output, {"fixed": True}, command)

    def test_rejected_attempt_package_binds_failure_and_every_other_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage = root / "stage"
            stage.mkdir()
            (stage / "ffmpeg-stderr-v1.txt").write_text("encoder failed\n", encoding="utf-8")
            claim = root / "claim.json"
            claim.write_text('{"claimed":true}\n', encoding="utf-8")
            rejected = root / "rejected"
            probe._preserve_rejected(
                stage, rejected, claim, RuntimeError("synthetic rejection"), True,
                {
                    "encoding_process_count": 1,
                    "encoder_return_code": 1,
                    "source_frames_written": 4,
                    "source_bytes_written": 24883200,
                },
                self.contract,
            )
            package = json.loads((rejected / "attempt-package-v1.json").read_text(encoding="utf-8"))
            failure = json.loads((rejected / "failure-v1.json").read_text(encoding="utf-8"))
            bound = {artifact["file"]: artifact for artifact in package["artifacts"]}
            self.assertIn("failure-v1.json", bound)
            self.assertIn("attempt-claim-v1.json", bound)
            self.assertIn("ffmpeg-stderr-v1.txt", bound)
            self.assertEqual(failure["attempt"]["source_frames_written"], 4)
            self.assertFalse(package["machine_passed"])
            for name, artifact in bound.items():
                path = rejected / name
                self.assertEqual(path.stat().st_size, artifact["bytes"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact["sha256"])

    def test_static_state_machine_claims_before_exactly_one_encoder_popen(self) -> None:
        source = inspect.getsource(probe.run_authorized_probe)
        self.assertLess(source.index("authorization = _authorization"), source.index("output = _output_path"))
        self.assertLess(source.index("claim = _claim_attempt"), source.index("process = subprocess.Popen"))
        self.assertEqual(source.count("subprocess.Popen("), 1)
        self.assertIn("_preserve_rejected", source)
        self.assertNotIn("render", source)
        tree = ast.parse((REPO_ROOT / probe.IMPLEMENTATION_RELATIVE_PATH).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        for forbidden in ("requests", "urllib", "socket", "moviepy", "av", "PIL", "cv2"):
            self.assertNotIn(forbidden, imported)


if __name__ == "__main__":
    unittest.main()
