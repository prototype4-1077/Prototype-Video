from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from pipeline import cartoon_source_opening as opening


class SourceOpeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inputs = opening._inputs()
        cls.black_hash = hashlib.sha256(bytes(1080 * 1920 * 3)).hexdigest()

    def fake_inputs(self) -> dict:
        inputs = copy.deepcopy(self.inputs)
        for row in inputs["rows"]:
            row["rgb_sha256"] = self.black_hash
        return inputs

    def fake_prepared(self, inputs: dict) -> tuple:
        source = inputs["source"]
        return (source, Image.new("RGB", (2, 2)),
                {pose["id"]: Image.new("RGBA", (2, 2)) for pose in source["poses"]},
                {entry["start_frame"]: Image.new("RGBA", (2, 2))
                 for entry in source["timeline"] if entry["type"] == "smear"})

    def compose_black(self, background, layer, source, frame):
        return Image.new("RGB", (1920, 1080)), {
            "frame": frame, "rendered_spill_pixels_source": 0, "spout_start_error_px_source": 0.0,
        }

    def assert_closed(self, prepared: tuple) -> None:
        for image in [prepared[1], *prepared[2].values(), *prepared[3].values()]:
            with self.assertRaises(ValueError):
                image.getpixel((0, 0))

    def test_preflight_source_only_provenance_and_exact_mapping(self) -> None:
        with patch.object(opening.pour, "compose_pour_frame", side_effect=AssertionError("must not render")), patch.object(
            opening.ledger, "load_contract", side_effect=AssertionError("historical gate must remain separate")
        ), patch.object(opening.ledger, "iter_phase35_frames", side_effect=AssertionError("must not read cache")):
            provenance = opening.preflight()
        self.assertEqual(provenance["clock"], opening.CLOCK)
        self.assertEqual(provenance["source_frames"], [112, 186])
        self.assertEqual(provenance["output_frames"], [1, 75])
        self.assertEqual(provenance["source_camera_clock_frame_count"], 258)
        self.assertFalse(provenance["external_scene_cache_used"])
        self.assertEqual(len(provenance["runtime_asset_hashes"]), 7)
        self.assertEqual(sum(record["hash_domain"] == "raw_bytes" for record in provenance["dependencies"]), 16)
        self.assertEqual(self.inputs["picture"].keys(), {"locks"})
        self.assertEqual(self.inputs["picture"]["locks"].keys(), {"phase23_contract"})

    def test_explicit_hash_domains_allow_line_endings_not_content_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(opening, "REPO_ROOT", Path(directory)):
            path = Path(directory) / "data.txt"
            with path.open("wb") as destination:
                destination.write(b"one\r\ntwo\r\n")
            record, _ = opening._file_record("data.txt", opening._sha(b"one\ntwo\n"), "lf_normalized_text")
            self.assertEqual(record["raw_sha256"], opening._sha(b"one\r\ntwo\r\n"))
            with self.assertRaises(opening.SourceOpeningError):
                opening._file_record("data.txt", record["sha256"], "raw_bytes")
            with path.open("wb") as destination:
                destination.write(b"one\nchanged\n")
            with self.assertRaises(opening.SourceOpeningError):
                opening._file_record("data.txt", record["sha256"], "lf_normalized_text")
            with path.open("w", encoding="utf-8") as destination:
                destination.write('{ "b": 2, "a": 1 }\n')
            opening._file_record("data.txt", opening._canonical({"a": 1, "b": 2}), "canonical_json_utf8")
            with self.assertRaises(opening.SourceOpeningError):
                opening._file_record("../escape.txt", "unused", "raw_bytes")

    def test_source_drift_stops_before_asset_prepare_or_first_yield(self) -> None:
        pins = dict(opening.PINNED_SOURCE_LF)
        pins["pipeline/cartoon_pour_layers.py"] = "0" * 64
        with patch.object(opening, "PINNED_SOURCE_LF", pins), patch.object(opening.ledger, "_prepare_pour") as prepare:
            with self.assertRaisesRegex(opening.SourceOpeningError, "cartoon_pour_layers.py"):
                next(opening.frames())
            prepare.assert_not_called()

    def test_all_75_mapping_original_source_clock_and_terminal_cleanup(self) -> None:
        inputs = self.fake_inputs()
        prepared = self.fake_prepared(inputs)
        seen = []
        with patch.object(opening, "_inputs", return_value=inputs), patch.object(
            opening.ledger, "_prepare_pour", return_value=prepared
        ) as prepare, patch.object(opening.pour, "compose_pour_frame", side_effect=self.compose_black) as compose:
            for number, frame, metrics in opening.frames():
                self.assertEqual(frame.shape, (1080, 1920, 3))
                self.assertEqual(frame.dtype, np.uint8)
                self.assertTrue(frame.flags.owndata)
                self.assertEqual(metrics["output_pts"], [number - 1, 30])
                self.assertEqual(metrics["source_pts"], [number + 110, 30])
                self.assertTrue(metrics["published_inventory_match"])
                seen.append((number, metrics["source_frame"]))
        self.assertEqual(seen, [(number, number + 111) for number in range(1, 76)])
        self.assertEqual([call.args[3] for call in compose.call_args_list], list(range(112, 187)))
        prepare.assert_called_once_with(inputs["picture"], inputs["assets"])
        self.assert_closed(prepared)

    def test_early_generator_close_closes_assets_and_keeps_rgb_owned(self) -> None:
        inputs = self.fake_inputs()
        prepared = self.fake_prepared(inputs)
        rendered = Image.new("RGB", (1920, 1080))
        liquid = self.compose_black(None, None, None, 112)[1]
        with patch.object(opening, "_inputs", return_value=inputs), patch.object(
            opening.ledger, "_prepare_pour", return_value=prepared
        ), patch.object(opening.pour, "compose_pour_frame", return_value=(rendered, liquid)):
            stream = opening.frames()
            _, frame, _ = next(stream)
            with self.assertRaises(ValueError):
                rendered.getpixel((0, 0))
            stream.close()
        self.assertEqual(int(frame.sum()), 0)
        self.assert_closed(prepared)

    def test_pixel_mismatch_is_not_yielded_and_assets_close(self) -> None:
        inputs = self.fake_inputs()
        inputs["rows"][0]["rgb_sha256"] = "0" * 64
        prepared = self.fake_prepared(inputs)
        with patch.object(opening, "_inputs", return_value=inputs), patch.object(
            opening.ledger, "_prepare_pour", return_value=prepared
        ), patch.object(opening.pour, "compose_pour_frame", side_effect=self.compose_black):
            with self.assertRaisesRegex(opening.SourceOpeningError, "source F112 RGB"):
                next(opening.frames())
        self.assert_closed(prepared)

    def test_render_exception_closes_assets(self) -> None:
        inputs = self.fake_inputs()
        prepared = self.fake_prepared(inputs)
        with patch.object(opening, "_inputs", return_value=inputs), patch.object(
            opening.ledger, "_prepare_pour", return_value=prepared
        ), patch.object(opening.pour, "compose_pour_frame", side_effect=RuntimeError("render stopped")):
            with self.assertRaisesRegex(RuntimeError, "render stopped"):
                next(opening.frames())
        self.assert_closed(prepared)

    def test_post_prepare_source_drift_closes_assets_without_render(self) -> None:
        inputs = self.fake_inputs()
        prepared = self.fake_prepared(inputs)
        with patch.object(opening, "_inputs", side_effect=[inputs, opening.SourceOpeningError("source drift")]), patch.object(
            opening.ledger, "_prepare_pour", return_value=prepared
        ), patch.object(opening.pour, "compose_pour_frame") as compose:
            with self.assertRaisesRegex(opening.SourceOpeningError, "source drift"):
                next(opening.frames())
            compose.assert_not_called()
        self.assert_closed(prepared)

    def test_contact_failure_is_not_yielded(self) -> None:
        inputs = self.fake_inputs()
        prepared = self.fake_prepared(inputs)
        def spill(*args):
            image, report = self.compose_black(*args)
            report["rendered_spill_pixels_source"] = 1
            return image, report
        with patch.object(opening, "_inputs", return_value=inputs), patch.object(
            opening.ledger, "_prepare_pour", return_value=prepared
        ), patch.object(opening.pour, "compose_pour_frame", side_effect=spill):
            with self.assertRaisesRegex(opening.SourceOpeningError, "liquid spill"):
                next(opening.frames())
        self.assert_closed(prepared)

    def test_audit_never_overwrites_existing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "source-opening-audit-v1.json"
            with sentinel.open("w", encoding="utf-8") as destination:
                destination.write("immutable evidence")
            with patch.object(opening, "preflight") as preflight:
                with self.assertRaises(FileExistsError):
                    opening.write_audit(directory)
                preflight.assert_not_called()
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "immutable evidence")

    def test_actual_sampled_source_render_hashes_match_published_inventory(self) -> None:
        expected = {
            112: "f108104d4ca4a8f1982712d8b814228a094ac93232d0e779a33abf84f6a545df",
            156: "b86244ef85a987fbc82633e9908464dad5232bbe5f2322d941c744827945e649",
            186: "f3d82b03fd2320f03e8e989b2d9fedd8736ce50c4ab648b4fc2e9350120ff477",
        }
        inputs = self.inputs
        prepared = opening.ledger._prepare_pour(inputs["picture"], inputs["assets"])
        source, background, registered, smears = prepared
        try:
            for source_frame, digest in expected.items():
                with self.subTest(source_frame=source_frame):
                    row = inputs["rows"][source_frame - 112]
                    self.assertEqual(row["rgb_sha256"], digest)
                    entry = opening.pour.timeline_entry_for_frame(source["timeline"], source_frame)
                    layer = registered[entry["pose_id"]] if entry["type"] == "pose" else smears[source_frame]
                    image, liquid = opening.pour.compose_pour_frame(background, layer, source, source_frame)
                    try:
                        self.assertEqual(opening._sha(np.asarray(image, dtype=np.uint8).tobytes()), digest)
                        self.assertEqual(liquid["rendered_spill_pixels_source"], 0)
                        self.assertEqual(liquid["spout_start_error_px_source"], 0.0)
                    finally:
                        image.close()
        finally:
            opening.ledger._close_pour_assets(prepared[1], prepared[2], prepared[3])


if __name__ == "__main__":
    unittest.main()
