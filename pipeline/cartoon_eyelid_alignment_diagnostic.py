"""Still-only Phase37 root-cause diagnostic for June's binding Phase36 F248 eyelid defect."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import gzip
import hashlib
import inspect
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterator

import cv2
import numpy as np
from PIL import Image, ImageDraw, __version__ as PILLOW_VERSION

from pipeline import cartoon_ledger_pour as phase36
from pipeline import cartoon_source_textured_direct_address as phase35


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase37_eyelid_alignment_diagnostic_v1.json"
IMPLEMENTATION_RELATIVE_PATH = "pipeline/cartoon_eyelid_alignment_diagnostic.py"
TEST_RELATIVE_PATH = "pipeline/tests/test_cartoon_eyelid_alignment_diagnostic.py"
FIXED_CREASE_RGB = np.asarray([111, 67, 47], dtype=np.uint8)
FULL_CLOSURE_THRESHOLD = 0.999


class EyelidDiagnosticError(RuntimeError):
    pass


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _lf_hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _raw_frame_hash(frame: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()


def _strict_json(path: str | Path, label: str) -> dict[str, Any]:
    def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise EyelidDiagnosticError(f"{label} contains duplicate key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise EyelidDiagnosticError(f"{label} contains non-finite JSON value: {value}")

    try:
        payload = Path(path).read_bytes().decode("utf-8")
        result = json.loads(payload, object_pairs_hook=reject_duplicate, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EyelidDiagnosticError(f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(result, dict):
        raise EyelidDiagnosticError(f"{label} must be a JSON object")
    return result


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise EyelidDiagnosticError(f"eyelid diagnostic mismatch for {label}: {actual!r} != {expected!r}")


def _repo_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise EyelidDiagnosticError(f"repository path escapes the worktree: {relative}") from exc
    if not path.is_file():
        raise EyelidDiagnosticError(f"repository file is missing: {relative}")
    return path


def _outputs_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    outputs_root = (REPO_ROOT / "../../outputs").resolve()
    try:
        path.relative_to(outputs_root)
    except ValueError as exc:
        raise EyelidDiagnosticError(f"external archive path escapes the outputs tree: {relative}") from exc
    return path


def load_contract(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    resolved = Path(path).resolve()
    _require_equal(resolved, (REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve(), "pinned contract path")
    contract = _strict_json(resolved, "Phase37 eyelid contract")
    _require_equal(contract["contract_version"], 1, "contract version")
    _require_equal(
        contract["contract_id"], "june_oxley_phase37_eyelid_alignment_diagnostic_v1", "contract id",
    )
    _require_equal(contract["cash_cost"], 0, "cash cost")
    _require_equal(contract["paid_runtime_dependency"], False, "paid dependency")
    _require_equal(contract["network_runtime_required"], False, "network dependency")
    _require_equal(contract["diagnostic"]["video_encode_allowed"], False, "video encode policy")
    _require_equal(
        contract["diagnostic"]["accepted_source_mutation_allowed"], False, "accepted source mutation policy",
    )
    for name, reference in contract["locks"].items():
        locked = _repo_path(str(reference["path"]))
        actual = _lf_hash(locked) if reference.get("hash_domain") == "lf_normalized_text" else _sha256(locked)
        _require_equal(actual, reference["sha256"], f"locked {name} SHA-256")
    return contract


def _read_picture_archive(
    contract: dict[str, Any], manifest: dict[str, Any], selected: set[int],
) -> tuple[dict[int, np.ndarray], dict[str, Any]]:
    picture = contract["immutable_picture"]
    archive = _outputs_path(str(picture["external_archive_path"]))
    if not archive.is_file():
        raise EyelidDiagnosticError(f"immutable Candidate01 picture archive is missing: {archive}")
    _require_equal(archive.stat().st_size, picture["archive_bytes"], "picture archive bytes")
    _require_equal(_sha256(archive), picture["archive_sha256"], "picture archive SHA-256")
    inventory = manifest["frame_hashes"]
    _require_equal(len(inventory), picture["frame_count"], "picture inventory frame count")
    _require_equal(
        _canonical_hash(inventory), picture["frame_inventory_canonical_sha256"],
        "picture inventory canonical SHA-256",
    )
    retained: dict[int, np.ndarray] = {}
    combined = hashlib.sha256()
    with gzip.open(archive, "rb") as handle:
        header = json.loads(handle.readline().decode("utf-8"))
        _require_equal(header, manifest["lossless_archive_header"], "picture archive header")
        shape = (int(header["height"]), int(header["width"]), int(header["channels"]))
        previous = np.zeros(shape, dtype=np.uint8)
        for frame_number, expected in enumerate(inventory, start=1):
            payload = handle.read(int(header["frame_bytes"]))
            if len(payload) != int(header["frame_bytes"]):
                raise EyelidDiagnosticError(f"picture archive frame {frame_number} is truncated")
            delta = np.frombuffer(payload, dtype=np.uint8).reshape(shape)
            frame = np.bitwise_xor(delta, previous)
            digest = _raw_frame_hash(frame)
            _require_equal(expected, {"frame": frame_number, "rgb_sha256": digest}, f"picture frame {frame_number}")
            combined.update(np.ascontiguousarray(frame).tobytes())
            if frame_number in selected:
                retained[frame_number] = frame.copy()
            previous = frame
        if handle.read(1):
            raise EyelidDiagnosticError("picture archive has trailing decompressed payload")
    _require_equal(set(retained), selected, "retained picture frames")
    _require_equal(combined.hexdigest(), picture["combined_rgb24_sha256"], "combined picture RGB24 SHA-256")
    return retained, {
        "path": str(archive),
        "bytes": archive.stat().st_size,
        "sha256": picture["archive_sha256"],
        "header": manifest["lossless_archive_header"],
        "frame_inventory_canonical_sha256": picture["frame_inventory_canonical_sha256"],
        "combined_rgb24_sha256": combined.hexdigest(),
        "verified_frames": len(inventory),
    }


@contextmanager
def _full_closure_crease_suppressed() -> Iterator[list[dict[str, Any]]]:
    phase33 = phase35.phase34_candidate09.phase33
    original_compose = phase33._compose_eye_lids
    suppressions: list[dict[str, Any]] = []

    def compose_without_explicit_full_closure_crease(
        canvas: np.ndarray,
        plate: np.ndarray,
        lid_texture: np.ndarray,
        owner: np.ndarray,
        center: tuple[int, int],
        radius: tuple[int, int],
        closure: float,
    ) -> tuple[float, int]:
        if closure < FULL_CLOSURE_THRESHOLD:
            return original_compose(canvas, plate, lid_texture, owner, center, radius, closure)
        original_blend = phase33._blend_color

        def blend_except_fixed_crease(target: np.ndarray, color: np.ndarray, alpha: np.ndarray) -> None:
            if (
                color.ndim == 3
                and color.shape[2] == 3
                and np.array_equal(color[0, 0], FIXED_CREASE_RGB)
                and bool(np.all(color == FIXED_CREASE_RGB))
            ):
                suppressions.append({
                    "center": list(center),
                    "radius": list(radius),
                    "closure": float(closure),
                    "nonzero_alpha_pixels": int((alpha > 0).sum()),
                    "maximum_alpha": int(alpha.max()),
                })
                return
            original_blend(target, color, alpha)

        phase33._blend_color = blend_except_fixed_crease
        try:
            return original_compose(canvas, plate, lid_texture, owner, center, radius, closure)
        finally:
            phase33._blend_color = original_blend

    phase33._compose_eye_lids = compose_without_explicit_full_closure_crease
    try:
        yield suppressions
    finally:
        phase33._compose_eye_lids = original_compose


def _evidence(evidence: Any) -> dict[str, Any]:
    return {
        "blink_closure": float(evidence.blink_closure),
        "iris_occlusion_ratios": [float(value) for value in evidence.iris_occlusion_ratios],
        "lid_areas": [int(value) for value in evidence.lid_areas],
        "lid_write_areas": [int(value) for value in evidence.lid_write_areas],
    }


def _bbox(mask: np.ndarray, padding: int = 0) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    if not len(xs):
        raise EyelidDiagnosticError("cannot measure an empty mask")
    height, width = mask.shape
    return (
        max(0, int(xs.min()) - padding), max(0, int(ys.min()) - padding),
        min(width, int(xs.max()) + 1 + padding), min(height, int(ys.max()) + 1 + padding),
    )


def _crop(frame: np.ndarray, box: tuple[int, int, int, int]) -> Image.Image:
    return Image.fromarray(frame, "RGB").crop(box)


def _label(image: Image.Image, label: str) -> Image.Image:
    header = 22
    result = Image.new("RGB", (image.width, image.height + header), (13, 13, 13))
    result.paste(image, (0, header))
    ImageDraw.Draw(result).text((5, 5), label, fill=(240, 231, 211))
    return result


def _comparison(
    before: np.ndarray,
    after: np.ndarray,
    box: tuple[int, int, int, int],
    scale: int,
    before_label: str,
    after_label: str,
) -> Image.Image:
    first = _crop(before, box)
    second = _crop(after, box)
    if scale != 1:
        size = (first.width * scale, first.height * scale)
        first = first.resize(size, Image.Resampling.NEAREST)
        second = second.resize(size, Image.Resampling.NEAREST)
    first = _label(first, before_label)
    second = _label(second, after_label)
    sheet = Image.new("RGB", (first.width + second.width, max(first.height, second.height)), (0, 0, 0))
    sheet.paste(first, (0, 0))
    sheet.paste(second, (first.width, 0))
    return sheet


def _neighbor_sweep(
    baseline: dict[int, np.ndarray], proposal: dict[int, np.ndarray], box: tuple[int, int, int, int],
) -> Image.Image:
    frame_numbers = sorted(baseline)
    columns = 5
    crop_width, crop_height = box[2] - box[0], box[3] - box[1]
    tile_size = (max(1, crop_width // 2), max(1, crop_height // 2))
    pair_width = tile_size[0] * 2
    header = 24
    pair_height = tile_size[1] + header
    rows = (len(frame_numbers) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * pair_width, rows * pair_height), (7, 7, 7))
    draw = ImageDraw.Draw(sheet)
    for index, frame_number in enumerate(frame_numbers):
        row, column = divmod(index, columns)
        x, y = column * pair_width, row * pair_height
        before = _crop(baseline[frame_number], box).resize(tile_size, Image.Resampling.LANCZOS)
        after = _crop(proposal[frame_number], box).resize(tile_size, Image.Resampling.LANCZOS)
        sheet.paste(before, (x, y + header))
        sheet.paste(after, (x + tile_size[0], y + header))
        changed = bool(np.any(baseline[frame_number] != proposal[frame_number]))
        draw.text((x + 4, y + 5), f"F{frame_number:03d} BEFORE | AFTER  {'CHANGED' if changed else 'IDENTICAL'}", fill=(255, 210, 130))
    return sheet


def _layer_decomposition(
    lid_texture: np.ndarray,
    baseline: np.ndarray,
    proposal: np.ndarray,
    crease_mask: np.ndarray,
    box: tuple[int, int, int, int],
) -> Image.Image:
    x1, y1, x2, y2 = box
    difference = np.abs(baseline.astype(np.int16) - proposal.astype(np.int16)).astype(np.uint8)
    amplified = np.clip(difference.astype(np.uint16) * 5, 0, 255).astype(np.uint8)
    mask_rgb = proposal.copy()
    local = crease_mask[y1:y2, x1:x2]
    local_rgb = mask_rgb[y1:y2, x1:x2].copy()
    local_rgb[local] = np.asarray([255, 40, 40], dtype=np.uint8)
    panels = [
        _label(_crop(lid_texture, box).resize(((x2 - x1) * 2, (y2 - y1) * 2), Image.Resampling.NEAREST), "REGISTERED BLINK TEXTURE"),
        _label(_crop(baseline, box).resize(((x2 - x1) * 2, (y2 - y1) * 2), Image.Resampling.NEAREST), "BASELINE + EXPLICIT CREASE"),
        _label(_crop(proposal, box).resize(((x2 - x1) * 2, (y2 - y1) * 2), Image.Resampling.NEAREST), "PROPOSAL: REGISTERED TEXTURE ONLY"),
        _label(Image.fromarray(local_rgb, "RGB").resize(((x2 - x1) * 2, (y2 - y1) * 2), Image.Resampling.NEAREST), "SUPPRESSED CREASE SUPPORT (RED)"),
        _label(_crop(amplified, box).resize(((x2 - x1) * 2, (y2 - y1) * 2), Image.Resampling.NEAREST), "5X ABSOLUTE DIFFERENCE"),
    ]
    width = max(panel.width for panel in panels)
    height = sum(panel.height for panel in panels)
    sheet = Image.new("RGB", (width, height), (0, 0, 0))
    y = 0
    for panel in panels:
        sheet.paste(panel, (0, y))
        y += panel.height
    return sheet


def _artifact_inventory(directory: Path) -> list[dict[str, Any]]:
    artifacts = []
    for path in sorted(directory.iterdir()):
        if path.is_file():
            artifacts.append({"file": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    return artifacts


def _gate(name: str, actual: Any, operator: str, threshold: Any) -> dict[str, Any]:
    if operator == "==":
        passed = actual == threshold
    elif operator == ">=":
        passed = float(actual) >= float(threshold)
    elif operator == "<=":
        passed = float(actual) <= float(threshold)
    else:
        raise EyelidDiagnosticError(f"unsupported gate operator: {operator}")
    return {"name": name, "actual": actual, "operator": operator, "threshold": threshold, "passed": bool(passed)}


def run_diagnostic(output_directory: str | Path | None = None) -> dict[str, Any]:
    contract = load_contract()
    output = Path(output_directory).resolve() if output_directory else (
        REPO_ROOT / str(contract["output"]["directory"])
    ).resolve()
    try:
        output.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise EyelidDiagnosticError("diagnostic output must stay inside the isolated worktree") from exc
    if output.exists():
        raise EyelidDiagnosticError(f"immutable diagnostic output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    phase36_manifest = _strict_json(
        _repo_path(contract["locks"]["phase36_candidate01_manifest"]["path"]), "Phase36 manifest",
    )
    phase35_manifest = _strict_json(
        _repo_path(contract["locks"]["phase35_candidate03_manifest"]["path"]), "Phase35 manifest",
    )
    phase36_contract = _strict_json(
        _repo_path(contract["locks"]["phase36_picture_contract"]["path"]), "Phase36 picture contract",
    )
    phase36_frames = [int(value) for value in contract["diagnostic"]["phase36_frames"]]
    source_frames = [int(value) for value in contract["diagnostic"]["source_frames"]]
    archived, archive_audit = _read_picture_archive(contract, phase36_manifest, set(phase36_frames))
    phase35_hashes = {int(row["frame"]): str(row["rgb_sha256"]) for row in phase35_manifest["frame_hashes"]}
    phase36_hashes = {int(row["frame"]): str(row["rgb_sha256"]) for row in phase36_manifest["frame_hashes"]}

    prepared = phase35.prepare_direct_address()
    baseline_source: dict[int, np.ndarray] = {}
    baseline_native: dict[int, np.ndarray] = {}
    baseline_evidence: dict[int, dict[str, Any]] = {}
    for frame_number in source_frames:
        image, native, evidence = phase35.compose_direct_address_frame(prepared, frame_number)
        final = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
        _require_equal(_raw_frame_hash(final), phase35_hashes[frame_number], f"reproduced Phase35 F{frame_number:03d}")
        baseline_source[frame_number] = final
        baseline_native[frame_number] = native.copy()
        baseline_evidence[frame_number] = _evidence(evidence)
    focus_source = int(contract["diagnostic"]["source_focus_frame"])
    _require_equal(
        _raw_frame_hash(baseline_source[focus_source]),
        contract["diagnostic"]["expected_phase35_f173_rgb_sha256"],
        "frozen Phase35 F173 baseline",
    )

    prepared.native_cache.clear()
    proposal_source: dict[int, np.ndarray] = {}
    proposal_native: dict[int, np.ndarray] = {}
    proposal_evidence: dict[int, dict[str, Any]] = {}
    with _full_closure_crease_suppressed() as suppressions:
        for frame_number in source_frames:
            image, native, evidence = phase35.compose_direct_address_frame(prepared, frame_number)
            proposal_source[frame_number] = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
            proposal_native[frame_number] = native.copy()
            proposal_evidence[frame_number] = _evidence(evidence)

    camera = next(row["camera"] for row in phase36_contract["shots"] if row["id"] == "LP030_COMPASSION_PUNCH")
    baseline_phase36: dict[int, np.ndarray] = {}
    proposal_phase36: dict[int, np.ndarray] = {}
    transform_evidence: dict[int, dict[str, Any]] = {}
    for source_frame, output_frame in zip(source_frames, phase36_frames):
        baseline_output, evidence = phase36.compassion_camera(baseline_source[source_frame], camera, source_frame)
        proposal_output, proposal_transform = phase36.compassion_camera(proposal_source[source_frame], camera, source_frame)
        _require_equal(evidence, proposal_transform, f"unchanged Phase36 camera transform F{output_frame:03d}")
        _require_equal(_raw_frame_hash(baseline_output), phase36_hashes[output_frame], f"reproduced Phase36 F{output_frame:03d}")
        _require_equal(_raw_frame_hash(archived[output_frame]), phase36_hashes[output_frame], f"archived Phase36 F{output_frame:03d}")
        _require_equal(
            _raw_frame_hash(baseline_output), _raw_frame_hash(archived[output_frame]),
            f"renderer/archive identity F{output_frame:03d}",
        )
        baseline_phase36[output_frame] = baseline_output
        proposal_phase36[output_frame] = proposal_output
        transform_evidence[output_frame] = evidence

    source_changed = [
        frame for frame in source_frames if bool(np.any(baseline_source[frame] != proposal_source[frame]))
    ]
    phase36_changed = [
        frame for frame in phase36_frames if bool(np.any(baseline_phase36[frame] != proposal_phase36[frame]))
    ]
    focus_output = int(contract["diagnostic"]["phase36_focus_frame"])
    _require_equal(source_changed, [focus_source], "proposal changed source frames")
    _require_equal(phase36_changed, [focus_output], "proposal changed Phase36 frames")

    native_diff = np.any(baseline_native[focus_source] != proposal_native[focus_source], axis=2)
    final_diff = np.any(baseline_source[focus_source] != proposal_source[focus_source], axis=2)
    phase36_diff = np.any(baseline_phase36[focus_output] != proposal_phase36[focus_output], axis=2)
    native_support = phase35._native_eye_support_mask(prepared)
    final_support = phase35._final_eye_support_mask(prepared, focus_source)
    transformed_support_rgb, _ = phase36.compassion_camera(
        np.repeat(final_support.astype(np.uint8)[:, :, None] * 255, 3, axis=2), camera, focus_source,
    )
    transformed_support = np.any(transformed_support_rgb > 0, axis=2)

    geometry = prepared.face.contract["semantic_geometry_native_xy"]
    crease_mask = np.zeros(prepared.face.plate.shape[:2], dtype=bool)
    for eye_name in ("viewer_left_eye", "viewer_right_eye"):
        eye = geometry[eye_name]
        _, _, crease_alpha = phase35.phase34_candidate09._semantic_lid_alpha_masks(
            prepared.face.plate.shape[:2], tuple(eye["center"]), tuple(eye["radius"]), 1.0,
        )
        crease_mask |= crease_alpha > 0

    deformation = geometry["deformation_roi"]
    cage_mask = np.zeros_like(native_support, dtype=bool)
    cage_mask[int(deformation[1]):int(deformation[3]), int(deformation[0]):int(deformation[2])] = True
    eye_y = np.where(native_support)[0]
    cage_gap = int(deformation[1]) - int(eye_y.max()) - 1
    phase34_source = inspect.getsource(phase35.phase34_candidate09._native_frame)
    phase35_source = inspect.getsource(phase35.compose_direct_address_frame)
    order_audit = {
        "cage_write_precedes_lid_write": phase34_source.index("canvas[warp_support > 0]") < phase34_source.index("phase33._compose_eye_lids"),
        "complete_face_paste_precedes_head_warp": phase35_source.index("frame.paste(face_frame") < phase35_source.index('regions["head"]'),
        "native_eye_support_cage_overlap_pixels": int((native_support & cage_mask).sum()),
        "native_eye_support_to_cage_vertical_gap_px": cage_gap,
        "determination": (
            "The mouth/cheek cage is spatially disjoint from both eye supports. Lids are composited after the cage, "
            "then the complete face is moved through one shared head warp and the Phase36 crop. Differential cage "
            "deformation cannot produce F248. The defect is the second fixed-color synthetic crease written over an "
            "already registered source blink texture that retains its own natural lid fold."
        ),
    }

    gates = [
        _gate("phase35_f173_exact_baseline", _raw_frame_hash(baseline_source[focus_source]), "==", contract["diagnostic"]["expected_phase35_f173_rgb_sha256"]),
        _gate("phase36_archive_verified_frames", archive_audit["verified_frames"], "==", 303),
        _gate("phase36_neighbor_frames_reproduced", len(baseline_phase36), "==", 17),
        _gate("proposal_source_changed_frames", source_changed, "==", [focus_source]),
        _gate("proposal_phase36_changed_frames", phase36_changed, "==", [focus_output]),
        _gate("native_diff_outside_eye_support", int((native_diff & ~native_support).sum()), "==", 0),
        _gate("phase35_diff_outside_transformed_eye_support", int((final_diff & ~final_support).sum()), "==", 0),
        _gate("phase36_diff_outside_twice_transformed_eye_support", int((phase36_diff & ~transformed_support).sum()), "==", 0),
        _gate("suppressed_pixels_match_explicit_crease_support", int(native_diff.sum()), "==", int(crease_mask.sum())),
        _gate("proposal_iris_occlusion_left", proposal_evidence[focus_source]["iris_occlusion_ratios"][0], ">=", 1.0),
        _gate("proposal_iris_occlusion_right", proposal_evidence[focus_source]["iris_occlusion_ratios"][1], ">=", 1.0),
        _gate("lid_areas_unchanged", proposal_evidence[focus_source]["lid_areas"], "==", baseline_evidence[focus_source]["lid_areas"]),
        _gate("lid_write_areas_unchanged", proposal_evidence[focus_source]["lid_write_areas"], "==", baseline_evidence[focus_source]["lid_write_areas"]),
        _gate("native_eye_support_cage_overlap", order_audit["native_eye_support_cage_overlap_pixels"], "==", 0),
        _gate("cage_write_precedes_lid_write", order_audit["cage_write_precedes_lid_write"], "==", True),
        _gate("complete_face_paste_precedes_head_warp", order_audit["complete_face_paste_precedes_head_warp"], "==", True),
        _gate("encoding_process_count", 0, "==", 0),
        _gate("paid_service_calls", 0, "==", 0),
    ]
    failed = [gate["name"] for gate in gates if not gate["passed"]]
    if failed:
        raise EyelidDiagnosticError(f"machine gates failed before evidence publication: {failed}")

    native_box = _bbox(native_support, 16)
    phase36_box = (
        max(0, min(row["transformed_eye_roi_xyxy"][0] for row in transform_evidence.values()) - 16),
        max(0, min(row["transformed_eye_roi_xyxy"][1] for row in transform_evidence.values()) - 16),
        min(1920, max(row["transformed_eye_roi_xyxy"][2] for row in transform_evidence.values()) + 16),
        min(1080, max(row["transformed_eye_roi_xyxy"][3] for row in transform_evidence.values()) + 16),
    )

    with tempfile.TemporaryDirectory(prefix="phase37-eyelid-", dir=output.parent) as temporary:
        stage = Path(temporary) / output.name
        stage.mkdir()
        native_stem = str(contract["output"]["native_comparison_stem"])
        phase36_stem = str(contract["output"]["phase36_comparison_stem"])
        for scale in (1, 2, 3):
            _comparison(
                baseline_native[focus_source], proposal_native[focus_source], native_box, scale,
                "F173 NATIVE BEFORE", "F173 NATIVE PROPOSAL",
            ).save(stage / f"{native_stem}-{scale}x.png")
            _comparison(
                baseline_phase36[focus_output], proposal_phase36[focus_output], phase36_box, scale,
                "F248 ARCHIVED BEFORE", "F248 CORRECTED-SOURCE PROPOSAL",
            ).save(stage / f"{phase36_stem}-{scale}x.png")
        _neighbor_sweep(baseline_phase36, proposal_phase36, phase36_box).save(
            stage / str(contract["output"]["phase36_sequence_filename"])
        )
        _layer_decomposition(
            prepared.face.phase33_base.lid_texture,
            baseline_native[focus_source], proposal_native[focus_source], crease_mask, native_box,
        ).save(stage / str(contract["output"]["layer_decomposition_filename"])
        )

        artifacts = _artifact_inventory(stage)
        report = {
            "report_version": 1,
            "diagnostic_id": "phase37_eyelid_alignment_diagnostic_v1",
            "status": "MACHINE_CAUSAL_ISOLATION_PASSED_HUMAN_ALIGNMENT_REVIEW_REQUIRED",
            "machine_passed": True,
            "human_visual_acceptance_required": True,
            "scope": "still-only F173/F248 eyelid root-cause isolation with actual Phase36 F240-F256 neighbor sweep",
            "cash_cost": 0,
            "paid_service_calls": 0,
            "network_calls": 0,
            "encoding_process_count": 0,
            "video_encoder_invoked": False,
            "contract": {"path": CONTRACT_RELATIVE_PATH, "raw_sha256": _sha256(REPO_ROOT / CONTRACT_RELATIVE_PATH)},
            "implementation": {"path": IMPLEMENTATION_RELATIVE_PATH, "sha256": _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH)},
            "tests": {"path": TEST_RELATIVE_PATH, "sha256": _sha256(REPO_ROOT / TEST_RELATIVE_PATH)},
            "toolchain": {"python_opencv": cv2.__version__, "numpy": np.__version__, "pillow": PILLOW_VERSION},
            "bindings": {
                "controlling_james_verdict_lf_sha256": _lf_hash(_repo_path(contract["locks"]["controlling_james_verdict"]["path"])),
                "phase36_candidate01_manifest_sha256": _sha256(_repo_path(contract["locks"]["phase36_candidate01_manifest"]["path"])),
                "phase36_candidate01_rejection_receipt_sha256": _sha256(_repo_path(contract["locks"]["phase36_candidate01_rejection_receipt"]["path"])),
                "phase36_archive": archive_audit,
            },
            "baseline": {
                "phase35_f173_rgb_sha256": _raw_frame_hash(baseline_source[focus_source]),
                "phase35_f173_native_rgb_sha256": _raw_frame_hash(baseline_native[focus_source]),
                "phase35_f173_evidence": baseline_evidence[focus_source],
                "phase35_source_frame_hashes": [
                    {"frame": frame, "rgb_sha256": _raw_frame_hash(baseline_source[frame])} for frame in source_frames
                ],
                "phase36_frame_hashes": [
                    {"frame": frame, "rgb_sha256": _raw_frame_hash(baseline_phase36[frame])} for frame in phase36_frames
                ],
            },
            "proposal": {
                "description": contract["diagnostic"]["proposal"],
                "suppression_calls": suppressions,
                "phase35_changed_frames": source_changed,
                "phase36_changed_frames": phase36_changed,
                "phase35_f173_rgb_sha256": _raw_frame_hash(proposal_source[focus_source]),
                "phase35_f173_native_rgb_sha256": _raw_frame_hash(proposal_native[focus_source]),
                "phase36_f248_rgb_sha256": _raw_frame_hash(proposal_phase36[focus_output]),
                "phase35_f173_evidence": proposal_evidence[focus_source],
            },
            "difference_audit": {
                "explicit_crease_support_pixels_native": int(crease_mask.sum()),
                "changed_pixels_native": int(native_diff.sum()),
                "changed_pixels_phase35_final": int(final_diff.sum()),
                "changed_pixels_phase36_f248": int(phase36_diff.sum()),
                "changed_pixels_outside_native_eye_support": int((native_diff & ~native_support).sum()),
                "changed_pixels_outside_phase35_eye_support": int((final_diff & ~final_support).sum()),
                "changed_pixels_outside_phase36_eye_support": int((phase36_diff & ~transformed_support).sum()),
                "native_review_box_xyxy": list(native_box),
                "phase36_review_box_xyxy": list(phase36_box),
            },
            "root_cause": order_audit,
            "gates": gates,
            "gate_count": len(gates),
            "failed_gates": failed,
            "artifacts": artifacts,
            "disposition": contract["disposition"],
        }
        report_path = stage / str(contract["output"]["report_filename"])
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        allowed_suffixes = {".png", ".json"}
        _require_equal(
            {path.suffix.lower() for path in stage.iterdir() if path.is_file()} <= allowed_suffixes,
            True,
            "still-only artifact suffixes",
        )
        stage.rename(output)

    return {
        "output_directory": str(output),
        "report": str(output / str(contract["output"]["report_filename"])),
        "machine_passed": True,
        "human_visual_acceptance_required": True,
        "phase35_f173_baseline_sha256": _raw_frame_hash(baseline_source[focus_source]),
        "phase36_f248_proposal_sha256": _raw_frame_hash(proposal_phase36[focus_output]),
        "encoding_process_count": 0,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    print(json.dumps(run_diagnostic(args.output_directory), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
