"""Pinned source data and topology-safe helpers for June's v3 studio asset."""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import zipfile

from pipeline.june_studio import REPO, fetch_pinned, sha256

MANIFEST = REPO / 'concept/characters/june_studio_sources_v3.json'


def prepare_assets(directory, cache):
    directory, cache = Path(directory), Path(cache)
    manifest = json.loads(MANIFEST.read_text())
    directory.mkdir(parents=True, exist_ok=True)
    missing = [key for key, spec in manifest['files'].items()
               if not (directory / spec['filename']).is_file()
               or sha256(directory / spec['filename']) != spec['sha256']]
    if missing:
        archive = fetch_pinned(manifest['downloads']['system_assets'], cache)
        with zipfile.ZipFile(archive) as bundle:
            for key in missing:
                spec = manifest['files'][key]
                target = directory / spec['filename']
                if target.parent != directory or Path(spec['filename']).name != spec['filename']:
                    raise ValueError('source output filename must be a basename')
                data = bundle.read(spec['archive_path'])
                import hashlib
                if hashlib.sha256(data).hexdigest() != spec['sha256']:
                    raise ValueError('source asset checksum mismatch: ' + key)
                target.write_bytes(data)
    source = fetch_pinned(manifest['downloads']['reference_obj'], directory)
    return {key: directory / spec['filename'] for key, spec in manifest['files'].items()} | {'reference_obj': source}


def checked_assets(directory):
    directory = Path(directory)
    manifest = json.loads(MANIFEST.read_text())
    result = {}
    specs = {**manifest['files'], 'reference_obj': manifest['downloads']['reference_obj']}
    for key, spec in specs.items():
        path = directory / spec['filename']
        if not path.is_file() or sha256(path) != spec['sha256']:
            raise ValueError('missing or changed v3 source: ' + key + '; run prepare-assets')
        result[key] = path
    return result


def read_obj(path):
    """Read only geometry/UV data; no material paths or executable extensions."""
    vertices, uv, faces, corners = [], [], [], []
    for line in Path(path).read_text().splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == 'v':
            vertices.append(tuple(float(x) for x in fields[1:4]))
        elif fields[0] == 'vt':
            uv.append(tuple(float(x) for x in fields[1:3]))
        elif fields[0] == 'f':
            face, texture = [], []
            for field in fields[1:]:
                values = field.split('/')
                if len(values) < 2 or not values[1]:
                    raise ValueError('v3 source polygon has no texture coordinates')
                vi, ti = int(values[0]), int(values[1])
                vi = vi - 1 if vi > 0 else len(vertices) + vi
                ti = ti - 1 if ti > 0 else len(uv) + ti
                if not (0 <= vi < len(vertices) and 0 <= ti < len(uv)):
                    raise ValueError('source OBJ polygon index is out of range')
                face.append(vi); texture.append(uv[ti])
            if len(face) < 3 or len(face) != len(set(face)):
                raise ValueError('invalid source polygon')
            faces.append(face); corners.append(texture)
    if not all(math.isfinite(x) for p in vertices + uv for x in p):
        raise ValueError('nonfinite source coordinate')
    return {'vertices': vertices, 'faces': faces, 'face_corner_uvs': corners}


def uv_lookup(source):
    """Use polygon identities, retaining each corner's seam-specific UV."""
    result = {}
    for face, coordinates in zip(source['faces'], source['face_corner_uvs']):
        signature = tuple(sorted(face))
        value = dict(zip(face, coordinates))
        if signature in result and result[signature] != value:
            raise ValueError('ambiguous UV polygon in source')
        result[signature] = value
    return result


def match_uvs(polygons, source_vertex_ids, reference):
    result = []
    for polygon in polygons:
        try:
            identities = [source_vertex_ids[index] for index in polygon]
            match = reference[tuple(sorted(identities))]
            result.append([match[identity] for identity in identities])
        except (IndexError, KeyError) as error:
            raise ValueError('delivered topology cannot be matched to the source UVs') from error
    return result


def connected_components(faces, vertex_count):
    parents = list(range(vertex_count))
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]; i = parents[i]
        return i
    for face in faces:
        for i in face[1:]:
            parents[root(i)] = root(face[0])
    groups = defaultdict(list)
    for i in range(vertex_count):
        groups[root(i)].append(i)
    return list(groups.values())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--directory', required=True); p.add_argument('--cache', required=True)
    args = p.parse_args()
    print(json.dumps({key: str(value) for key, value in prepare_assets(args.directory, args.cache).items()}, indent=2))


if __name__ == '__main__':
    main()
