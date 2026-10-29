"""Rebuild the existing 75-frame opening from pinned, repository-local source art.

This is a pixel-equivalence adapter, not a delivery/encode authorization. It does
not call or weaken the historical Ledger Pour top-level execution gate. The
picture JSON supplies only scene data; the existing pour loader still enforces
its asset, registration, liquid, camera and source-clock invariants.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import PIL
from PIL import Image

from pipeline import cartoon_ledger_pour as ledger
from pipeline import cartoon_pour_layers as pour


REPO_ROOT = Path(__file__).resolve().parents[1]
PICTURE_PATH = "concept/characters/june_oxley_phase36_ledger_pour_v1.json"
POUR_PATH = "concept/style_frames/june_golden_scene_gs060_layered_pour_v1.json"
INVENTORY_PATH = "collab/phase42_integrated_scene_review_v1/source-frame-inventory-v1.json"
CLOCK = {"width": 1920, "height": 1080, "fps": 30, "frame_count": 75, "duration_seconds": 2.5}
SOURCE_START, SOURCE_END = 112, 186
# JSON uses UTF-8 canonical sort_keys/compact/ensure_ascii=False; source text
# uses CRLF -> LF normalization only; art and RGB arrays use exact raw bytes.
PINNED_JSON = {
    PICTURE_PATH: "d1900e8ee1e9584a4f4197038375119554e402f9d2664cdfcb8ba5f78fa3f8d9",
    POUR_PATH: "88282f3b8106e6f7d20fdf80b556a2f6143f921e646482201fd4f323cccd23ae",
    INVENTORY_PATH: "9d1e0ed0c33a7f96f65d35bd1b5ad12321fca395ccc1bb8ca3e625cddc1129de",
}
PINNED_SOURCE_LF = {
    "pipeline/cartoon_ledger_pour.py": "22965cf665ff8a3c93b2423521b661c19463d655698a2e44f24e5f84dfde13c8",
    "pipeline/cartoon_pour_layers.py": "3e92ff5e328b2c259fea61e7317e90b6e6f5f4774ca8ac3c58c3121df22ab208",
}
OPENING_ROWS_SHA256 = "747abb15041099c73b3af30ed28422cbdb081140d23cfc80e7f8a9e608c23ab8"


class SourceOpeningError(RuntimeError):
    """A source, pixel or clock lock failed; no mismatching frame is yielded."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise SourceOpeningError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _file_record(relative: str, expected: str, domain: str) -> tuple[dict[str, Any], Any]:
    if domain not in ("canonical_json_utf8", "lf_normalized_text", "raw_bytes"):
        raise SourceOpeningError(f"unsupported hash domain: {domain}")
    path = (REPO_ROOT / relative).resolve()
    if not path.is_relative_to(REPO_ROOT.resolve()):
        raise SourceOpeningError(f"source dependency escapes repository: {relative}")
    raw = path.read_bytes()
    payload = json.loads(raw) if domain == "canonical_json_utf8" else None
    digest = _canonical(payload) if domain == "canonical_json_utf8" else _sha(
        raw.replace(b"\r\n", b"\n") if domain == "lf_normalized_text" else raw
    )
    _equal(digest, expected, f"{relative} ({domain}) SHA-256")
    return {"path": relative, "hash_domain": domain, "sha256": digest, "raw_sha256": _sha(raw), "bytes": len(raw)}, payload


