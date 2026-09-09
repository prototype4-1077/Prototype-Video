"""Topology and pinned-input regression checks for the June v3 asset path."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline import june_studio_v3 as subject
from pipeline.june_studio import sha256


class JuneV3Tests(unittest.TestCase):
    def test_uvs_follow_vertex_identity_after_face_removal_and_rotation(self):
        reference = subject.uv_lookup({
            'faces': [[10, 11, 12], [12, 11, 13]],
            'face_corner_uvs': [[(.1, .1), (.8, .1), (.8, .8)], [(.2, .8), (.2, .1), (.1, .8)]],
        })
        # The first face was removed; the remaining face starts at another corner.
        result = subject.match_uvs([[3, 2, 1]], [10, 11, 12, 13], reference)
        self.assertEqual(result, [[(.1, .8), (.2, .8), (.2, .1)]])

    def test_uv_seam_coordinates_are_not_collapsed_per_vertex(self):
        reference = subject.uv_lookup({
            'faces': [[0, 1, 2], [2, 1, 3]],
            'face_corner_uvs': [[(0, 0), (.4, 0), (.4, 1)], [(.6, 1), (.6, 0), (1, 1)]],
        })
        result = subject.match_uvs([[0, 1, 2], [2, 1, 3]], [0, 1, 2, 3], reference)
        self.assertNotEqual(result[0][1], result[1][1])

    def test_unmatched_topology_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'topology'):
            subject.match_uvs([[0, 1, 2]], [100, 101, 102], {})

    def test_ambiguous_source_polygon_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            subject.uv_lookup({'faces': [[0, 1, 2], [2, 0, 1]],
                               'face_corner_uvs': [[(0, 0)]*3, [(1, 1)]*3]})

    def test_source_obj_handles_relative_indices_and_uv_corners(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'part.obj'
            path.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 0 1\nf -3/-3 -2/-2 -1/-1\n')
            obj = subject.read_obj(path)
            self.assertEqual(obj['faces'], [[0, 1, 2]])
            self.assertEqual(obj['face_corner_uvs'], [[(0., 0.), (1., 0.), (0., 1.)]])

    def test_changed_texture_is_rejected_before_building(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); skin = root/'skin.png'; mesh = root/'base.obj'
            skin.write_bytes(b'original'); mesh.write_bytes(b'source')
            manifest = root/'sources.json'
            manifest.write_text(json.dumps({'files': {'skin': {'filename': 'skin.png', 'sha256': sha256(skin)}},
                                           'downloads': {'reference_obj': {'filename': 'base.obj', 'sha256': sha256(mesh)}}}))
            with patch.object(subject, 'MANIFEST', manifest):
                self.assertEqual(subject.checked_assets(root)['skin'], skin)
                skin.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'changed v3 source'):
                    subject.checked_assets(root)


if __name__ == '__main__':
    unittest.main()
