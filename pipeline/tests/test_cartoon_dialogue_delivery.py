from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from pipeline import cartoon_dialogue_delivery as delivery


RECIPE = delivery.new.ROOT / "concept/scenes/june-rest-your-hands-v1.json"


class DialogueDeliveryTests(unittest.TestCase):
    def test_existing_export_is_rejected_before_reading_or_executing(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(delivery.new, "compile_scene") as compile:
            with self.assertRaises(FileExistsError):
                delivery.recover(RECIPE, Path("unused"), Path(folder), expected_picture_sha256="unused", render_source=Path("unused"))
            compile.assert_not_called()

    def test_non_audio_failure_cannot_be_recovered_as_an_audio_only_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            prior = Path(folder)/"prior"
            prior.mkdir()
            (prior/"failure.json").write_text(json.dumps({"error":"protected region violation"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "AAC-quality"):
                delivery.recover(RECIPE, prior, Path(folder)/"output", expected_picture_sha256="unused", render_source=Path("unused"))
            self.assertFalse((Path(folder)/"output").exists())

    def test_pixel_source_identity_excludes_delivery_only_changes_but_not_render_changes(self):
        source = Path(delivery.new.__file__).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as folder:
            changed = Path(folder)/"source.py"
            changed.write_text(source.replace('AAC_BITRATE = "512k"', 'AAC_BITRATE = "256k"'), encoding="utf-8")
            self.assertEqual(delivery.pixel_code_hash(changed), delivery.pixel_code_hash(Path(delivery.new.__file__)))
            changed.write_text(source.replace('"runtime_performance_human_accepted": False', '"runtime_performance_human_accepted": True'), encoding="utf-8")
            self.assertNotEqual(delivery.pixel_code_hash(changed), delivery.pixel_code_hash(Path(delivery.new.__file__)))


if __name__ == "__main__":
    unittest.main()