def _inputs() -> dict[str, Any]:
    dependencies = []
    parsed = {}
    for relative, expected in PINNED_JSON.items():
        record, parsed[relative] = _file_record(relative, expected, "canonical_json_utf8")
        dependencies.append(record)
    for relative, expected in PINNED_SOURCE_LF.items():
        record, _ = _file_record(relative, expected, "lf_normalized_text")
        dependencies.append(record)
    picture, source = parsed[PICTURE_PATH], parsed[POUR_PATH]
    _equal({key: picture["clock"][key] for key in ("width", "height", "fps")},
           {key: CLOCK[key] for key in ("width", "height", "fps")}, "picture geometry/clock")
    _equal(picture["shots"][0]["output_frames"], [1, 75], "opening output mapping")
    _equal(picture["shots"][0]["source_frames"], [SOURCE_START, SOURCE_END], "opening source mapping")
    _equal(picture["shots"][0]["transform"], "phase23_camera_exact", "opening camera")
    _equal(picture["locks"]["phase23_contract"]["path"], POUR_PATH, "pour data path")
    # The historical raw-text lock happens to hold LF bytes. Declare that domain
    # explicitly here; do not modify ledger.load_contract or claim it passed.
    record, _ = _file_record(POUR_PATH, picture["locks"]["phase23_contract"]["sha256"], "lf_normalized_text")
    dependencies.append(record)
    references = [source["identity_reference"], source["style_reference"], source["liquid_reference"],
                  source["background"], source["background"]["source_provenance"]]
    references += [pose[key] for pose in source["poses"] for key in ("foreground", "source_art")]
    for relative, expected in sorted({ref["path"]: ref["sha256"] for ref in references}.items()):
        record, _ = _file_record(relative, expected, "raw_bytes")
        dependencies.append(record)
    # Uses the existing strict asset/contact/camera/clock validator, no renderer.
    validated, _, _ = pour.load_pour_layer_contract(REPO_ROOT / POUR_PATH)
    _equal(validated, source, "validated pour scene data")
    assets = {"background": source["background"]["sha256"],
              **{f"pose_{pose['id']}": pose["foreground"]["sha256"] for pose in source["poses"]}}
    inventory = parsed[INVENTORY_PATH]
    _equal(len(inventory), 303, "published inventory length")
    rows = inventory[:75]
    _equal(_canonical(rows), OPENING_ROWS_SHA256, "published opening inventory")
    for output_frame, row in enumerate(rows, 1):
        _equal(row["output_frame"], output_frame, "inventory output frame")
        _equal(row["pour_source_frame"], SOURCE_START + output_frame - 1, "inventory source frame")
        _equal(row["original_pour_pixels_preserved"], True, "published opening preservation")
    _equal(PIL.__version__, "12.2.0", "Pillow raster toolchain")
    _equal(np.__version__, "2.4.4", "NumPy raster toolchain")
    provenance = {
        "adapter": "pipeline/cartoon_source_opening.py",
        "adapter_lf_sha256": _sha(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
        "scope": "existing opening RGB equivalence only; no delivery or encode authorization",
        "clock": dict(CLOCK), "source_frames": [SOURCE_START, SOURCE_END],
        "output_frames": [1, 75], "source_camera_clock_frame_count": source["output"]["frame_count"],
        "opening_inventory_canonical_sha256": OPENING_ROWS_SHA256,
        "dependencies": dependencies, "runtime_asset_hashes": assets,
        "toolchain": {"pillow": PIL.__version__, "numpy": np.__version__},
        "external_scene_cache_used": False,
    }
    # Only the one data reference required by _prepare_pour crosses this boundary.
    return {"picture": {"locks": {"phase23_contract": picture["locks"]["phase23_contract"]}},
            "source": source, "assets": assets, "rows": rows, "provenance": provenance}


def preflight() -> dict[str, Any]:
    """Validate and report exact local source provenance; renders/writes nothing."""
    return _inputs()["provenance"]


def frames() -> Iterator[tuple[int, np.ndarray, dict[str, Any]]]:
    """Yield F001..F075 as independent RGB uint8 arrays, checked before yield.

    Source-frame numbers (112..186), not output time, drive the unchanged
    258-frame camera/effects clock. Call close() when stopping early, or use
    contextlib.closing(frames()). All returned prepared assets are then closed.
    """
    inputs = _inputs()
    prepared = None
    try:
        prepared = ledger._prepare_pour(inputs["picture"], inputs["assets"])
        phase23, background, registered, smears = prepared
        _equal(phase23, inputs["source"], "prepared pour data")
        _equal(_inputs()["provenance"], inputs["provenance"], "source state after prepare")
        for row in inputs["rows"]:
            output_frame, source_frame = row["output_frame"], row["pour_source_frame"]
            entry = pour.timeline_entry_for_frame(phase23["timeline"], source_frame)
            layer = registered[entry["pose_id"]] if entry["type"] == "pose" else smears[source_frame]
            image, liquid = pour.compose_pour_frame(background, layer, phase23, source_frame)
            try:
                _equal(image.mode, "RGB", "rendered color mode")
                frame = np.array(image, dtype=np.uint8, copy=True)
            finally:
                image.close()
            _equal(frame.shape, (1080, 1920, 3), "rendered RGB shape")
            digest = _sha(frame.tobytes())
            _equal(digest, row["rgb_sha256"], f"output F{output_frame:03d} / source F{source_frame:03d} RGB")
            _equal(liquid["frame"], source_frame, "liquid source clock")
            _equal(liquid["rendered_spill_pixels_source"], 0, "liquid spill")
            _equal(liquid["spout_start_error_px_source"], 0.0, "liquid spout contact")
            yield output_frame, frame, {
                "output_frame": output_frame, "source_frame": source_frame,
                "output_pts": [output_frame - 1, 30], "source_pts": [source_frame - 1, 30],
                "rgb_hash_domain": "rgb24_row_major_raw_bytes", "rgb_sha256": digest,
                "published_rgb_sha256": row["rgb_sha256"], "published_inventory_match": True,
                "opening_inventory_canonical_sha256": OPENING_ROWS_SHA256,
                "transform": "phase23_camera_exact", "liquid": liquid,
            }
        _equal(_inputs()["provenance"], inputs["provenance"], "source state after rendering")
    finally:
        if prepared is not None:
            ledger._close_pour_assets(prepared[1], prepared[2], prepared[3])


def write_audit(output_directory: str | Path) -> dict[str, Any]:
    """Stream all 75 hashes and at most three PNGs into a NEW evidence directory."""
    output = Path(output_directory).resolve()
    output.mkdir(parents=True, exist_ok=False)
    provenance = preflight()
    records = []
    with closing(frames()) as stream:
        for number, frame, metrics in stream:
            records.append(metrics)
            if number in (1, 45, 75):
                with (output / f"output-f{number:03d}-source-f{metrics['source_frame']:03d}.png").open("xb") as destination:
                    with Image.fromarray(frame) as image:
                        image.save(destination, format="PNG")
    _equal(len(records), 75, "audit rendered frame count")
    report = {"provenance": provenance, "verified_frames": len(records), "rgb_hash_mismatches": 0,
              "all_published_opening_hashes_match": True, "frames": records,
              "encoded_media_created": False, "scene_cache_created": False}
    with (output / "source-opening-audit-v1.json").open("x", encoding="utf-8", newline="\n") as destination:
        json.dump(report, destination, indent=2)
        destination.write("\n")
    return {"audit": str(output / "source-opening-audit-v1.json"), "verified_frames": len(records),
            "all_published_opening_hashes_match": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(write_audit(args.audit_directory) if args.audit_directory else preflight(), indent=2))
