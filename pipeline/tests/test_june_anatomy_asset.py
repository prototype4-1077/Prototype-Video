"""Offline asset integrity and topology gates for the CC0 June foundation."""
import gzip
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from pipeline.blender.june_anatomy_source import load


class JuneAnatomyAssetTests(unittest.TestCase):
    def test_source_is_complete_and_offline(self):
        data=load()
        for part in ('head','left_hand','right_hand'):
            mesh=data[part];count=len(mesh['vertices'])
            self.assertGreater(count,1000)
            self.assertEqual(len(set(mesh['source_vertex_ids'])),count)
            for face in mesh['faces']:
                self.assertEqual(len(face),len(set(face)))
                self.assertTrue(all(0<=i<count for i in face))
        self.assertEqual(data['provenance']['license'],'CC0-1.0')
        for side in ('l','r'):
            for digit in range(1,6):
                for joint in range(1,5):
                    self.assertEqual(len(data['joints'][f'{side}-finger-{digit}-{joint}']),3)

    def test_corruption_is_rejected_before_decompression(self):
        with patch.object(Path,'read_bytes',return_value=b'corrupted asset'),patch.object(gzip,'decompress') as decoder:
            with self.assertRaisesRegex(ValueError,'pinned provenance'):load()
            decoder.assert_not_called()

    def test_predecessor_fixture_restoration_matches_original_locks(self):
        root=Path(__file__).resolve().parents[2]
        contract=json.loads((root/'concept/characters/june_oxley_phase35_candidate03_blink_vui_probe_v2.json').read_text())
        filenames={'probe-report-v1.json','failure-v1.json','attempt-package-v1.json',
                   'h264-sps-trace-v1.txt','ffprobe-stream-v1.json','ffprobe-frames-v1.json'}
        restored={k:v for k,v in contract['locks'].items() if v['path'].startswith('collab/phase35_candidate_03_blink_vui_probe_attempt_01/') and Path(v['path']).name in filenames}
        self.assertEqual(len(restored),6)
        for reference in restored.values():
            self.assertEqual(hashlib.sha256((root/reference['path']).read_bytes()).hexdigest(),reference['sha256'])


if __name__=='__main__':unittest.main()
