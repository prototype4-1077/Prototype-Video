import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image, ImageChops

from pipeline.cartoon_viseme_atlas import (
    REQUIRED_VISEMES,
    atlas_cells,
    load_viseme_atlas_contract,
    mouth_patch_mask,
    render_viseme_preview,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "concept" / "style_frames" / "june_oxley_viseme_atlas_v1.json"


class CartoonVisemeAtlasTests(unittest.TestCase):
    def _fixture(self, root: Path, mutation=None) -> Path:
        source = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        if mutation:
            mutation(source)
        contract_dir = root / "concept" / "style_frames"
        contract_dir.mkdir(parents=True)
        shutil.copy2(
            ROOT / "concept" / "style_frames" / "june_oxley_viseme_atlas_v1.png",
            contract_dir / "june_oxley_viseme_atlas_v1.png",
        )
        shutil.copy2(
            ROOT / "concept" / "style_frames" / "june-oxley-canonical-turnaround-v1.png",
            contract_dir / "june-oxley-canonical-turnaround-v1.png",
        )
        contract = contract_dir / "june_oxley_viseme_atlas_v1.json"
        contract.write_text(json.dumps(source), encoding="utf-8")
        return contract

    def test_canonical_atlas_is_identity_locked_and_zero_cash(self):
        contract, image_path = load_viseme_atlas_contract(CONTRACT_PATH)
        self.assertEqual(tuple(contract["grid"]["order"]), REQUIRED_VISEMES)
        self.assertEqual(contract["neutral_viseme"], "X")
        self.assertEqual(contract["generation"]["cash_cost"], 0)
        self.assertEqual(contract["image"]["sha256"], "73df92931fd6f0e5d276ab85524232479a23d7e3049feb47b0cff7058a24f201")
        with Image.open(image_path) as atlas:
            self.assertEqual(atlas.size, (1254, 1254))
            cells = atlas_cells(atlas, contract)
        self.assertEqual(set(cells), set(REQUIRED_VISEMES))
        self.assertTrue(all(cell.size == (418, 418) for cell in cells.values()))
        self.assertTrue(all(ImageChops.difference(cells[shape], cells["X"]).getbbox() for shape in REQUIRED_VISEMES[:-1]))

    def test_feathered_patch_has_transparent_edges_and_opaque_center(self):
        contract, _ = load_viseme_atlas_contract(CONTRACT_PATH)
        mask = mouth_patch_mask(contract)
        self.assertEqual(mask.size, (242, 160))
        self.assertEqual(mask.getpixel((0, 0)), 0)
        self.assertEqual(mask.getpixel((mask.width - 1, mask.height - 1)), 0)
        self.assertGreaterEqual(mask.getpixel((mask.width // 2, mask.height // 2)), 250)

    def test_contract_rejects_order_hash_identity_and_patch_regressions(self):
        mutations = (
            (lambda item: item["grid"]["order"].reverse(), "canonical order"),
            (lambda item: item["image"].update(sha256="0" * 64), "image hash"),
            (lambda item: item["canonical_identity_reference"].update(sha256="0" * 64), "identity reference hash"),
            (lambda item: item.update(mouth_patch_box=[-1, 0, 20, 20]), "mouth_patch_box"),
            (lambda item: item["generation"].update(cash_cost=1), "zero-cash"),
        )
        for index, (mutation, message) in enumerate(mutations):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temp_dir:
                contract = self._fixture(Path(temp_dir), mutation)
                with self.assertRaisesRegex(ValueError, message):
                    load_viseme_atlas_contract(contract)

    def test_preview_is_bounded_deterministic_and_clears_stale_frames(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "edit" / "preview"
            frames = output / "frames"
            frames.mkdir(parents=True)
            stale = frames / "frame_9999.png"
            stale.write_bytes(b"stale")

            def create_video(command, *, check):
                self.assertTrue(check)
                Path(command[-1]).write_bytes(b"deterministic-test-video")

            with mock.patch(
                "pipeline.cartoon_viseme_atlas.subprocess.run",
                side_effect=create_video,
            ) as run:
                report = render_viseme_preview(
                    CONTRACT_PATH,
                    output,
                    ffmpeg=sys.executable,
                    transition_frames=2,
                    hold_frames=2,
                    output_scale=1,
                )
        self.assertFalse(stale.exists())
        self.assertEqual(report["frame_count"], 36)
        self.assertEqual(report["duration_seconds"], 1.2)
        self.assertEqual((report["width"], report["height"]), (418, 418))
        self.assertEqual(report["sequence"], list(REQUIRED_VISEMES))
        self.assertEqual(len(report["first_frame_sha256"]), 64)
        self.assertEqual(len(report["last_frame_sha256"]), 64)
        command = run.call_args.args[0]
        self.assertIn("libx264", command)
        self.assertIn("yuv420p", command)
        self.assertTrue(str(command[-1]).endswith(".partial.mp4"))

    def test_preview_rejects_unsafe_timing_or_scale(self):
        for kwargs in (
            {"fps": 0},
            {"transition_frames": 1},
            {"hold_frames": 1},
            {"output_scale": 0},
            {"output_scale": 5},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                render_viseme_preview(CONTRACT_PATH, "unused", **kwargs)


if __name__ == "__main__":
    unittest.main()
