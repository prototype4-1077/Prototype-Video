from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest

import numpy as np

from pipeline import cartoon_source_textured_direct_address as direct
from pipeline import cartoon_source_textured_face as phase34
from pipeline import cartoon_source_textured_face_v2 as phase34_candidate09


PCM_SUBFORMAT_GUID = bytes.fromhex("0100000000001000800000aa00389b71")


def _wav_chunk(chunk_id: bytes, payload: bytes) -> bytes:
    return chunk_id + struct.pack("<I", len(payload)) + payload + (b"\0" if len(payload) % 2 else b"")


def _wav_bytes(fmt_payload: bytes, data_payload: bytes, *, riff_size: int | None = None) -> bytes:
    body = b"WAVE" + _wav_chunk(b"fmt ", fmt_payload) + _wav_chunk(b"data", data_payload)
    return b"RIFF" + struct.pack("<I", len(body) if riff_size is None else riff_size) + body


class WaveProbeTests(unittest.TestCase):
    def _probe(self, payload: bytes) -> dict[str, int]:
        with tempfile.TemporaryDirectory(prefix="phase35-wave-probe-") as temporary:
            path = Path(temporary) / "probe.wav"
            path.write_bytes(payload)
            return direct._wave_probe(path)

    def test_accepts_standard_and_extensible_pcm(self) -> None:
        pcm = struct.pack("<HHIIHH", 1, 1, 48000, 144000, 3, 24)
        self.assertEqual(
            self._probe(_wav_bytes(pcm, bytes(12))),
            {"sample_rate": 48000, "channels": 1, "sample_width": 3, "sample_count": 4},
        )

        extensible = struct.pack(
            "<HHIIHHHHI16s", 0xFFFE, 2, 48000, 288000, 6, 24, 22, 24, 3,
            PCM_SUBFORMAT_GUID,
        )
        self.assertEqual(
            self._probe(_wav_bytes(extensible, bytes(24))),
            {"sample_rate": 48000, "channels": 2, "sample_width": 3, "sample_count": 4},
        )

    def test_rejects_malformed_or_non_pcm_wav(self) -> None:
        pcm = struct.pack("<HHIIHH", 1, 1, 48000, 144000, 3, 24)
        extensible = struct.pack(
            "<HHIIHHHHI16s", 0xFFFE, 2, 48000, 288000, 6, 24, 22, 24, 3,
            PCM_SUBFORMAT_GUID,
        )
        cases = {
            "chunks outside declared RIFF": _wav_bytes(pcm, bytes(12), riff_size=4),
            "truncated declared extension": _wav_bytes(
                extensible[:16] + struct.pack("<H", 30) + extensible[18:], bytes(24),
            ),
            "unsupported extensible subtype": _wav_bytes(
                extensible[:24] + bytes.fromhex("0300000000001000800000aa00389b71"), bytes(24),
            ),
            "misaligned sample data": _wav_bytes(pcm, bytes(5)),
            "zero-width PCM": _wav_bytes(
                struct.pack("<HHIIHH", 1, 1, 48000, 0, 0, 0), b"",
            ),
            "partial trailing chunk header": (
                b"RIFF" + struct.pack("<I", 4 + len(_wav_chunk(b"fmt ", pcm)) + 3)
                + b"WAVE" + _wav_chunk(b"fmt ", pcm) + b"bad"
            ),
        }
        for label, payload in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(direct.SourceTexturedDirectAddressError):
                    self._probe(payload)


class SourceTexturedDirectAddressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = direct.prepare_direct_address()

    def test_contract_is_canonical_hash_locked_to_candidate08_and_candidate09_blink(self) -> None:
        contract, path = direct.load_contract()
        self.assertEqual(
            direct._canonical_hash(contract),
            direct.EXPECTED_CONTRACT_CANONICAL_SHA256,
        )
        self.assertEqual(contract["locks"]["phase34_candidate08_renderer"]["sha256"], phase34._sha256(phase34.REPO_ROOT / phase34.IMPLEMENTATION_RELATIVE_PATH))
        self.assertEqual(contract["locks"]["phase34_renderer"]["sha256"], phase34_candidate09._sha256(phase34_candidate09.REPO_ROOT / phase34_candidate09.IMPLEMENTATION_RELATIVE_PATH))
        self.assertIn("candidate08", json.dumps(contract).lower())
        self.assertIn("candidate09", json.dumps(contract).lower())
        self.assertEqual(path, direct.REPO_ROOT / direct.CONTRACT_RELATIVE_PATH)
        archive = direct.REPO_ROOT / contract["locks"]["phase35_candidate01_implementation_archive"]["path"]
        self.assertEqual(direct._sha256(archive), "a9ae557aa397ffe7a6ac4a9821ac3f693d70a3d144f13c9ae9c2b5975fb3800a")
        with tarfile.open(archive, "r") as source:
            member = source.extractfile("pipeline/cartoon_source_textured_direct_address.py")
            self.assertIsNotNone(member)
            self.assertEqual(
                hashlib.sha256(member.read()).hexdigest(),
                "ac93e299c8378f0669e84938dd54fe03fbd26589f793721b4f94c74f7b9385fa",
            )

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
            expected, _ = phase34_candidate09._native_frame(prepared.face, reference_frame)
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
        expected, _ = phase34_candidate09._native_frame(prepared.face, 8)
        self.assertTrue(np.array_equal(actual, expected))
        self.assertEqual(evidence.blink_closure, 1.0)

    def test_adapter_rejects_unrepresentable_timing(self) -> None:
        with self.assertRaisesRegex(direct.SourceTexturedDirectAddressError, "not representable"):
            direct._synthetic_viseme_schedule(
                {"from_shape": "A", "to_shape": "B", "blend": 0.3},
                10,
            )

        with self.assertRaisesRegex(direct.SourceTexturedDirectAddressError, "outside"):
            direct._synthetic_blink_schedule(1.01)

    def test_candidate09_linear_blink_policy_is_exact(self) -> None:
        expected = [0.0, 0.25, 0.5, 0.75, 1.0, 0.75, 0.5, 0.25, 0.0]
        for curve in self.prepared.contract["performance"]["blink_curves"]:
            self.assertEqual(curve["closures"], expected)
            actual = [
                direct.production_blink_closure(self.prepared.contract, frame)
                for frame in curve["frames"]
            ]
            self.assertEqual(actual, expected)
            for closure in actual:
                render_frame, table = direct._synthetic_blink_schedule(closure)
                self.assertEqual(render_frame, 2)
                self.assertEqual(table, {"2": closure})
        expected_pairs = {
            (frame, frame + 1)
            for start in (77, 169)
            for frame in range(start, start + 8)
        }
        self.assertEqual(direct._blink_pairs(self.prepared.contract), expected_pairs)
        self.assertEqual(
            direct._blink_review_frames(self.prepared.contract),
            list(range(77, 86)) + list(range(169, 178)),
        )

    def test_candidate09_reference_pixels_and_candidate08_nonblink_are_preserved(self) -> None:
        neutral = {"from_shape": "X", "to_shape": "X", "blend": 1.0}
        for closure, reference_frame in ((0.25, 5), (0.5, 6), (0.75, 7), (1.0, 8)):
            actual, evidence = direct.controlled_native_frame(self.prepared, neutral, closure)
            expected, _ = phase34_candidate09._native_frame(self.prepared.face, reference_frame)
            self.assertTrue(np.array_equal(actual, expected), closure)
            self.assertEqual(evidence.blink_closure, closure)

        candidate08 = json.loads(
            (direct.REPO_ROOT / "collab/phase34_candidate_08/june-phase34-source-textured-visemes-preview-manifest-v1.json").read_text(encoding="utf-8")
        )
        candidate09 = json.loads(
            (direct.REPO_ROOT / "collab/phase34_candidate_09/june-phase34-source-textured-visemes-preview-manifest-v2.json").read_text(encoding="utf-8")
        )
        c08 = {entry["frame"]: entry["rgb_sha256"] for entry in candidate08["frames"]}
        c09 = {entry["frame"]: entry["rgb_sha256"] for entry in candidate09["frames"]}
        for reference_frame in (16, 22, 30, 38, 46, 54, 62, 70, 78):
            self.assertEqual(c09[reference_frame], c08[reference_frame], reference_frame)

    def test_candidate02_eight_frame_delta_is_exactly_eye_only(self) -> None:
        baseline_manifest = json.loads(
            (direct.REPO_ROOT / self.prepared.contract["locks"]["phase35_candidate01_manifest"]["path"]).read_text(encoding="utf-8")
        )
        baseline_hashes = {
            entry["frame"]: entry["rgb_sha256"]
            for entry in baseline_manifest["frame_hashes"]
        }
        native_eye_support = direct._native_eye_support_mask(self.prepared)
        for frame_number in self.prepared.contract["preencode_gates"]["required_candidate01_changed_frames"]:
            current_image, current_native, _ = direct.compose_direct_address_frame(
                self.prepared, frame_number,
            )
            baseline_image, baseline_native, _ = direct.compose_direct_address_frame(
                self.prepared, frame_number, candidate01=True,
            )
            baseline_final = np.asarray(baseline_image, dtype=np.uint8)
            self.assertEqual(
                phase34._raw_frame_hash(baseline_final), baseline_hashes[frame_number], frame_number,
            )
            native_changed = np.any(current_native != baseline_native, axis=2)
            self.assertEqual(int((native_changed & ~native_eye_support).sum()), 0, frame_number)
            final_changed = np.any(
                np.asarray(current_image, dtype=np.uint8) != baseline_final, axis=2,
            )
            allowed = direct._final_eye_support_mask(self.prepared, frame_number)
            self.assertEqual(int((final_changed & ~allowed).sum()), 0, frame_number)

    def test_all_228_control_schedules_are_representable(self) -> None:
        for frame_number, viseme in enumerate(self.prepared.visemes, start=1):
            closure = direct.production_blink_closure(self.prepared.contract, frame_number)
            render_frame, _ = direct._synthetic_blink_schedule(closure)
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
        self.assertNotIn("soundfile", imported)
        self.assertNotIn("wave", imported)
        self.assertIn("struct", imported)
        self.assertNotIn("ffmpeg", source.lower())
        self.assertNotIn("Popen", source)
        preview_source = inspect.getsource(direct.write_unencoded_preview)
        self.assertLess(preview_source.index("try:"), preview_source.index("tempfile.mkdtemp"))
        self.assertLess(preview_source.index("if failed:"), preview_source.index("stage.replace(output)"))
        self.assertIn("verify_lossless_archive", preview_source)
        self.assertGreaterEqual(preview_source.count("_execution_state_mismatches"), 2)

    def test_execution_state_detects_a_provenance_mismatch(self) -> None:
        captured = direct._capture_execution_state(
            self.prepared.contract, self.prepared.contract_path,
        )
        captured["implementation_sha256"] = "0" * 64
        self.assertIn(
            "implementation_sha256",
            direct._execution_state_mismatches(
                captured, self.prepared.contract, self.prepared.contract_path,
            ),
        )
        altered = json.loads(json.dumps(self.prepared.contract))
        altered["locks"]["dialogue_audio"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(direct.SourceTexturedDirectAddressError, "captured locked dialogue_audio"):
            direct._capture_execution_state(altered, self.prepared.contract_path)

    def test_measurement_domains_and_thresholds_are_preregistered(self) -> None:
        gates = self.prepared.contract["preencode_gates"]
        self.assertEqual(gates["accepted_candidate08_same_domain_maximum_source_pop"], 152.9947967529297)
        self.assertEqual(gates["maximum_native_face_temporal_excess_over_accepted_candidate08"], 0.01)
        self.assertEqual(gates["maximum_native_face_adjacent_8x8_mean_delta"], 145.0)
        self.assertEqual(gates["maximum_native_blink_adjacent_8x8_mean_delta"], 130.0)
        self.assertEqual(gates["maximum_final_composed_face_adjacent_8x8_mean_delta"], 170.0)
        self.assertEqual(gates["required_audio_samples_per_frame"], 1600)
        self.assertEqual(gates["required_lossless_rgb_archive_verified_frames"], 228)
        self.assertEqual(gates["required_candidate01_preserved_frame_hashes"], 220)
        self.assertEqual(gates["required_candidate01_changed_frames"], [78, 80, 82, 84, 170, 172, 174, 176])
        self.assertEqual(gates["required_candidate01_baseline_rerender_hash_mismatches"], 0)
        self.assertEqual(gates["required_candidate01_native_changed_pixels_outside_eye_support"], 0)
        self.assertEqual(gates["required_candidate01_final_changed_pixels_outside_transformed_eye_support"], 0)
        self.assertEqual(gates["required_candidate01_delta_frames_evaluated"], 8)
        self.assertEqual(gates["required_end_state_hash_mismatches"], 0)
        source = inspect.getsource(direct.write_unencoded_preview)
        self.assertIn("phase34_lanczos_resampled_1920x1080_rgb_before_body_head_camera_or_atmosphere", source)
        self.assertIn("final_composed_1920x1080_rgb_before_encode", source)


if __name__ == "__main__":
    unittest.main()
