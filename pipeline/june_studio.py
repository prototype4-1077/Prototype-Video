"""Small, offline-first production utilities for June's reusable 3D studio.

External tools/assets are downloaded once, checksum verified, and reused. Shot
cache keys include actual input bytes; an incomplete render is never a hit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
import wave
import zipfile

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "concept/characters/june_studio_sources_v1.json"
USER_AGENT = "JuneOxleyStudio/1.0 (Prototype-Video; https://github.com/prototype4-1077/Prototype-Video)"
VOICE_ID = "NOpBlnGInO9m6vDvFkFC"


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def fetch_pinned(spec, directory):
    """Fetch a declared asset; network/identity failures do not invent a fallback."""
    target = Path(directory) / spec["filename"]
    if Path(spec["filename"]).name != spec["filename"]:
        raise ValueError("asset filename must be a basename")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and sha256(target) == spec["sha256"]:
        return target
    partial = target.with_name(target.name + ".partial")
    request = urllib.request.Request(spec["url"], headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=45) as response, partial.open("wb") as output:
            count = 0
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > spec["bytes"]:
                    raise ValueError("asset exceeds its pinned size")
                output.write(block)
        if count != spec["bytes"] or sha256(partial) != spec["sha256"]:
            raise ValueError("downloaded asset does not match its pinned identity")
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return target


def bootstrap(directory, include_rhubarb=True):
    directory = Path(directory).resolve()
    manifest = json.loads(MANIFEST.read_text())
    receipt = {"schema_version": 1, "manifest_sha256": sha256(MANIFEST), "files": {}}
    for name, spec in manifest["downloads"].items():
        if name == "rhubarb_linux" and not include_rhubarb:
            continue
        path = fetch_pinned(spec, directory)
        receipt["files"][name] = {"path": str(path), "sha256": sha256(path), "license": spec["license"]}
        print("Verified " + name, flush=True)
        if name == "rhubarb_linux":
            root = directory / "rhubarb"
            root.mkdir(exist_ok=True)
            # Validate every path before any extraction, including Unix symlinks.
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    destination = (root / info.filename).resolve()
                    if not destination.is_relative_to(root) or (info.external_attr >> 16) & 0o170000 == 0o120000:
                        raise ValueError("unsafe archive member")
                archive.extractall(root)
            binary = root / "Rhubarb-Lip-Sync-1.14.0-Linux/rhubarb"
            binary.chmod(0o755)
            receipt["rhubarb_binary"] = str(binary)
            receipt["rhubarb_version"] = subprocess.check_output([str(binary), "--version"], text=True).strip()
    atomic_json(directory / "tool-receipt.json", receipt)
    return receipt


def input_identity(files, settings):
    payload = {"files": {str(k): sha256(v) for k, v in sorted(files.items())}, "settings": settings}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest(), payload


def cache_valid(directory, identity, frame_count):
    """Verify completion, expected frame count, and encoded file integrity."""
    directory = Path(directory)
    receipt = directory / "complete.json"
    if not receipt.is_file():
        return False
    try:
        record = json.loads(receipt.read_text())
        if record["identity"] != identity or record["frame_count"] != frame_count:
            return False
        hashes = record["frame_sha256"]
        expected = {f"frame_{frame:04d}.png" for frame in range(1, frame_count + 1)}
        if set(hashes) != expected:
            return False
        return all((directory / name).is_file() and sha256(directory / name) == digest for name, digest in hashes.items())
    except (ValueError, KeyError, OSError, TypeError):
        return False


def complete_cache(directory, identity, frame_count, inputs):
    directory = Path(directory)
    hashes = {f"frame_{frame:04d}.png": sha256(directory / f"frame_{frame:04d}.png")
              for frame in range(1, frame_count + 1)}
    atomic_json(directory / "complete.json", {"identity": identity, "frame_count": frame_count,
                                              "inputs": inputs, "frame_sha256": hashes})


def status(directory, stage, **details):
    value = {"stage": stage, "updated_unix": time.time(), **details}
    atomic_json(Path(directory) / "status.json", value)
    print(json.dumps(value), flush=True)


def preserved_voice(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'voiceover-manifest.json').read_text())
    if manifest.get('voice_id') != VOICE_ID:
        raise ValueError('June studio requires the established Spuds voice; no substitution is allowed')
    checksums = dict((parts[1].lstrip('*'), parts[0]) for line in
                     (directory / 'SHA256SUMS').read_text().splitlines()
                     if len(parts := line.split()) == 2)
    if sha256(directory / 'vo.mp3') != checksums.get('vo.mp3'):
        raise ValueError('voice take does not match its preserved checksum')


def prepare_voice(directory, rhubarb):
    """Bind validated mouth cues to the exact preserved take and decoded WAV."""
    from pipeline.cartoon_lipsync import run_rhubarb
    directory = Path(directory).resolve()
    preserved_voice(directory)
    script = json.loads((directory / 'script.json').read_text())
    dialogue = ' '.join(scene['text'] for scene in script['scenes'])
    if not dialogue.strip():
        raise ValueError('speech alignment requires the actual dialogue text')
    wav = directory / 'dialogue.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(directory / 'vo.mp3'),
                    '-ar', '48000', '-ac', '1', str(wav)], check=True)
    cues = run_rhubarb(wav, directory / 'mouth-cues.json', dialogue=dialogue, rhubarb_bin=rhubarb)
    with wave.open(str(wav)) as stream:
        duration = stream.getnframes() / stream.getframerate()
    if abs(duration - cues['metadata']['duration']) > .03:
        raise ValueError('speech cue clock differs from decoded audio duration')
    receipt = {'schema_version': 1, 'voice_id': VOICE_ID, 'duration_seconds': duration,
               'rhubarb_sha256': sha256(rhubarb),
               'files': {name: sha256(directory / name) for name in
                         ('vo.mp3', 'dialogue.wav', 'mouth-cues.json', 'script.json')}}
    atomic_json(directory / 'cue-source.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    install = sub.add_parser("bootstrap")
    install.add_argument("directory")
    install.add_argument("--assets-only", action="store_true")
    voice = sub.add_parser("prepare-voice")
    voice.add_argument("directory")
    voice.add_argument("--rhubarb", required=True)
    args = parser.parse_args()
    if args.command == "bootstrap":
        bootstrap(args.directory, include_rhubarb=not args.assets_only)
    elif args.command == "prepare-voice":
        prepare_voice(args.directory, args.rhubarb)


if __name__ == "__main__":
    main()
