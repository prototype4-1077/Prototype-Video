from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import shutil
import subprocess
from types import SimpleNamespace
import unittest

import numpy as np

from pipeline import cartoon_mouth_semantics_refinement as mouth


class MouthTranslationTests(unittest.TestCase):
    def test_mapping_distinguishes_raw_phonemes_from_internal_art_names(self) -> None:
        self.assertEqual(mouth.RHUBARB_TO_ART,
                         {"A": "X", "B": "C", "C": "D", "D": "B", "E": "A",
                          "F": "G", "G": "F", "H": "H", "X": "X"})

    def test_plan_preserves_all_frames_blends_and_raw_provenance(self) -> None:
        _, original = mouth.direct_renderer.performance_viseme_plan(mouth.REPO_ROOT / mouth.CUE_SOURCE,
                                                                    fps=30, transition_frames=2)
        before = deepcopy(original)
        translated = mouth.translated_plan(original)
        self.assertEqual(len(translated), 228)
        self.assertEqual(before, original)
        for raw, new in zip(original, translated):
            self.assertEqual(new["frame"], raw["frame"])
            self.assertEqual(new["blend"], raw["blend"])
            for key in ("from_shape", "to_shape"):
                self.assertEqual(new["rhubarb_" + key], raw[key])
                self.assertEqual(new[key], mouth.RHUBARB_TO_ART[raw[key]])

    def test_unknown_and_double_translation_fail_before_mutation(self) -> None:
        row = [{"frame": 1, "from_shape": "X", "to_shape": "?", "blend": 1.0}]
        with self.assertRaises(ValueError):
            mouth.translated_plan(row)
        row[0]["to_shape"] = "A"
        with self.assertRaisesRegex(ValueError, "already"):
            mouth.translated_plan(mouth.translated_plan(row))

    def test_cache_and_plan_objects_restore_on_render_failure(self) -> None:
        raw = [{"frame": 1, "from_shape": "X", "to_shape": "G", "blend": 1.0}]
        native, adapter = {"old": object()}, {"old": object()}
        prepared = SimpleNamespace(visemes=raw, native_cache=native, adapter_cache=adapter)
        with self.assertRaisesRegex(RuntimeError, "injected"):
            with mouth.mouth_override(prepared):
                self.assertEqual(prepared.visemes[0]["to_shape"], "F")
                self.assertEqual(prepared.native_cache, {})
                self.assertEqual(prepared.adapter_cache, {})
                prepared.native_cache["new"] = 7
                raise RuntimeError("injected render failure")
        self.assertIs(prepared.visemes, raw)
        self.assertIs(prepared.native_cache, native)
        self.assertIs(prepared.adapter_cache, adapter)
        self.assertEqual(set(native), {"old"})
        self.assertEqual(set(adapter), {"old"})

    def test_excerpt_uses_original_scene_clock_and_only_preview_edge_fades(self) -> None:
        source = np.arange(484800 * 2, dtype=np.int32).reshape(-1, 2)
        before = source.copy()
        excerpt = mouth.preview_excerpt(source, 25, 162)
        exact = source[158400:379200]
        self.assertEqual(excerpt.shape, (220800, 2))
        self.assertTrue(np.array_equal(excerpt[1440:-1440], exact[1440:-1440]))
        self.assertFalse(np.any(excerpt[[0, -1]]))
        self.assertTrue(np.array_equal(source, before))


class MouthTranslationPixelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = mouth.direct_renderer.prepare_direct_address()

    def test_upstream_closed_lips_resolve_to_exact_plate_not_open_art_A(self) -> None:
        row = {"frame": 1, "from_shape": "A", "to_shape": "A", "blend": 1.0}
        mapped = mouth.translated_plan([row])[0]
        pixels, evidence = mouth.direct_renderer.controlled_native_frame(self.prepared, mapped, 0.0)
        self.assertEqual(evidence.oral_activation, 0.0)
        self.assertEqual(evidence.cavity_area, 0)
        self.assertTrue(np.array_equal(pixels, self.prepared.face.plate))

    def test_upstream_f_v_resolves_to_existing_labiodental_contact_art(self) -> None:
        raw = {"frame": 1, "from_shape": "G", "to_shape": "G", "blend": 1.0}
        mapped = mouth.translated_plan([raw])[0]
        _, evidence = mouth.direct_renderer.controlled_native_frame(self.prepared, mapped, 0.0)
        self.assertEqual(evidence.pose_weights["F"], 1.0)
        self.assertGreater(evidence.f_visible_incisor_area, 0)
        self.assertGreater(evidence.f_lower_lip_contact_length, 0)

    def test_actual_transition_changes_stay_inside_declared_perioral_support(self) -> None:
        support = mouth.prospective_native_support(self.prepared)
        for frame in (26, 27, 35, 49, 66, 67, 73, 94):
            raw = self.prepared.visemes[frame - 1]
            before, _ = mouth.direct_renderer.controlled_native_frame(self.prepared, raw, 0.0)
            with mouth.mouth_override(self.prepared):
                after, evidence = mouth.direct_renderer.controlled_native_frame(self.prepared, self.prepared.visemes[frame - 1], 0.0)
            self.assertFalse(np.any(before[~support] != after[~support]), frame)
            self.assertEqual(evidence.folded_triangles, 0, frame)
            self.assertEqual(evidence.depth_order_violation_pixels, 0, frame)
            self.assertGreater(evidence.minimum_triangle_area_ratio, 0.0, frame)

    def test_rest_retains_the_same_pixels_at_all_eye_closures(self) -> None:
        row = {"frame": 1, "from_shape": "X", "to_shape": "X", "blend": 1.0}
        for closure in (0.0, 0.5, 1.0):
            before, _ = mouth.direct_renderer.controlled_native_frame(self.prepared, row, closure)
            after, _ = mouth.direct_renderer.controlled_native_frame(self.prepared, mouth.translated_plan([row])[0], closure)
            self.assertTrue(np.array_equal(before, after))

    def test_reused_independent_adapter_matches_fresh_context_exactly(self) -> None:
        candidate = replace(self.prepared, visemes=mouth.translated_plan(self.prepared.visemes),
                            native_cache={}, adapter_cache={})
        original_plan = self.prepared.visemes
        for frame in (27, 35, 67):
            row = candidate.visemes[frame - 1]
            cached, _ = mouth.direct_renderer.controlled_native_frame(candidate, row, 0.0)
            repeated, _ = mouth.direct_renderer.controlled_native_frame(candidate, row, 0.0)
            self.assertIs(cached, repeated)
            with mouth.mouth_override(self.prepared):
                fresh, _ = mouth.direct_renderer.controlled_native_frame(self.prepared,
                                                                          self.prepared.visemes[frame - 1], 0.0)
            self.assertTrue(np.array_equal(cached, fresh), frame)
            self.assertIs(self.prepared.visemes, original_plan)


class MouthStudyPublishedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.package = mouth.REPO_ROOT / "collab/phase42_mouth_semantics_v1"
        cls.report = json.loads((cls.package / "mouth-semantics-study-report-v1.json").read_text(encoding="utf-8"))

    def test_published_bytes_and_native_scope_are_bound_to_actual_source(self) -> None:
        report = self.report
        self.assertEqual(report["implementation_sha256"], mouth.scene._hash(mouth.Path(mouth.__file__)))
        self.assertEqual(report["upstream_cue_sha256"], mouth.scene._hash(mouth.REPO_ROOT / mouth.CUE_SOURCE))
        self.assertEqual(report["mapping"], mouth.RHUBARB_TO_ART)
        self.assertEqual([row["source_frame"] for row in report["frames"]], list(mouth.STUDY_FRAMES))
        self.assertEqual(report["maximum_changed_pixels_outside_perioral_roi"], 0)
        self.assertEqual(report["maximum_folded_triangles"], 0)
        self.assertEqual(report["maximum_depth_order_violation_pixels"], 0)
        self.assertFalse(report["human_accepted"])
        self.assertFalse(report["production_promotion_allowed"])
        for name, entry in report["artifacts"].items():
            self.assertEqual(mouth.scene._hash(self.package / name), entry["sha256"], name)
        for row in report["frames"]:
            self.assertEqual(row["translated"]["frame"], row["raw"]["frame"])
            self.assertEqual(row["translated"]["blend"], row["raw"]["blend"])
            self.assertEqual(row["changed_outside_perioral_roi"], 0)
            if row["raw"]["to_shape"] == "A" and row["raw"]["blend"] == 1.0:
                self.assertEqual(row["candidate_cavity_area"], 0)

    def test_decoded_frame_clock_color_and_lossless_audio_are_actual_not_report_only(self) -> None:
        ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
        self.assertIsNotNone(ffmpeg)
        self.assertIsNotNone(ffprobe)
        mp4 = self.package / f"{mouth.NAME}.mp4"
        mov = self.package / f"{mouth.NAME}.mov"
        probe = mouth.scene._probe(mp4, ffprobe)
        video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
        self.assertEqual((int(video["nb_frames"]), int(video["nb_read_frames"])), (138, 138))
        self.assertEqual(video["avg_frame_rate"], "30/1")
        self.assertEqual(video["sample_aspect_ratio"], "1:1")
        for key in ("color_space", "color_transfer", "color_primaries"):
            self.assertEqual(video[key], "bt709")
        self.assertEqual(video["color_range"], "tv")
        frames = json.loads(subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_frames",
                                            "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(mp4)],
                                           check=True, capture_output=True).stdout)["frames"]
        self.assertEqual(len(frames), 138)
        for index, frame in enumerate(frames):
            self.assertAlmostEqual(float(frame["best_effort_timestamp_time"]), index / 30, delta=1e-6)
        wav = self.package / "accepted-audio-excerpt-with-preview-edge-fades.wav"
        expected, expected_probe = mouth.scene.picture._read_pcm24_wave(wav)
        decoded = subprocess.run([ffmpeg, "-v", "error", "-i", str(mov), "-map", "0:a:0", "-f", "s24le", "-"],
                                 check=True, capture_output=True).stdout
        self.assertEqual(hashlib.sha256(decoded).hexdigest(), expected_probe["data_sha256"])
        binding = mouth.scene.accepted_components()
        full, _ = mouth.scene.picture._read_pcm24_wave(mouth.REPO_ROOT / binding["audio"]["path"])
        self.assertTrue(np.array_equal(expected, mouth.preview_excerpt(full, 25, 162)))
        self.assertEqual(mouth.scene._video_hash(mov, ffmpeg), mouth.scene._video_hash(mp4, ffmpeg))


if __name__ == "__main__":
    unittest.main()
