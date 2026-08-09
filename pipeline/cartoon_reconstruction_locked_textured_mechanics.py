"""Phase 32 reconstruction-locked textured mechanics proof for June Oxley.

This module transports only the nine patch-local RGBA arrays accepted by Phase
30 through the exact Phase 31 motion.  Character regions are warped in linear
premultiplied RGB, resolved to one visible owner, passed through the one locked
Phase 27 registration, and composited over the clean GS030 porch.  No source
plate, generated texture, inferred hidden surface, or second texture source may
enter the character after patch extraction.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline.cartoon_connected_region_mechanics import (
    PREVIEW_SIZE,
    REGION_IDS,
    ConnectedRegionMechanicsError,
    FlatMechanicsFrame,
    _components,
    _register_region_masks,
    _tps_displacement,
    _tps_parameters,
    _transform_point,
    load_connected_region_mechanics_contract,
    render_flat_mechanics_frame,
)
from pipeline.cartoon_pose_layers import registered_pose_layer
from pipeline.cartoon_reconstruction_locked_patch import (
    LockedPatch,
    evaluate_reconstruction_lock,
    extract_locked_patches,
    load_reconstruction_contract,
    recompose_locked_patches,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = Path(
    "concept/characters/june_oxley_reconstruction_locked_textured_mechanics_v1.json"
)
IMPLEMENTATION_RELATIVE_PATH = Path(
    "pipeline/cartoon_reconstruction_locked_textured_mechanics.py"
)
_PINNED_CONTRACT_CANONICAL_SHA256 = "08c455de7b6f3511d15b19886606cc22d977b2397aaa81bf7d32fa41fc635535"
SOURCE_SIZE = (1672, 941)
OUTPUT_SIZE = (1920, 1080)
ALPHA_THRESHOLD = 16


def _occupied_alpha(alpha: np.ndarray) -> np.ndarray:
    """Return the one contract-wide definition of visible character occupancy."""
    values = np.asarray(alpha)
    if np.issubdtype(values.dtype, np.floating):
        values = np.rint(np.clip(values, 0.0, 1.0) * 255.0).astype(np.uint8)
    return values > ALPHA_THRESHOLD


class ReconstructionLockedTexturedMechanicsError(ValueError):
    """Raised when Phase 32 cannot prove a required invariant."""


@dataclass
class TexturedMechanicsFrame:
    frame: int
    raw_character_rgba: np.ndarray
    registered_character_rgba: np.ndarray
    beauty_rgb: np.ndarray
    owner_index: np.ndarray
    registered_owner_masks: dict[str, np.ndarray]
    source_coordinate_xy: np.ndarray
    phase31_frame: FlatMechanicsFrame
    geometry_metrics: dict[str, Any]
    texture_metrics: dict[str, Any]
    seam_metrics: dict[str, Any]
    deformation_metrics: dict[str, Any]
    material_points_preview: dict[str, np.ndarray]

    def close(self) -> None:
        self.registered_owner_masks.clear()
        self.material_points_preview.clear()
        self.phase31_frame.close()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _source_commit() -> str | None:
    """Return the repository commit when available; hashes remain authoritative."""
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and len(value) == 40 else None


def _phase32_provenance(contract: dict[str, Any]) -> dict[str, Any]:
    contract_path = (REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve()
    implementation_path = (REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH).resolve()
    return {
        "contract_path": str(CONTRACT_RELATIVE_PATH).replace("\\", "/"),
        "contract_raw_sha256": _sha256(contract_path),
        "contract_canonical_sha256": _canonical_hash(contract),
        "implementation_path": str(IMPLEMENTATION_RELATIVE_PATH).replace("\\", "/"),
        "implementation_sha256": _sha256(implementation_path),
        "source_commit": _source_commit(),
    }


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ReconstructionLockedTexturedMechanicsError(
            f"{label} mismatch: {actual!r} != {expected!r}"
        )


def _locked_path(reference: dict[str, Any], label: str) -> Path:
    path = (REPO_ROOT / str(reference.get("path", ""))).resolve()
    if not path.is_file():
        raise ReconstructionLockedTexturedMechanicsError(f"{label} is missing: {path}")
    actual = _sha256(path)
    expected = str(reference.get("sha256", ""))
    if not expected or actual != expected:
        raise ReconstructionLockedTexturedMechanicsError(
            f"{label} SHA-256 mismatch: {actual} != {expected}"
        )
    return path


def _validate_contract(contract: dict[str, Any]) -> None:
    _require_equal(_canonical_hash(contract), _PINNED_CONTRACT_CANONICAL_SHA256, "complete Phase32 contract")
    _require_equal(contract.get("contract_version"), 1, "contract version")
    _require_equal(
        contract.get("contract_id"),
        "june_oxley_reconstruction_locked_textured_mechanics_v1",
        "contract id",
    )
    _require_equal(contract.get("phase"), "phase32_reconstruction_locked_textured_mechanics", "phase")
    _require_equal(contract.get("cash_cost"), 0, "cash cost")
    _require_equal(contract.get("paid_runtime_dependency"), False, "paid dependency")
    _require_equal(contract.get("network_runtime_required"), False, "network dependency")
    _require_equal(contract.get("delivery_attempt_version"), 3, "delivery attempt version")
    _require_equal(contract.get("audit_revision"), 2, "audit revision")
    timing = contract["timing"]
    _require_equal(
        (timing["frame_start"], timing["frame_end"], timing["frame_count"], timing["fps"]),
        (1, 49, 49, 30),
        "timing",
    )
    keys = [1, 7, 13, 19, 25, 31, 37, 43, 49]
    _require_equal(timing["key_frames"], keys, "timing keys")
    _require_equal(contract["delivery"]["review_frames"], keys, "delivery review keys")
    texture = contract["texture_policy"]
    _require_equal(texture["character_texture_source_count"], 1, "texture source count")
    _require_equal(texture["direct_source_plate_read_after_patch_extraction_allowed"], False, "source plate reads")
    _require_equal(texture["new_character_texture_allowed"], False, "new texture")
    _require_equal(texture["ai_generated_character_pixels_allowed"], False, "AI character pixels")
    _require_equal(texture["inpainted_character_pixels_allowed"], False, "inpainted pixels")
    _require_equal(
        texture["face_identity_source_roi_xyxy"],
        [595, 25, 725, 190],
        "face identity source ROI",
    )
    _require_equal(texture["face_identity_ssim_erosion_px"], 5, "face SSIM erosion")
    _require_equal(
        texture["registration_ringing_speckle_removal_allowed"],
        True,
        "registration ringing cleanup",
    )
    _require_equal(
        texture["maximum_registration_ringing_speckle_area_px"],
        1,
        "registration ringing speckle area",
    )
    ownership = contract["ownership_policy"]
    _require_equal(
        ownership["visible_alpha_threshold_exclusive_uint8"],
        ALPHA_THRESHOLD,
        "visible alpha threshold",
    )
    phase30 = json.loads(
        _locked_path(contract["locks"]["phase30_contract"], "Phase30 contract").read_text(encoding="utf-8")
    )
    _require_equal(ownership["priority"], phase30["rest_reconstruction"]["rest_owner_priority"], "owner priority")
    _require_equal(set(ownership["priority"]), set(REGION_IDS), "owner inventory")
    _require_equal(
        ownership["required_adjacent_pairs"],
        phase30["patch_extraction"]["overlap"]["required_adjacent_pairs"],
        "required seam pairs",
    )
    _require_equal(ownership["alpha_over_between_character_regions_allowed"], False, "character alpha-over")
    _require_equal(ownership["candidate_summing_allowed"], False, "candidate summing")
    delivery = contract["delivery"]
    _require_equal(
        (delivery["width"], delivery["height"], delivery["fps"], delivery["frame_count"]),
        (1920, 1080, 30, 49),
        "delivery geometry",
    )
    _require_equal(delivery["one_encode_without_retry"], True, "single encode")
    _require_equal(delivery["staged_atomic_directory_publication"], True, "atomic publication")
    _require_equal(
        delivery["output_directory"],
        "../../outputs/edit/phase32-reconstruction-locked-textured-mechanics-v3",
        "versioned delivery directory",
    )
    _require_equal(
        delivery["encoding"],
        {
            "implementation": "libx264",
            "preset": "slow",
            "tune": "animation",
            "crf": 0,
            "lossless_yuv": True,
            "gop": 1,
            "b_frames": 0,
            "video_track_timescale": 90000,
        },
        "lossless-yuv delivery encoding",
    )
    failure = contract["failure_policy"]
    _require_equal(failure["mode"], "fail_closed", "failure mode")
    _require_equal(failure["partial_success_allowed"], False, "partial success")
    _require_equal(failure["fallback_allowed"], False, "fallback")
    _require_equal(failure["automatic_reencode_allowed"], False, "automatic reencode")


def load_reconstruction_locked_textured_contract(path: str | Path) -> dict[str, Any]:
    contract_path = Path(path).resolve()
    if not contract_path.is_file():
        raise ReconstructionLockedTexturedMechanicsError(
            f"Phase32 contract is missing: {contract_path}"
        )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    _validate_contract(contract)
    locks = contract["locks"]
    for identifier, label in (
        ("phase30_contract", "Phase30 contract"),
        ("phase30_implementation", "Phase30 implementation"),
        ("phase31_contract", "Phase31 contract"),
        ("phase31_implementation", "Phase31 implementation"),
        ("phase31_acceptance_receipt", "Phase31 acceptance receipt"),
        ("phase32_rejected_delivery_receipt", "Phase32 rejected-delivery receipt"),
        ("phase32_superseded_delivery_receipt", "Phase32 superseded-delivery receipt"),
        ("accepted_character_source", "accepted character source"),
        ("clean_environment", "clean environment"),
    ):
        _locked_path(locks[identifier], label)
    receipt = json.loads(
        _locked_path(locks["phase31_acceptance_receipt"], "Phase31 acceptance receipt").read_text(
            encoding="utf-8"
        )
    )
    rejected_receipt = json.loads(
        _locked_path(
            locks["phase32_rejected_delivery_receipt"],
            "Phase32 rejected-delivery receipt",
        ).read_text(encoding="utf-8")
    )
    _require_equal(
        rejected_receipt["status"],
        locks["phase32_rejected_delivery_receipt"]["required_status"],
        "Phase32 rejected delivery status",
    )
    _require_equal(
        rejected_receipt["encoding"]["encoding_process_count"],
        locks["phase32_rejected_delivery_receipt"]["required_encoding_process_count"],
        "Phase32 rejected delivery encoding count",
    )
    _require_equal(
        rejected_receipt["report"]["failed_gate_count"],
        locks["phase32_rejected_delivery_receipt"]["required_failed_gate_count"],
        "Phase32 rejected delivery failed gate count",
    )
    _require_equal(receipt["report"]["machine_passed"], True, "Phase31 receipt machine pass")
    _require_equal(
        receipt["report"]["passed_gate_count"],
        locks["phase31_acceptance_receipt"]["required_gate_count"],
        "Phase31 receipt gate count",
    )
    _require_equal(receipt["report"]["failed_gate_count"], 0, "Phase31 failed gate count")
    superseded_receipt = json.loads(
        _locked_path(
            locks["phase32_superseded_delivery_receipt"],
            "Phase32 superseded-delivery receipt",
        ).read_text(encoding="utf-8")
    )
    superseded_lock = locks["phase32_superseded_delivery_receipt"]
    _require_equal(
        superseded_receipt["status"],
        superseded_lock["required_status"],
        "Phase32 superseded delivery status",
    )
    _require_equal(
        superseded_receipt["report"]["machine_passed"],
        superseded_lock["required_machine_passed"],
        "Phase32 superseded delivery machine pass",
    )
    _require_equal(
        superseded_receipt["report"]["passed_gate_count"],
        superseded_lock["required_gate_count"],
        "Phase32 superseded delivery gate count",
    )
    _require_equal(
        superseded_receipt["video"]["encoding_process_count"],
        superseded_lock["required_encoding_process_count"],
        "Phase32 superseded delivery encoding count",
    )
    return contract


def _verify_external_evidence(contract: dict[str, Any]) -> None:
    """Verify non-repository media only at the production preflight boundary."""
    locks = contract["locks"]
    phase31_receipt = json.loads(
        _locked_path(
            locks["phase31_acceptance_receipt"], "Phase31 acceptance receipt"
        ).read_text(encoding="utf-8")
    )
    phase31_report_path = _locked_path(
        phase31_receipt["report"], "accepted Phase31 report"
    )
    _locked_path(phase31_receipt["video"], "accepted Phase31 video")
    _locked_path(
        phase31_receipt["decoded_contact_sheet"],
        "accepted Phase31 contact sheet",
    )
    phase31_report = json.loads(phase31_report_path.read_text(encoding="utf-8"))
    _require_equal(
        phase31_report.get("machine_passed"),
        True,
        "accepted Phase31 report machine pass",
    )
    _require_equal(
        len(phase31_report.get("gate_results", [])),
        locks["phase31_acceptance_receipt"]["required_gate_count"],
        "accepted Phase31 report gate count",
    )
    if not all(bool(row.get("passed")) for row in phase31_report["gate_results"]):
        raise ReconstructionLockedTexturedMechanicsError(
            "accepted Phase31 report contains a failed gate"
        )
    rejected_receipt = json.loads(
        _locked_path(
            locks["phase32_rejected_delivery_receipt"],
            "Phase32 rejected-delivery receipt",
        ).read_text(encoding="utf-8")
    )
    _locked_path(rejected_receipt["report"], "rejected Phase32 report")
    _locked_path(rejected_receipt["video"], "rejected Phase32 video")
    for artifact_name, artifact in rejected_receipt["review_artifacts"].items():
        _locked_path(artifact, f"rejected Phase32 {artifact_name}")
    superseded_receipt = json.loads(
        _locked_path(
            locks["phase32_superseded_delivery_receipt"],
            "Phase32 superseded-delivery receipt",
        ).read_text(encoding="utf-8")
    )
    superseded_report_path = _locked_path(
        superseded_receipt["report"], "superseded Phase32 report"
    )
    _locked_path(superseded_receipt["video"], "superseded Phase32 video")
    for artifact_name, artifact in superseded_receipt["review_artifacts"].items():
        _locked_path(artifact, f"superseded Phase32 {artifact_name}")
    superseded_report = json.loads(
        superseded_report_path.read_text(encoding="utf-8")
    )
    _require_equal(
        superseded_report.get("machine_passed"),
        True,
        "superseded Phase32 report machine pass",
    )
    _require_equal(
        len(superseded_report.get("gate_results", [])),
        locks["phase32_superseded_delivery_receipt"]["required_gate_count"],
        "superseded Phase32 report gate count",
    )


def _srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb, dtype=np.float32)
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(rgb: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb, dtype=np.float32)
    return np.where(
        rgb <= 0.0031308,
        rgb * 12.92,
        1.055 * np.maximum(rgb, 0.0) ** (1.0 / 2.4) - 0.055,
    )


def _rgba_to_linear_premultiplied(rgba: np.ndarray) -> np.ndarray:
    values = np.asarray(rgba, dtype=np.float32) / 255.0
    alpha = values[:, :, 3:4]
    linear = _srgb_to_linear(values[:, :, :3])
    return np.concatenate((linear * alpha, alpha), axis=2).astype(np.float32)


def _linear_premultiplied_to_rgba(premultiplied: np.ndarray) -> np.ndarray:
    values = np.asarray(premultiplied, dtype=np.float32)
    if not np.all(np.isfinite(values)):
        raise ReconstructionLockedTexturedMechanicsError("non-finite premultiplied character values")
    alpha = np.clip(values[:, :, 3:4], 0.0, 1.0)
    rgb_premultiplied = np.clip(values[:, :, :3], 0.0, alpha)
    linear = np.zeros_like(rgb_premultiplied)
    np.divide(
        rgb_premultiplied,
        np.maximum(alpha, 1e-8),
        out=linear,
        where=alpha > 1e-8,
    )
    srgb = np.clip(_linear_to_srgb(np.clip(linear, 0.0, 1.0)), 0.0, 1.0)
    srgb[alpha[:, :, 0] <= 1e-8] = 0.0
    return np.round(np.concatenate((srgb, alpha), axis=2) * 255.0).astype(np.uint8)


def _patch_local_premultiplied(patch: LockedPatch) -> np.ndarray:
    return _rgba_to_linear_premultiplied(patch.rgba)


def _local_affine_matrix(patch: LockedPatch, matrix: np.ndarray) -> np.ndarray:
    x0, y0, _, _ = patch.bbox_xyxy
    local = np.asarray(matrix[:2], dtype=np.float64).copy()
    local[:, 2] += matrix[:2, :2] @ np.asarray((x0, y0), dtype=np.float64)
    return local


def _warp_affine_premultiplied(
    patch: LockedPatch,
    matrix: np.ndarray,
    canvas_shape: tuple[int, int],
) -> np.ndarray:
    height, width = canvas_shape
    local = _patch_local_premultiplied(patch)
    warped = cv2.warpAffine(
        local,
        _local_affine_matrix(patch, matrix).astype(np.float32),
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )
    alpha = np.clip(warped[:, :, 3:4], 0.0, 1.0)
    warped[:, :, :3] = np.clip(warped[:, :, :3], 0.0, alpha)
    warped[:, :, 3:4] = alpha
    return warped.astype(np.float32)


def _lower_inverse_map(
    support: np.ndarray,
    source_controls: np.ndarray,
    destination_controls: np.ndarray,
) -> tuple[tuple[int, int, int, int], np.ndarray, np.ndarray, np.ndarray]:
    height, width = support.shape
    ys, xs = np.where(support)
    if not len(xs):
        raise ReconstructionLockedTexturedMechanicsError("lower-garment support is empty")
    margin = 4
    if np.array_equal(source_controls, destination_controls):
        destination_support = np.column_stack((xs, ys)).astype(np.float64)
    else:
        points = np.column_stack((xs, ys)).astype(np.float64)
        forward_parameters = _tps_parameters(
            source_controls, destination_controls - source_controls
        )
        destination_support = points + _tps_displacement(
            points, source_controls, forward_parameters
        )
    x0 = max(0, int(math.floor(float(np.min(destination_support[:, 0])))) - margin)
    x1 = min(width, int(math.ceil(float(np.max(destination_support[:, 0])))) + 1 + margin)
    y0 = max(0, int(math.floor(float(np.min(destination_support[:, 1])))) - margin)
    y1 = min(height, int(math.ceil(float(np.max(destination_support[:, 1])))) + 1 + margin)
    grid_y, grid_x = np.indices((y1 - y0, x1 - x0), dtype=np.float64)
    destination = np.column_stack(((grid_x + x0).ravel(), (grid_y + y0).ravel()))
    if np.array_equal(source_controls, destination_controls):
        source = destination
    else:
        parameters = _tps_parameters(
            source_controls, destination_controls - source_controls
        )
        source = destination.copy()
        for _ in range(7):
            source = destination - _tps_displacement(source, source_controls, parameters)
    map_x = source[:, 0].reshape(grid_x.shape).astype(np.float32)
    map_y = source[:, 1].reshape(grid_y.shape).astype(np.float32)
    return (x0, y0, x1, y1), map_x, map_y, source


def _warp_lower_premultiplied(
    patch: LockedPatch,
    source_controls: np.ndarray,
    destination_controls: np.ndarray,
    canvas_shape: tuple[int, int],
) -> tuple[np.ndarray, tuple[int, int, int, int], np.ndarray, np.ndarray]:
    height, width = canvas_shape
    full = np.zeros((height, width, 4), dtype=np.float32)
    x0, y0, x1, y1 = patch.bbox_xyxy
    full[y0:y1, x0:x1] = _patch_local_premultiplied(patch)
    roi, map_x, map_y, _ = _lower_inverse_map(
        patch.semantic_support_mask, source_controls, destination_controls
    )
    rx0, ry0, rx1, ry1 = roi
    sampled = cv2.remap(
        full,
        map_x,
        map_y,
        interpolation=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )
    alpha = np.clip(sampled[:, :, 3:4], 0.0, 1.0)
    sampled[:, :, :3] = np.clip(sampled[:, :, :3], 0.0, alpha)
    sampled[:, :, 3:4] = alpha
    output = np.zeros_like(full)
    output[ry0:ry1, rx0:rx1] = sampled
    return output, roi, map_x, map_y


def _warp_binary_affine(mask: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    height, width = mask.shape
    return cv2.warpAffine(
        mask.astype(np.uint8),
        matrix[:2].astype(np.float32),
        (width, height),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    ) > 0


def _warp_binary_lower(
    mask: np.ndarray,
    roi_support: np.ndarray,
    source_controls: np.ndarray,
    destination_controls: np.ndarray,
) -> np.ndarray:
    roi, map_x, map_y, _ = _lower_inverse_map(
        roi_support, source_controls, destination_controls
    )
    x0, y0, x1, y1 = roi
    sampled = cv2.remap(
        mask.astype(np.uint8),
        map_x,
        map_y,
        interpolation=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    ) > 0
    result = np.zeros_like(mask)
    result[y0:y1, x0:x1] = sampled
    return result


def _transported_owner_masks(
    patches: dict[str, LockedPatch], phase31: FlatMechanicsFrame
) -> dict[str, np.ndarray]:
    output: dict[str, np.ndarray] = {}
    for identifier in REGION_IDS:
        patch = patches[identifier]
        if identifier == "lower_garment":
            controls = phase31.cage_controls[identifier]
            output[identifier] = _warp_binary_lower(
                patch.rest_owner_mask,
                patch.semantic_support_mask,
                controls["source"],
                controls["destination"],
            )
        else:
            output[identifier] = _warp_binary_affine(
                patch.rest_owner_mask, phase31.region_transforms[identifier]
            )
    return output


def _patch_visible_source_mask(patch: LockedPatch) -> np.ndarray:
    """Expand a patch's alpha>16 pixels into locked global source coordinates."""
    x0, y0, x1, y1 = patch.bbox_xyxy
    mask = np.zeros(patch.semantic_support_mask.shape, dtype=bool)
    mask[y0:y1, x0:x1] = _occupied_alpha(patch.rgba[:, :, 3])
    return mask & patch.semantic_support_mask


def _transported_visible_masks(
    patches: dict[str, LockedPatch], phase31: FlatMechanicsFrame
) -> dict[str, np.ndarray]:
    """Transport exactly the visible (>16 alpha) part of each locked patch."""
    output: dict[str, np.ndarray] = {}
    for identifier in REGION_IDS:
        patch = patches[identifier]
        source_visible = _patch_visible_source_mask(patch)
        if identifier == "lower_garment":
            controls = phase31.cage_controls[identifier]
            output[identifier] = _warp_binary_lower(
                source_visible,
                patch.semantic_support_mask,
                controls["source"],
                controls["destination"],
            )
        else:
            output[identifier] = _warp_binary_affine(
                source_visible, phase31.region_transforms[identifier]
            )
    return output


def _resolve_transported_ownership(
    supports: dict[str, np.ndarray],
    transported_owner_masks: dict[str, np.ndarray],
    priority: list[str],
    *,
    desired_geometry: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    shape = next(iter(supports.values())).shape
    owner = np.full(shape, -1, dtype=np.int16)
    fallback = np.zeros(shape, dtype=bool)
    identifier_index = {identifier: index for index, identifier in enumerate(REGION_IDS)}
    candidate_union = np.logical_or.reduce(list(supports.values()))
    desired = candidate_union if desired_geometry is None else desired_geometry
    for identifier in priority:
        selected = (
            (owner < 0)
            & supports[identifier]
            & transported_owner_masks[identifier]
        )
        owner[selected] = identifier_index[identifier]
    for identifier in priority:
        selected = (owner < 0) & supports[identifier]
        owner[selected] = identifier_index[identifier]
        fallback[selected] = True
    uncovered = desired & (owner < 0)
    occupied = int(np.count_nonzero(desired))
    selected_count = (owner[desired] >= 0).astype(np.uint8)
    metrics = {
        "phase31_geometry_pixels": occupied,
        "phase31_geometry_pixels_uncovered": int(np.count_nonzero(uncovered)),
        "overlap_fallback_pixels": int(np.count_nonzero(fallback)),
        "overlap_fallback_fraction": float(np.count_nonzero(fallback) / max(1, occupied)),
        "selected_owners_per_occupied_pixel_minimum": int(np.min(selected_count)),
        "selected_owners_per_occupied_pixel_maximum": int(np.max(selected_count)),
        "multiply_composited_character_pixels": 0,
    }
    return owner, fallback, metrics


def _source_coordinates_for_selection(
    identifier: str,
    selection: np.ndarray,
    phase31: FlatMechanicsFrame,
) -> np.ndarray:
    ys, xs = np.where(selection)
    destination = np.column_stack((xs, ys)).astype(np.float64)
    if identifier == "lower_garment":
        controls = phase31.cage_controls[identifier]
        if np.array_equal(controls["source"], controls["destination"]):
            return destination
        parameters = _tps_parameters(
            controls["source"], controls["destination"] - controls["source"]
        )
        source = destination.copy()
        for _ in range(7):
            source = destination - _tps_displacement(source, controls["source"], parameters)
        return source
    inverse = np.linalg.inv(phase31.region_transforms[identifier])
    homogeneous = np.column_stack((destination, np.ones(len(destination), dtype=np.float64)))
    return (homogeneous @ inverse.T)[:, :2]


def _nearest_patch_premultiplied(
    patch: LockedPatch, source_coordinates: np.ndarray
) -> np.ndarray:
    x0, y0, x1, y1 = patch.bbox_xyxy
    rounded = np.rint(source_coordinates).astype(np.int64)
    local_x = np.clip(rounded[:, 0] - x0, 0, x1 - x0 - 1)
    local_y = np.clip(rounded[:, 1] - y0, 0, y1 - y0 - 1)
    rgba = patch.rgba[local_y, local_x].reshape(-1, 1, 4)
    return _rgba_to_linear_premultiplied(rgba)[:, 0]


def _nearest_visible_patch_premultiplied(
    patch: LockedPatch,
    source_coordinates: np.ndarray,
    *,
    search_radius: int = 4,
) -> tuple[np.ndarray, np.ndarray]:
    """Select the nearest locked patch pixel whose quantized alpha is visible.

    Binary support warps and cubic RGBA warps can disagree by a fraction of a
    pixel at an edge.  Coverage repair may only choose an existing nearby
    locked patch pixel; it never invents or blends new character texture.
    """
    x0, y0, x1, y1 = patch.bbox_xyxy
    rounded = np.rint(source_coordinates).astype(np.int64)
    local_x = np.clip(rounded[:, 0] - x0, 0, x1 - x0 - 1)
    local_y = np.clip(rounded[:, 1] - y0, 0, y1 - y0 - 1)
    best_x = local_x.copy()
    best_y = local_y.copy()
    best_alpha = patch.rgba[best_y, best_x, 3].copy()
    offsets = sorted(
        (
            (dx * dx + dy * dy, dx, dy)
            for dy in range(-search_radius, search_radius + 1)
            for dx in range(-search_radius, search_radius + 1)
        ),
        key=lambda row: row[0],
    )
    unresolved = ~_occupied_alpha(best_alpha)
    for _, dx, dy in offsets:
        if not np.any(unresolved):
            break
        candidate_x = np.clip(local_x + dx, 0, x1 - x0 - 1)
        candidate_y = np.clip(local_y + dy, 0, y1 - y0 - 1)
        candidate_alpha = patch.rgba[candidate_y, candidate_x, 3]
        replace = unresolved & _occupied_alpha(candidate_alpha)
        best_x[replace] = candidate_x[replace]
        best_y[replace] = candidate_y[replace]
        best_alpha[replace] = candidate_alpha[replace]
        unresolved &= ~replace
    if np.any(unresolved):
        visible_y, visible_x = np.where(_occupied_alpha(patch.rgba[:, :, 3]))
        if not len(visible_x):
            raise ReconstructionLockedTexturedMechanicsError(
                f"locked patch {patch.identifier} contains no visible texture"
            )
        for index in np.where(unresolved)[0]:
            distances = (
                (visible_x.astype(np.int64) - local_x[index]) ** 2
                + (visible_y.astype(np.int64) - local_y[index]) ** 2
            )
            nearest = int(np.argmin(distances))
            best_x[index] = visible_x[nearest]
            best_y[index] = visible_y[nearest]
            best_alpha[index] = patch.rgba[
                visible_y[nearest], visible_x[nearest], 3
            ]
    rgba = patch.rgba[best_y, best_x].reshape(-1, 1, 4)
    actual_coordinates = np.column_stack((best_x + x0, best_y + y0)).astype(
        np.float64
    )
    return _rgba_to_linear_premultiplied(rgba)[:, 0], actual_coordinates


def _candidate_premultiplied(
    identifier: str,
    patch: LockedPatch,
    phase31: FlatMechanicsFrame,
    canvas_shape: tuple[int, int],
) -> np.ndarray:
    if identifier == "lower_garment":
        controls = phase31.cage_controls[identifier]
        return _warp_lower_premultiplied(
            patch,
            controls["source"],
            controls["destination"],
            canvas_shape,
        )[0]
    return _warp_affine_premultiplied(
        patch, phase31.region_transforms[identifier], canvas_shape
    )


def _vector_psnr(first: np.ndarray, second: np.ndarray) -> float:
    if not len(first):
        return 0.0
    mse = float(np.mean((first.astype(np.float64) - second.astype(np.float64)) ** 2))
    return 99.0 if mse <= 1e-12 else float(10.0 * math.log10((255.0 * 255.0) / mse))


def _vector_ssim(first: np.ndarray, second: np.ndarray) -> float:
    if not len(first):
        return 0.0
    x = first.astype(np.float64)
    y = second.astype(np.float64)
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    values = []
    for channel in range(3):
        a = x[:, channel]
        b = y[:, channel]
        mean_a = float(np.mean(a))
        mean_b = float(np.mean(b))
        variance_a = float(np.var(a))
        variance_b = float(np.var(b))
        covariance = float(np.mean((a - mean_a) * (b - mean_b)))
        values.append(
            ((2.0 * mean_a * mean_b + c1) * (2.0 * covariance + c2))
            / ((mean_a * mean_a + mean_b * mean_b + c1) * (variance_a + variance_b + c2))
        )
    return float(np.mean(values))


def _masked_spatial_ssim(
    first_rgb: np.ndarray, second_rgb: np.ndarray, mask: np.ndarray
) -> float:
    """Return an 11x11 Gaussian-window SSIM averaged only inside ``mask``."""
    if not np.any(mask):
        return 0.0
    first = first_rgb.astype(np.float32)
    second = second_rgb.astype(np.float32)
    c1 = float((0.01 * 255.0) ** 2)
    c2 = float((0.03 * 255.0) ** 2)
    values: list[np.ndarray] = []
    for channel in range(3):
        x = first[:, :, channel]
        y = second[:, :, channel]
        mean_x = cv2.GaussianBlur(x, (11, 11), 1.5)
        mean_y = cv2.GaussianBlur(y, (11, 11), 1.5)
        variance_x = cv2.GaussianBlur(x * x, (11, 11), 1.5) - mean_x * mean_x
        variance_y = cv2.GaussianBlur(y * y, (11, 11), 1.5) - mean_y * mean_y
        covariance = cv2.GaussianBlur(x * y, (11, 11), 1.5) - mean_x * mean_y
        numerator = (2.0 * mean_x * mean_y + c1) * (2.0 * covariance + c2)
        denominator = (
            (mean_x * mean_x + mean_y * mean_y + c1)
            * (variance_x + variance_y + c2)
        )
        values.append(numerator / np.maximum(denominator, 1e-12))
    return float(np.mean(np.stack(values, axis=2)[mask]))


def _sample_reference_rgba(
    patch: LockedPatch, coordinates: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Sample the locked rest texture at fractional source coordinates.

    Using the same premultiplied-linear reconstruction model as the forward
    warp avoids counting an intentional subpixel bicubic sample as texture
    damage.  Separate sharpness gates still detect blur after deformation.
    """
    if not len(coordinates):
        return np.empty((0, 4), dtype=np.uint8), np.empty((0,), dtype=bool)
    x0, y0, x1, y1 = patch.bbox_xyxy
    height, width = patch.rgba.shape[:2]
    finite = np.all(np.isfinite(coordinates), axis=1)
    valid = (
        finite
        & (coordinates[:, 0] >= x0 - 0.5)
        & (coordinates[:, 0] <= x1 - 0.5)
        & (coordinates[:, 1] >= y0 - 0.5)
        & (coordinates[:, 1] <= y1 - 0.5)
    )
    sampled = np.zeros((len(coordinates), 4), dtype=np.uint8)
    if np.any(valid):
        premultiplied = _patch_local_premultiplied(patch)
        valid_coordinates = coordinates[valid] - np.asarray((x0, y0))
        chunks: list[np.ndarray] = []
        for start in range(0, len(valid_coordinates), 30_000):
            rows = valid_coordinates[start : start + 30_000]
            values = cv2.remap(
                premultiplied,
                rows[:, 0].astype(np.float32).reshape(-1, 1),
                rows[:, 1].astype(np.float32).reshape(-1, 1),
                interpolation=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0.0, 0.0, 0.0, 0.0),
            )
            chunks.append(_linear_premultiplied_to_rgba(values)[:, 0])
        sampled[valid] = np.concatenate(chunks, axis=0)
    return sampled, valid


def _edge_chamfer_p95(first: np.ndarray, second: np.ndarray) -> float:
    kernel = np.ones((3, 3), dtype=np.uint8)
    first_edge = first & ~(cv2.erode(first.astype(np.uint8), kernel) > 0)
    second_edge = second & ~(cv2.erode(second.astype(np.uint8), kernel) > 0)
    distance_to_first = cv2.distanceTransform((~first_edge).astype(np.uint8), cv2.DIST_L2, 5)
    distance_to_second = cv2.distanceTransform((~second_edge).astype(np.uint8), cv2.DIST_L2, 5)
    distances = np.concatenate((distance_to_second[first_edge], distance_to_first[second_edge]))
    return float(np.percentile(distances, 95)) if len(distances) else 0.0


def _secondary_alpha_edge_fraction(
    textured_alpha: np.ndarray, expected_geometry: np.ndarray
) -> float:
    kernel = np.ones((3, 3), dtype=np.uint8)
    textured_edge = textured_alpha & ~(
        cv2.erode(textured_alpha.astype(np.uint8), kernel) > 0
    )
    expected_interior = cv2.erode(
        expected_geometry.astype(np.uint8), kernel, iterations=2
    ) > 0
    internal_transparency = expected_interior & ~textured_alpha
    secondary = textured_edge & (
        cv2.dilate(internal_transparency.astype(np.uint8), kernel) > 0
    )
    return float(np.count_nonzero(secondary) / max(1, np.count_nonzero(textured_edge)))


def _meaningful_components(mask: np.ndarray, maximum_speckle_area: int) -> int:
    """Count visible components after excluding contract-allowed one-pixel ringing."""
    count, _, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    return sum(
        int(stats[label, cv2.CC_STAT_AREA]) > maximum_speckle_area
        for label in range(1, count)
    )


def _visible_seam_metrics(
    owner: np.ndarray,
    candidates: dict[str, np.ndarray],
    phase31: FlatMechanicsFrame,
    adjacent_pairs: list[list[str]],
) -> tuple[dict[str, dict[str, Any]], float, float]:
    kernel = np.ones((5, 5), dtype=np.uint8)
    rows: dict[str, dict[str, Any]] = {}
    p95_values: list[float] = []
    source_divergence_values: list[float] = []
    for first, second in adjacent_pairs:
        first_index = REGION_IDS.index(first)
        second_index = REGION_IDS.index(second)
        first_owner = owner == first_index
        second_owner = owner == second_index
        boundary = (
            cv2.dilate(first_owner.astype(np.uint8), kernel) > 0
        ) & (cv2.dilate(second_owner.astype(np.uint8), kernel) > 0)
        overlap = (
            phase31.source_region_masks[first]
            & phase31.source_region_masks[second]
            & _occupied_alpha(candidates[first][:, :, 3])
            & _occupied_alpha(candidates[second][:, :, 3])
        )
        band = boundary & overlap
        if np.any(band):
            first_rgba = _linear_premultiplied_to_rgba(
                candidates[first][band].reshape(-1, 1, 4)
            )[:, 0]
            second_rgba = _linear_premultiplied_to_rgba(
                candidates[second][band].reshape(-1, 1, 4)
            )[:, 0]
            disagreement = np.max(
                np.abs(
                    first_rgba[:, :3].astype(np.int16)
                    - second_rgba[:, :3].astype(np.int16)
                ),
                axis=1,
            )
            p95 = float(np.percentile(disagreement, 95))
            first_coordinates = _source_coordinates_for_selection(
                first, band, phase31
            )
            second_coordinates = _source_coordinates_for_selection(
                second, band, phase31
            )
            source_divergence = np.linalg.norm(
                first_coordinates - second_coordinates, axis=1
            )
            source_divergence_p95 = float(
                np.percentile(source_divergence, 95)
            )
        else:
            p95 = None
            source_divergence_p95 = None
        if p95 is not None:
            p95_values.append(p95)
        if source_divergence_p95 is not None:
            source_divergence_values.append(source_divergence_p95)
        rows[f"{first}__{second}"] = {
            "boundary_band_pixels": int(np.count_nonzero(band)),
            "candidate_rgb_disagreement_p95": p95,
            "cross_owner_source_coordinate_divergence_p95_px": (
                source_divergence_p95
            ),
            "evaluable": bool(np.any(band)),
        }
    return (
        rows,
        max(p95_values, default=0.0),
        max(source_divergence_values, default=0.0),
    )


def _deformation_gradient_metrics(
    patches: dict[str, LockedPatch], phase31: FlatMechanicsFrame
) -> dict[str, Any]:
    matrix_batches: list[np.ndarray] = []
    per_region_evidence: dict[str, dict[str, Any]] = {}
    for identifier in REGION_IDS:
        if identifier == "lower_garment":
            controls = phase31.cage_controls[identifier]
            source = controls["source"]
            if np.array_equal(source, controls["destination"]):
                matrices = np.eye(2, dtype=np.float64)[None, :, :]
                eligible_count = int(
                    np.count_nonzero(patches[identifier].semantic_support_mask)
                )
                evaluated_count = eligible_count
            else:
                parameters = _tps_parameters(source, controls["destination"] - source)
                mask = patches[identifier].semantic_support_mask
                ys, xs = np.where(mask)
                points = np.column_stack((xs, ys)).astype(np.float64)
                epsilon = 0.5
                derivative_x = (
                    _tps_displacement(points + (epsilon, 0.0), source, parameters)
                    - _tps_displacement(points - (epsilon, 0.0), source, parameters)
                ) / (2.0 * epsilon)
                derivative_y = (
                    _tps_displacement(points + (0.0, epsilon), source, parameters)
                    - _tps_displacement(points - (0.0, epsilon), source, parameters)
                ) / (2.0 * epsilon)
                matrices = np.empty((len(points), 2, 2), dtype=np.float64)
                matrices[:, 0, 0] = 1.0 + derivative_x[:, 0]
                matrices[:, 0, 1] = derivative_y[:, 0]
                matrices[:, 1, 0] = derivative_x[:, 1]
                matrices[:, 1, 1] = 1.0 + derivative_y[:, 1]
                eligible_count = len(points)
                evaluated_count = len(points)
        else:
            matrices = phase31.region_transforms[identifier][None, :2, :2]
            eligible_count = 1
            evaluated_count = 1
        matrix_batches.append(matrices)
        per_region_evidence[identifier] = {
            "eligible_jacobian_count": int(eligible_count),
            "evaluated_jacobian_count": int(evaluated_count),
            "coverage_fraction": float(evaluated_count / max(1, eligible_count)),
            "domain": (
                "every_semantic_support_pixel"
                if identifier == "lower_garment"
                else "exact_affine_jacobian"
            ),
        }
    all_matrices = np.concatenate(matrix_batches, axis=0)
    values = np.linalg.svd(all_matrices, compute_uv=False)
    minimum_values = np.maximum(values[:, 1], 1e-12)
    first = all_matrices[:, :, 0]
    second = all_matrices[:, :, 1]
    shear_cosines = np.abs(np.sum(first * second, axis=1)) / np.maximum(
        1e-12, np.linalg.norm(first, axis=1) * np.linalg.norm(second, axis=1)
    )
    return {
        "minimum_singular_value": float(np.min(values)),
        "maximum_singular_value": float(np.max(values)),
        "maximum_anisotropy": float(np.max(values[:, 0] / minimum_values)),
        "maximum_shear_cosine": float(np.max(shear_cosines)),
        "jacobian_evidence": per_region_evidence,
    }


def _material_points_preview(
    patches: dict[str, LockedPatch], phase31: FlatMechanicsFrame
) -> dict[str, np.ndarray]:
    scale = np.asarray((PREVIEW_SIZE[0] / SOURCE_SIZE[0], PREVIEW_SIZE[1] / SOURCE_SIZE[1]))
    output: dict[str, np.ndarray] = {}
    for identifier in REGION_IDS:
        mask = patches[identifier].rest_owner_mask
        boundary = mask & ~(
            cv2.erode(mask.astype(np.uint8), np.ones((3, 3), dtype=np.uint8)) > 0
        )
        y_grid, x_grid = np.indices(mask.shape)
        dense_grid = mask & (x_grid % 4 == 0) & (y_grid % 4 == 0)
        evidence_mask = boundary | dense_grid
        ys, xs = np.where(evidence_mask)
        points = np.column_stack((xs, ys)).astype(np.float64)
        if identifier == "lower_garment":
            controls = phase31.cage_controls[identifier]
            if np.array_equal(controls["source"], controls["destination"]):
                destination = points
            else:
                parameters = _tps_parameters(
                    controls["source"], controls["destination"] - controls["source"]
                )
                destination = points + _tps_displacement(points, controls["source"], parameters)
        else:
            matrix = phase31.region_transforms[identifier]
            homogeneous = np.column_stack((points, np.ones(len(points))))
            destination = (homogeneous @ matrix.T)[:, :2]
        output[identifier] = destination * scale
    return output


def _registered_character(
    raw_rgba: np.ndarray, phase31_contract: dict[str, Any]
) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
    lock = phase31_contract["phase30_lock"]
    control_path = _locked_path(lock["inherited_control_and_metadata"]["control"], "Phase30 control")
    control = json.loads(control_path.read_text(encoding="utf-8"))
    pose = next(row for row in control["poses"] if row["id"] == "POSE_100_STANDING")
    image = Image.fromarray(raw_rgba, mode="RGBA")
    try:
        registered, registration_report = registered_pose_layer(
            image, pose, control["contact_registration"]
        )
        try:
            return np.asarray(registered, dtype=np.uint8).copy(), control, pose
        finally:
            registered.close()
    finally:
        image.close()


def _remove_registration_ringing_speckles(
    registered_rgba: np.ndarray, maximum_area: int
) -> tuple[np.ndarray, int]:
    """Remove only detached one-pixel alpha islands created by bicubic registration."""
    alpha = _occupied_alpha(registered_rgba[:, :, 3])
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        alpha.astype(np.uint8), connectivity=8
    )
    if count <= 2:
        return registered_rgba, 0
    areas = stats[1:, cv2.CC_STAT_AREA]
    largest_label = int(np.argmax(areas)) + 1
    removable = np.zeros(alpha.shape, dtype=bool)
    removed = 0
    for label in range(1, count):
        if label == largest_label:
            continue
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area <= maximum_area:
            removable |= labels == label
            removed += area
    if not removed:
        return registered_rgba, 0
    cleaned = registered_rgba.copy()
    cleaned[removable] = 0
    return cleaned, removed


def _contact_shadow_alpha(registered_boot_mask: np.ndarray, contract: dict[str, Any]) -> np.ndarray:
    mask = registered_boot_mask.astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 7))
    expanded = cv2.dilate(mask, kernel)
    shifted = np.zeros_like(expanded)
    shifted[4:] = expanded[:-4]
    sigma = float(contract["scene"]["contact_shadow"]["source_blur_radius_px"])
    blurred = cv2.GaussianBlur(shifted, (0, 0), sigmaX=sigma, sigmaY=max(1.0, sigma * 0.35))
    return blurred.astype(np.float32) / 255.0 * float(contract["scene"]["contact_shadow"]["opacity"])


def _composite_beauty(
    registered_rgba: np.ndarray,
    registered_boot_mask: np.ndarray,
    environment_rgb: np.ndarray,
    contract: dict[str, Any],
) -> np.ndarray:
    background = _srgb_to_linear(environment_rgb.astype(np.float32) / 255.0)
    shadow_alpha = _contact_shadow_alpha(registered_boot_mask, contract)[:, :, None]
    shadow_rgb = _srgb_to_linear(
        np.asarray(contract["scene"]["contact_shadow"]["rgb"], dtype=np.float32)[None, None, :] / 255.0
    )
    background = shadow_rgb * shadow_alpha + background * (1.0 - shadow_alpha)
    character = registered_rgba.astype(np.float32) / 255.0
    character_alpha = character[:, :, 3:4]
    character_linear = _srgb_to_linear(character[:, :, :3])
    composite = character_linear * character_alpha + background * (1.0 - character_alpha)
    resized = cv2.resize(composite, OUTPUT_SIZE, interpolation=cv2.INTER_LANCZOS4)
    return np.round(np.clip(_linear_to_srgb(np.clip(resized, 0.0, 1.0)), 0.0, 1.0) * 255.0).astype(np.uint8)


def _prepare_dependencies(
    contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, LockedPatch], np.ndarray, np.ndarray]:
    locks = contract["locks"]
    phase30_contract = load_reconstruction_contract(
        _locked_path(locks["phase30_contract"], "Phase30 contract")
    )
    phase30_report, _, reconstruction_image = evaluate_reconstruction_lock(phase30_contract)
    reconstruction_image.close()
    if not phase30_report["machine_passed"]:
        raise ReconstructionLockedTexturedMechanicsError("Phase30 machine gate did not pass")
    patches = extract_locked_patches(phase30_contract)
    phase31_contract = load_connected_region_mechanics_contract(
        _locked_path(locks["phase31_contract"], "Phase31 contract")
    )
    source = recompose_locked_patches(patches, (SOURCE_SIZE[1], SOURCE_SIZE[0], 4))
    environment_path = _locked_path(locks["clean_environment"], "clean environment")
    with Image.open(environment_path) as image:
        environment = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
    return phase30_contract, phase31_contract, patches, source, environment


def _assert_locked_frame_inputs(
    contract: dict[str, Any],
    patches: dict[str, LockedPatch],
    source_reconstruction: np.ndarray | None,
    environment_rgb: np.ndarray | None,
) -> None:
    """Reject injected arrays that are not byte-exact Phase 30/scene inputs."""
    phase30_contract = load_reconstruction_contract(
        _locked_path(contract["locks"]["phase30_contract"], "Phase30 contract")
    )
    expected_patches = extract_locked_patches(phase30_contract)
    _require_equal(set(patches), set(expected_patches), "locked patch identifiers")
    scalar_fields = ("identifier", "kind", "bbox_xyxy", "source_coordinate_hash")
    array_fields = (
        "rgba",
        "source_mask",
        "semantic_support_mask",
        "semantic_owner_mask",
        "rest_owner_mask",
    )
    for identifier in REGION_IDS:
        actual = patches[identifier]
        expected = expected_patches[identifier]
        for field in scalar_fields:
            _require_equal(
                getattr(actual, field),
                getattr(expected, field),
                f"{identifier} {field}",
            )
        for field in array_fields:
            if not np.array_equal(getattr(actual, field), getattr(expected, field)):
                raise ReconstructionLockedTexturedMechanicsError(
                    f"{identifier} {field} differs from the locked Phase30 patch"
                )
    expected_source = recompose_locked_patches(
        expected_patches, (SOURCE_SIZE[1], SOURCE_SIZE[0], 4)
    )
    if source_reconstruction is not None and not np.array_equal(
        source_reconstruction, expected_source
    ):
        raise ReconstructionLockedTexturedMechanicsError(
            "injected source reconstruction differs from Phase30"
        )
    if environment_rgb is not None:
        with Image.open(
            _locked_path(contract["locks"]["clean_environment"], "clean environment")
        ) as image:
            expected_environment = np.asarray(image.convert("RGB"), dtype=np.uint8)
            if not np.array_equal(environment_rgb, expected_environment):
                raise ReconstructionLockedTexturedMechanicsError(
                    "injected environment differs from the locked clean porch"
                )


def render_textured_mechanics_frame(
    contract: dict[str, Any],
    phase30_patches: dict[str, LockedPatch],
    frame: int,
    *,
    phase31_contract: dict[str, Any] | None = None,
    source_reconstruction: np.ndarray | None = None,
    environment_rgb: np.ndarray | None = None,
    reference_registered: np.ndarray | None = None,
    _prepared_dependencies_verified: bool = False,
) -> TexturedMechanicsFrame:
    """Render one source, registered, and 1080p textured Phase 32 frame."""
    _validate_contract(contract)
    if set(phase30_patches) != set(REGION_IDS):
        raise ReconstructionLockedTexturedMechanicsError("Phase32 requires exactly nine locked patches")
    if not _prepared_dependencies_verified:
        _assert_locked_frame_inputs(
            contract, phase30_patches, source_reconstruction, environment_rgb
        )
    if phase31_contract is None:
        phase31_contract = load_connected_region_mechanics_contract(
            _locked_path(contract["locks"]["phase31_contract"], "Phase31 contract")
        )
    if source_reconstruction is None:
        source_reconstruction = recompose_locked_patches(
            phase30_patches, (SOURCE_SIZE[1], SOURCE_SIZE[0], 4)
        )
    if environment_rgb is None:
        with Image.open(_locked_path(contract["locks"]["clean_environment"], "clean environment")) as image:
            environment_rgb = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
    phase31 = render_flat_mechanics_frame(phase31_contract, phase30_patches, frame)
    endpoint = frame in (1, 49)
    height, width = SOURCE_SIZE[1], SOURCE_SIZE[0]
    visible_region_masks = _transported_visible_masks(phase30_patches, phase31)
    desired_geometry = np.logical_or.reduce(list(visible_region_masks.values()))
    transported = _transported_owner_masks(phase30_patches, phase31)
    if endpoint:
        raw = source_reconstruction.copy()
        owner = np.full((height, width), -1, dtype=np.int16)
        for index, identifier in enumerate(REGION_IDS):
            owner[phase30_patches[identifier].rest_owner_mask] = index
        source_xy = np.full((height, width, 2), np.nan, dtype=np.float32)
        ys, xs = np.where(_occupied_alpha(raw[:, :, 3]))
        source_xy[ys, xs] = np.column_stack((xs, ys)).astype(np.float32)
        ownership_metrics = {
            "phase31_geometry_pixels": int(np.count_nonzero(raw[:, :, 3] > ALPHA_THRESHOLD)),
            "phase31_geometry_pixels_uncovered": 0,
            "overlap_fallback_pixels": 0,
            "overlap_fallback_fraction": 0.0,
            "coverage_fallback_pixels": 0,
            "selected_owners_per_occupied_pixel_minimum": 1,
            "selected_owners_per_occupied_pixel_maximum": 1,
            "multiply_composited_character_pixels": 0,
        }
        texture_region_masks = {
            identifier: visible_region_masks[identifier].copy()
            for identifier in REGION_IDS
        }
        endpoint_premultiplied = _rgba_to_linear_premultiplied(raw)
        premultiplied_nonfinite_values = int(
            np.count_nonzero(~np.isfinite(endpoint_premultiplied))
        )
        premultiplied_rgb_over_alpha_excess = float(
            max(
                0.0,
                np.max(
                    endpoint_premultiplied[:, :, :3]
                    - endpoint_premultiplied[:, :, 3:4]
                ),
            )
        )
        del endpoint_premultiplied
        per_pair_seams = {
            f"{first}__{second}": {
                "boundary_band_pixels": 0,
                "candidate_rgb_disagreement_p95": None,
                "cross_owner_source_coordinate_divergence_p95_px": None,
                "evaluable": False,
            }
            for first, second in contract["ownership_policy"]["required_adjacent_pairs"]
        }
        disagreement_p95 = 0.0
        source_divergence_p95 = 0.0
    else:
        candidates: dict[str, np.ndarray] = {}
        texture_region_masks: dict[str, np.ndarray] = {}
        for identifier in contract["ownership_policy"]["priority"]:
            candidate = _candidate_premultiplied(
                identifier,
                phase30_patches[identifier],
                phase31,
                (height, width),
            )
            candidates[identifier] = candidate
            texture_region_masks[identifier] = (
                visible_region_masks[identifier]
                & _occupied_alpha(candidate[:, :, 3])
            )
        owner, fallback, ownership_metrics = _resolve_transported_ownership(
            texture_region_masks,
            transported,
            contract["ownership_policy"]["priority"],
            desired_geometry=desired_geometry,
        )
        final_premultiplied = np.zeros((height, width, 4), dtype=np.float32)
        source_xy = np.full((height, width, 2), np.nan, dtype=np.float32)
        for identifier in contract["ownership_policy"]["priority"]:
            candidate = candidates[identifier]
            index = REGION_IDS.index(identifier)
            selected = owner == index
            final_premultiplied[selected] = candidate[selected]
            coordinates = _source_coordinates_for_selection(identifier, selected, phase31)
            ys, xs = np.where(selected)
            source_xy[ys, xs] = coordinates.astype(np.float32)
        coverage_owner, _, _ = _resolve_transported_ownership(
            visible_region_masks,
            transported,
            contract["ownership_policy"]["priority"],
            desired_geometry=desired_geometry,
        )
        coverage_holes = desired_geometry & (
            (owner < 0) | ~_occupied_alpha(final_premultiplied[:, :, 3])
        )
        for index, identifier in enumerate(REGION_IDS):
            selected_holes = coverage_holes & (coverage_owner == index)
            if not np.any(selected_holes):
                continue
            coordinates = _source_coordinates_for_selection(
                identifier, selected_holes, phase31
            )
            ys, xs = np.where(selected_holes)
            repaired, actual_coordinates = _nearest_visible_patch_premultiplied(
                phase30_patches[identifier], coordinates
            )
            final_premultiplied[ys, xs] = repaired
            owner[ys, xs] = index
            source_xy[ys, xs] = actual_coordinates.astype(np.float32)
            texture_region_masks[identifier][ys, xs] = True
        ownership_metrics["coverage_fallback_pixels"] = int(
            np.count_nonzero(coverage_holes)
        )
        premultiplied_nonfinite_values = int(
            np.count_nonzero(~np.isfinite(final_premultiplied))
        )
        premultiplied_rgb_over_alpha_excess = float(
            max(
                0.0,
                np.max(
                    final_premultiplied[:, :, :3]
                    - final_premultiplied[:, :, 3:4]
                ),
            )
        )
        raw = _linear_premultiplied_to_rgba(final_premultiplied)
        uncovered_after_quantization = desired_geometry & ~_occupied_alpha(
            raw[:, :, 3]
        )
        ownership_metrics["phase31_geometry_pixels_uncovered"] = int(
            np.count_nonzero(uncovered_after_quantization)
        )
        if ownership_metrics["phase31_geometry_pixels_uncovered"]:
            ownership_metrics["selected_owners_per_occupied_pixel_minimum"] = 0
        else:
            ownership_metrics["selected_owners_per_occupied_pixel_minimum"] = 1
        per_pair_seams, disagreement_p95, source_divergence_p95 = _visible_seam_metrics(
            owner,
            candidates,
            phase31,
            contract["ownership_policy"]["required_adjacent_pairs"],
        )
        del candidates, final_premultiplied

    registered, control, pose = _registered_character(raw, phase31_contract)
    registration_ringing_speckles_removed = 0
    if not endpoint:
        registered, registration_ringing_speckles_removed = (
            _remove_registration_ringing_speckles(
                registered,
                int(
                    contract["texture_policy"][
                        "maximum_registration_ringing_speckle_area_px"
                    ]
                ),
            )
        )
    raw_owner_masks = {
        identifier: owner == index for index, identifier in enumerate(REGION_IDS)
    }
    registered_owner_masks = _register_region_masks(
        raw_owner_masks,
        pose,
        control["contact_registration"],
        ALPHA_THRESHOLD,
    )
    registered_texture_region_masks = _register_region_masks(
        visible_region_masks,
        pose,
        control["contact_registration"],
        ALPHA_THRESHOLD,
    )
    expected_registered_visible_masks = _register_region_masks(
        visible_region_masks,
        pose,
        control["contact_registration"],
        ALPHA_THRESHOLD,
    )
    registered_geometry = np.logical_or.reduce(
        list(expected_registered_visible_masks.values())
    )
    registered_alpha = _occupied_alpha(registered[:, :, 3])
    intersection = int(np.count_nonzero(registered_alpha & registered_geometry))
    union = int(np.count_nonzero(registered_alpha | registered_geometry))
    preview_registered = cv2.resize(
        registered_alpha.astype(np.uint8), PREVIEW_SIZE, interpolation=cv2.INTER_NEAREST
    ) > 0
    preview_geometry = cv2.resize(
        registered_geometry.astype(np.uint8),
        PREVIEW_SIZE,
        interpolation=cv2.INTER_NEAREST,
    ) > 0
    per_region_geometry: dict[str, dict[str, float | int]] = {}
    for identifier in REGION_IDS:
        textured_mask = registered_texture_region_masks[identifier] & registered_alpha
        expected_mask = expected_registered_visible_masks[identifier]
        region_intersection = int(np.count_nonzero(textured_mask & expected_mask))
        region_union = int(np.count_nonzero(textured_mask | expected_mask))
        per_region_geometry[identifier] = {
            "components": _meaningful_components(
                textured_mask,
                int(
                    contract["texture_policy"][
                        "maximum_registration_ringing_speckle_area_px"
                    ]
                ),
            ),
            "expected_components": _meaningful_components(
                expected_mask,
                int(
                    contract["texture_policy"][
                        "maximum_registration_ringing_speckle_area_px"
                    ]
                ),
            ),
            "alpha_iou_to_phase31": float(region_intersection / max(1, region_union)),
            "alpha_edge_chamfer_p95_preview_px": _edge_chamfer_p95(
                cv2.resize(
                    textured_mask.astype(np.uint8), PREVIEW_SIZE, interpolation=cv2.INTER_NEAREST
                )
                > 0,
                cv2.resize(
                    expected_mask.astype(np.uint8),
                    PREVIEW_SIZE,
                    interpolation=cv2.INTER_NEAREST,
                )
                > 0,
            ),
        }
    geometry_metrics = {
        "per_region": per_region_geometry,
        "registered_character_alpha_iou_to_phase31": float(intersection / max(1, union)),
        "bidirectional_alpha_edge_chamfer_p95_preview_px": _edge_chamfer_p95(
            preview_registered, preview_geometry
        ),
        "phase31_geometry_pixels_uncovered": ownership_metrics["phase31_geometry_pixels_uncovered"],
        "character_pixels_outside_phase31_geometry": int(
            np.count_nonzero((raw[:, :, 3] > ALPHA_THRESHOLD) & ~desired_geometry)
        ),
        "minimum_registered_region_alpha_iou_to_phase31": min(
            row["alpha_iou_to_phase31"] for row in per_region_geometry.values()
        ),
        "maximum_registered_region_alpha_edge_chamfer_p95_preview_px": max(
            row["alpha_edge_chamfer_p95_preview_px"]
            for row in per_region_geometry.values()
        ),
        "minimum_registered_region_components": min(
            row["components"] for row in per_region_geometry.values()
        ),
        "maximum_registered_region_components": max(
            row["components"] for row in per_region_geometry.values()
        ),
        "registered_character_union_components": _components(
            registered_alpha
        ),
        "registration_ringing_speckles_removed": registration_ringing_speckles_removed,
    }
    selected = owner >= 0
    coordinates = source_xy[selected]
    if endpoint:
        reference_rgba = source_reconstruction[selected]
        coordinate_valid = np.ones((len(coordinates),), dtype=bool)
    else:
        reference_rgba = np.zeros((len(coordinates), 4), dtype=np.uint8)
        coordinate_valid = np.zeros((len(coordinates),), dtype=bool)
        selected_region_indices = owner[selected]
        for index, identifier in enumerate(REGION_IDS):
            region = selected_region_indices == index
            sampled, valid = _sample_reference_rgba(
                phase30_patches[identifier], coordinates[region]
            )
            reference_rgba[region] = sampled
            coordinate_valid[region] = valid
    selected_region_indices = owner[selected]
    reference_rgb = reference_rgba[:, :3]
    output_rgb = raw[selected, :3]
    opaque = raw[selected, 3] >= 242
    comparable = coordinate_valid & opaque
    errors = np.abs(output_rgb[comparable].astype(np.int16) - reference_rgb[comparable].astype(np.int16))
    per_region: dict[str, dict[str, float]] = {}
    laplacian_ratios: list[float] = []
    expected_rgb = np.zeros_like(raw[:, :, :3])
    expected_rgb[selected] = reference_rgb
    comparable_map = np.zeros((height, width), dtype=bool)
    comparable_map[selected] = comparable
    output_gray = cv2.cvtColor(raw[:, :, :3], cv2.COLOR_RGB2GRAY)
    expected_gray = cv2.cvtColor(expected_rgb, cv2.COLOR_RGB2GRAY)
    output_laplacian = cv2.Laplacian(output_gray, cv2.CV_32F)
    expected_laplacian = cv2.Laplacian(expected_gray, cv2.CV_32F)
    erosion_kernel = np.ones((3, 3), dtype=np.uint8)
    for index, identifier in enumerate(REGION_IDS):
        region_select = selected_region_indices == index
        region_compare = comparable & region_select
        region_output = output_rgb[region_compare]
        region_reference = reference_rgb[region_compare]
        if not len(region_output):
            raise ReconstructionLockedTexturedMechanicsError(
                f"frame {frame} has no source-aligned texture samples for {identifier}"
            )
        per_region[identifier] = {
            "psnr_db": _vector_psnr(region_reference, region_output),
            "ssim": _masked_spatial_ssim(
                expected_rgb,
                raw[:, :, :3],
                cv2.erode(
                    ((owner == index) & comparable_map).astype(np.uint8),
                    erosion_kernel,
                )
                > 0,
            ),
            "mean_absolute_error": float(
                np.mean(np.abs(region_reference.astype(np.int16) - region_output.astype(np.int16)))
            ),
            "p95_absolute_error": float(
                np.percentile(
                    np.abs(region_reference.astype(np.int16) - region_output.astype(np.int16)),
                    95,
                )
            ),
        }
        interior = cv2.erode((owner == index).astype(np.uint8), erosion_kernel) > 0
        destination_variance = float(np.var(output_laplacian[interior]))
        expected_variance = float(np.var(expected_laplacian[interior]))
        laplacian_ratios.append(destination_variance / max(expected_variance, 1e-6))
    face_index = REGION_IDS.index("head_neck")
    face_source = np.zeros((height, width), dtype=bool)
    face_x0, face_y0, face_x1, face_y1 = contract["texture_policy"][
        "face_identity_source_roi_xyxy"
    ]
    face_source[face_y0:face_y1, face_x0:face_x1] = True
    face_source &= phase30_patches["head_neck"].semantic_support_mask
    face_destination = _warp_binary_affine(
        face_source, phase31.region_transforms["head_neck"]
    )
    face_erosion = 2 * int(contract["texture_policy"]["face_identity_ssim_erosion_px"]) + 1
    face_mask = cv2.erode(
        ((owner == face_index) & comparable_map & face_destination).astype(np.uint8),
        np.ones((face_erosion, face_erosion), dtype=np.uint8),
    ) > 0
    face_output = raw[:, :, :3][face_mask]
    face_reference = expected_rgb[face_mask]
    endpoint_raw_mismatch = int(
        np.count_nonzero(np.any(raw != source_reconstruction, axis=2))
    ) if endpoint else 0
    if reference_registered is None:
        reference_registered, _, _ = _registered_character(
            source_reconstruction, phase31_contract
        )
    endpoint_registered_mismatch = int(
        np.count_nonzero(np.any(registered != reference_registered, axis=2))
    ) if endpoint else 0
    reference_registered_hash = hashlib.sha256(reference_registered.tobytes()).hexdigest()
    _require_equal(
        reference_registered_hash,
        contract["locks"]["phase30_registered_rest_rgba_bytes_sha256"],
        "Phase30 registered rest RGBA bytes",
    )
    nonzero_rgb_under_zero_alpha = int(
        np.count_nonzero(np.any(raw[:, :, :3] != 0, axis=2) & (raw[:, :, 3] == 0))
    )
    texture_metrics = {
        "per_region": per_region,
        "minimum_region_psnr_db": min(row["psnr_db"] for row in per_region.values()),
        "minimum_region_ssim": min(row["ssim"] for row in per_region.values()),
        "face_psnr_db": _vector_psnr(face_reference, face_output),
        "face_ssim": _masked_spatial_ssim(
            expected_rgb, raw[:, :, :3], face_mask
        ),
        "minimum_laplacian_variance_ratio": min(laplacian_ratios),
        "maximum_laplacian_variance_ratio": max(laplacian_ratios),
        "mean_source_aligned_rgb_error": float(np.mean(errors)) if errors.size else 0.0,
        "p95_source_aligned_rgb_error": float(np.percentile(errors, 95)) if errors.size else 0.0,
        "endpoint_raw_rgba_mismatched_pixels": endpoint_raw_mismatch,
        "endpoint_registered_rgba_mismatched_pixels": endpoint_registered_mismatch,
        "valid_source_coordinate_fraction": float(np.mean(coordinate_valid)),
        "nonzero_rgb_pixels_where_alpha_zero": nonzero_rgb_under_zero_alpha,
        "nonfinite_values": premultiplied_nonfinite_values,
        "premultiplied_rgb_over_alpha_excess": premultiplied_rgb_over_alpha_excess,
        "samples_outside_locked_patch_arrays": int(np.count_nonzero(~coordinate_valid)),
        "generated_character_texture_pixels": 0,
        "ai_generated_character_pixels": 0,
        "inpainted_character_pixels": 0,
        "character_texture_source_count": 1,
    }
    visible_seam_errors: list[float] = []
    seam_kernel = np.ones((5, 5), dtype=np.uint8)
    for first, second in contract["ownership_policy"]["required_adjacent_pairs"]:
        first_owner = owner == REGION_IDS.index(first)
        second_owner = owner == REGION_IDS.index(second)
        visible_band = (
            (cv2.dilate(first_owner.astype(np.uint8), seam_kernel) > 0)
            & (cv2.dilate(second_owner.astype(np.uint8), seam_kernel) > 0)
            & comparable_map
        )
        if np.any(visible_band):
            visible_error = np.max(
                np.abs(
                    raw[:, :, :3][visible_band].astype(np.int16)
                    - expected_rgb[visible_band].astype(np.int16)
                ),
                axis=1,
            )
            visible_p95 = float(np.percentile(visible_error, 95))
        else:
            visible_p95 = 0.0
        per_pair_seams[f"{first}__{second}"][
            "source_aligned_visible_rgb_error_p95"
        ] = visible_p95
        visible_seam_errors.append(visible_p95)
    seam_metrics = {
        **ownership_metrics,
        "per_pair": per_pair_seams,
        "unowned_alpha_pixels": int(np.count_nonzero((raw[:, :, 3] > ALPHA_THRESHOLD) & (owner < 0))),
        "internal_transparent_seam_paths": _components(
            (cv2.erode(desired_geometry.astype(np.uint8), np.ones((3, 3), dtype=np.uint8)) > 0)
            & ~_occupied_alpha(raw[:, :, 3])
        ),
        "seam_candidate_rgb_disagreement_p95": disagreement_p95,
        "cross_owner_source_coordinate_divergence_p95_px": source_divergence_p95,
        "source_aligned_visible_seam_band_rgb_error_p95": max(
            visible_seam_errors, default=0.0
        ),
        "secondary_alpha_edge_fraction": _secondary_alpha_edge_fraction(
            _occupied_alpha(raw[:, :, 3]), desired_geometry
        ),
    }
    deformation_metrics = _deformation_gradient_metrics(phase30_patches, phase31)
    material_points = _material_points_preview(phase30_patches, phase31)
    registered_boots = (
        registered_owner_masks["left_boot"] | registered_owner_masks["right_boot"]
    ) & (registered[:, :, 3] > ALPHA_THRESHOLD)
    beauty = _composite_beauty(registered, registered_boots, environment_rgb, contract)
    return TexturedMechanicsFrame(
        frame=int(frame),
        raw_character_rgba=raw,
        registered_character_rgba=registered,
        beauty_rgb=beauty,
        owner_index=owner,
        registered_owner_masks=registered_owner_masks,
        source_coordinate_xy=source_xy,
        phase31_frame=phase31,
        geometry_metrics=geometry_metrics,
        texture_metrics=texture_metrics,
        seam_metrics=seam_metrics,
        deformation_metrics=deformation_metrics,
        material_points_preview=material_points,
    )


def _flatten_quality_gates(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        f"{section}.{identifier}": threshold
        for section, rows in contract["quality_gates"].items()
        for identifier, threshold in rows.items()
    }


def _gate_results(
    contract: dict[str, Any], measurements: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for identifier, threshold in _flatten_quality_gates(contract).items():
        section, gate_name = identifier.split(".", 1)
        if gate_name.startswith("minimum_"):
            operator = ">="
            metric_name = gate_name[len("minimum_") :]
        elif gate_name.startswith("maximum_"):
            operator = "<="
            metric_name = gate_name[len("maximum_") :]
        elif gate_name.startswith("required_"):
            operator = "=="
            metric_name = gate_name[len("required_") :]
        else:
            raise ReconstructionLockedTexturedMechanicsError(
                f"unsupported Phase32 gate prefix: {identifier}"
            )
        section_measurements = measurements.get(section, {})
        variant_name = (
            f"{metric_name}__minimum"
            if operator == ">="
            else f"{metric_name}__maximum"
        )
        measured = section_measurements.get(
            variant_name, section_measurements.get(metric_name)
        )
        comparable = measured is not None
        if isinstance(measured, (float, np.floating)) and not math.isfinite(float(measured)):
            comparable = False
        if not comparable:
            passed = False
        elif operator == ">=":
            passed = bool(measured >= threshold)
        elif operator == "<=":
            passed = bool(measured <= threshold)
        else:
            passed = bool(measured == threshold)
        rows.append(
            {
                "id": identifier,
                "measured": measured,
                "operator": operator,
                "threshold": threshold,
                "passed": passed,
            }
        )
    return rows


def _mask_bbox(mask: np.ndarray, padding: int = 0) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    if not len(xs):
        return (0, 0, 1, 1)
    height, width = mask.shape
    return (
        max(0, int(xs.min()) - padding),
        max(0, int(ys.min()) - padding),
        min(width, int(xs.max()) + 1 + padding),
        min(height, int(ys.max()) + 1 + padding),
    )


def _centered_box(
    mask: np.ndarray, width: int = 220, height: int = 150
) -> tuple[int, int, int, int]:
    y_values, x_values = np.where(mask)
    canvas_height, canvas_width = mask.shape
    if len(x_values):
        center_x = int(round(float(np.mean(x_values))))
        center_y = int(round(float(np.mean(y_values))))
    else:
        center_x = canvas_width // 2
        center_y = canvas_height // 2
    x0 = max(0, min(canvas_width - width, center_x - width // 2))
    y0 = max(0, min(canvas_height - height, center_y - height // 2))
    return (x0, y0, x0 + width, y0 + height)


def _frame_review_metadata(frame: TexturedMechanicsFrame) -> dict[str, Any]:
    owner_masks = frame.registered_owner_masks
    alpha = frame.registered_character_rgba[:, :, 3] > ALPHA_THRESHOLD
    subject = cv2.dilate(alpha.astype(np.uint8), np.ones((7, 7), dtype=np.uint8)) > 0
    groups = (
        ("neck_torso", ("head_neck", "torso_shell")),
        ("left_sleeve_hand", ("left_sleeve", "left_hand")),
        ("right_sleeve_hand_mug", ("right_sleeve", "right_hand_mug")),
        ("torso_lower", ("torso_shell", "lower_garment")),
        ("lower_boots", ("lower_garment", "left_boot", "right_boot")),
    )
    seam_boxes: dict[str, tuple[int, int, int, int]] = {}
    seam_pair_boxes: dict[str, tuple[int, int, int, int]] = {}
    kernel = np.ones((9, 9), dtype=np.uint8)
    for label, identifiers in groups:
        first = owner_masks[identifiers[0]]
        others = np.logical_or.reduce([owner_masks[row] for row in identifiers[1:]])
        boundary = (
            cv2.dilate(first.astype(np.uint8), kernel) > 0
        ) & (cv2.dilate(others.astype(np.uint8), kernel) > 0)
        seam_boxes[label] = _centered_box(boundary)
    for pair in frame.seam_metrics["per_pair"]:
        first, second = pair.split("__", 1)
        boundary = (
            cv2.dilate(owner_masks[first].astype(np.uint8), kernel) > 0
        ) & (cv2.dilate(owner_masks[second].astype(np.uint8), kernel) > 0)
        seam_pair_boxes[pair] = _centered_box(boundary)
    return {
        "subject_mask_source": subject,
        "face_box_source": _mask_bbox(owner_masks["head_neck"] & alpha, padding=12),
        "seam_boxes_source": seam_boxes,
        "seam_pair_boxes_source": seam_pair_boxes,
    }


def _aggregate_frame_measurements(
    frame_rows: list[dict[str, Any]],
    material_histories: dict[str, list[np.ndarray]],
) -> dict[str, dict[str, Any]]:
    geometry_rows = [row["geometry"] for row in frame_rows]
    texture_rows = [row["texture"] for row in frame_rows]
    seam_rows = [row["ownership"] for row in frame_rows]
    moving_rows = [
        row for row in frame_rows if int(row["frame"]) not in (1, 49)
    ]
    moving_seam_rows = [row["ownership"] for row in moving_rows]
    deformation_rows = [row["deformation"] for row in frame_rows]
    velocities: list[float] = []
    accelerations: list[float] = []
    jerks: list[float] = []
    material_extrema: dict[str, dict[str, Any]] = {}
    for identifier, history in material_histories.items():
        values = np.stack(history, axis=0)
        velocity = np.diff(values, axis=0)
        acceleration = np.diff(velocity, axis=0)
        jerk = np.diff(acceleration, axis=0)
        if velocity.size:
            norms = np.linalg.norm(velocity, axis=2)
            transition, point = np.unravel_index(int(np.argmax(norms)), norms.shape)
            value = float(norms[transition, point])
            velocities.append(value)
            material_extrema.setdefault("velocity", {})[identifier] = {
                "value": value,
                "transition_frames": [int(transition + 1), int(transition + 2)],
                "tracked_point_index": int(point),
            }
        if acceleration.size:
            norms = np.linalg.norm(acceleration, axis=2)
            transition, point = np.unravel_index(int(np.argmax(norms)), norms.shape)
            value = float(norms[transition, point])
            accelerations.append(value)
            material_extrema.setdefault("acceleration", {})[identifier] = {
                "value": value,
                "transition_frames": [
                    int(transition + 1),
                    int(transition + 2),
                    int(transition + 3),
                ],
                "tracked_point_index": int(point),
            }
        if jerk.size:
            norms = np.linalg.norm(jerk, axis=2)
            transition, point = np.unravel_index(int(np.argmax(norms)), norms.shape)
            value = float(norms[transition, point])
            jerks.append(value)
            material_extrema.setdefault("jerk", {})[identifier] = {
                "value": value,
                "transition_frames": [
                    int(transition + 1),
                    int(transition + 2),
                    int(transition + 3),
                    int(transition + 4),
                ],
                "tracked_point_index": int(point),
            }
    all_region_component_inventories_match = all(
        all(
            int(region["components"]) == int(region["expected_components"])
            and int(region["components"]) > 0
            for region in row["per_region"].values()
        )
        for row in geometry_rows
    )
    all_unions_connected = all(
        int(row["registered_character_union_components"]) == 1
        for row in geometry_rows
    )
    all_single_owner = all(
        int(row["selected_owners_per_occupied_pixel_minimum"]) == 1
        and int(row["selected_owners_per_occupied_pixel_maximum"]) == 1
        for row in seam_rows
    )
    pair_names = sorted(
        {
            pair
            for row in moving_seam_rows
            for pair in row["per_pair"]
        }
    )
    seam_argmax: dict[str, dict[str, Any]] = {}
    for pair in pair_names:
        evidence = [
            (int(row["frame"]), row["ownership"]["per_pair"][pair])
            for row in moving_rows
        ]
        evaluable = [item for item in evidence if item[1].get("evaluable")]
        if evaluable:
            frame_number, pair_row = max(
                evaluable,
                key=lambda item: float(
                    item[1].get("candidate_rgb_disagreement_p95") or 0.0
                ),
            )
            seam_argmax[pair] = {
                "frame": frame_number,
                "boundary_band_pixels": int(pair_row["boundary_band_pixels"]),
                "candidate_rgb_disagreement_p95": float(
                    pair_row["candidate_rgb_disagreement_p95"]
                ),
                "cross_owner_source_coordinate_divergence_p95_px": float(
                    pair_row[
                        "cross_owner_source_coordinate_divergence_p95_px"
                    ]
                ),
            }
        else:
            seam_argmax[pair] = {
                "frame": None,
                "boundary_band_pixels": 0,
                "candidate_rgb_disagreement_p95": None,
                "cross_owner_source_coordinate_divergence_p95_px": None,
            }
    return {
        "dependencies": {
            "all_locked_hashes_match": True,
            "phase30_machine_pass": True,
            "phase31_acceptance_receipt_machine_pass": True,
            "phase31_acceptance_gate_count": 82,
            "nine_patch_rgba_hashes_match": True,
        },
        "geometry": {
            "registered_character_alpha_iou_to_phase31": min(
                float(row["registered_character_alpha_iou_to_phase31"])
                for row in geometry_rows
            ),
            "bidirectional_alpha_edge_chamfer_p95_preview_px": max(
                float(row["bidirectional_alpha_edge_chamfer_p95_preview_px"])
                for row in geometry_rows
            ),
            "registered_region_alpha_iou_to_phase31": min(
                float(row["minimum_registered_region_alpha_iou_to_phase31"])
                for row in geometry_rows
            ),
            "registered_region_alpha_edge_chamfer_p95_preview_px": max(
                float(row["maximum_registered_region_alpha_edge_chamfer_p95_preview_px"])
                for row in geometry_rows
            ),
            "phase31_geometry_pixels_uncovered": max(
                int(row["phase31_geometry_pixels_uncovered"])
                for row in geometry_rows
            ),
            "character_pixels_outside_phase31_geometry": max(
                int(row["character_pixels_outside_phase31_geometry"])
                for row in geometry_rows
            ),
            "region_component_inventory_matches_locked_source": (
                all_region_component_inventories_match
            ),
            "character_union_components": 1 if all_unions_connected else 0,
        },
        "premultiplication": {
            "nonfinite_values": max(int(row["nonfinite_values"]) for row in texture_rows),
            "premultiplied_rgb_over_alpha_excess": max(
                float(row["premultiplied_rgb_over_alpha_excess"])
                for row in texture_rows
            ),
            "nonzero_rgb_pixels_where_alpha_zero": max(
                int(row["nonzero_rgb_pixels_where_alpha_zero"])
                for row in texture_rows
            ),
            "samples_outside_locked_patch_arrays": max(
                int(row["samples_outside_locked_patch_arrays"])
                for row in texture_rows
            ),
            "generated_character_texture_pixels": max(
                int(row["generated_character_texture_pixels"])
                for row in texture_rows
            ),
            "ai_generated_character_pixels": max(
                int(row["ai_generated_character_pixels"])
                for row in texture_rows
            ),
            "inpainted_character_pixels": max(
                int(row["inpainted_character_pixels"])
                for row in texture_rows
            ),
            "character_texture_source_count": max(
                int(row["character_texture_source_count"]) for row in texture_rows
            ),
            "valid_source_coordinate_fraction": min(
                float(row["valid_source_coordinate_fraction"])
                for row in texture_rows
            ),
        },
        "ownership": {
            "selected_owners_per_occupied_pixel": 1 if all_single_owner else 0,
            "multiply_composited_character_pixels": max(
                int(row["multiply_composited_character_pixels"])
                for row in seam_rows
            ),
            "unowned_alpha_pixels": max(
                int(row["unowned_alpha_pixels"]) for row in seam_rows
            ),
            "overlap_fallback_fraction": max(
                float(row["overlap_fallback_fraction"]) for row in seam_rows
            ),
            "internal_transparent_seam_paths": max(
                int(row["internal_transparent_seam_paths"]) for row in seam_rows
            ),
            "source_aligned_visible_seam_band_rgb_error_p95": max(
                float(row["source_aligned_visible_seam_band_rgb_error_p95"])
                for row in seam_rows
            ),
            "secondary_alpha_edge_fraction": max(
                float(row["secondary_alpha_edge_fraction"]) for row in seam_rows
            ),
            "visible_seam_boundary_band_pixels_per_pair": min(
                int(pair_row["boundary_band_pixels"])
                for row in moving_seam_rows
                for pair_row in row["per_pair"].values()
            ),
            "cross_owner_source_coordinate_divergence_p95_px": max(
                (
                    float(
                        pair_row[
                            "cross_owner_source_coordinate_divergence_p95_px"
                        ]
                    )
                    for row in moving_seam_rows
                    for pair_row in row["per_pair"].values()
                    if pair_row.get("evaluable")
                ),
                default=0.0,
            ),
            "candidate_rgb_disagreement_p95_diagnostic": max(
                (
                    float(pair_row["candidate_rgb_disagreement_p95"])
                    for row in moving_seam_rows
                    for pair_row in row["per_pair"].values()
                    if pair_row.get("evaluable")
                ),
                default=0.0,
            ),
            "seam_pair_argmax_evidence": seam_argmax,
        },
        "deformation": {
            "deformation_gradient_singular_value": min(
                float(row["minimum_singular_value"]) for row in deformation_rows
            ),
            "deformation_gradient_singular_value__maximum": max(
                float(row["maximum_singular_value"]) for row in deformation_rows
            ),
            "deformation_gradient_anisotropy": max(
                float(row["maximum_anisotropy"]) for row in deformation_rows
            ),
            "deformation_gradient_shear_cosine": max(
                float(row["maximum_shear_cosine"]) for row in deformation_rows
            ),
            "tracked_material_point_velocity_preview_px_per_frame": max(
                velocities, default=0.0
            ),
            "tracked_material_point_acceleration_preview_px_per_frame_squared": max(
                accelerations, default=0.0
            ),
            "tracked_material_point_jerk_preview_px_per_frame_cubed": max(
                jerks, default=0.0
            ),
            "tracked_material_point_count": sum(
                int(history[0].shape[0])
                for history in material_histories.values()
                if history
            ),
            "jacobian_evidence": deformation_rows[0]["jacobian_evidence"],
            "tracked_material_point_extrema_evidence": material_extrema,
        },
        "texture": {
            "source_aligned_region_rgb_psnr_db": min(
                float(row["minimum_region_psnr_db"]) for row in texture_rows
            ),
            "source_aligned_region_rgb_ssim": min(
                float(row["minimum_region_ssim"]) for row in texture_rows
            ),
            "source_aligned_face_rgb_psnr_db": min(
                float(row["face_psnr_db"]) for row in texture_rows
            ),
            "source_aligned_face_rgb_ssim": min(
                float(row["face_ssim"]) for row in texture_rows
            ),
            "motion_compensated_laplacian_variance_ratio": min(
                float(row["minimum_laplacian_variance_ratio"])
                for row in texture_rows
            ),
            "motion_compensated_laplacian_variance_ratio__maximum": max(
                float(row["maximum_laplacian_variance_ratio"])
                for row in texture_rows
            ),
            "mean_source_aligned_rgb_error": max(
                float(row["mean_source_aligned_rgb_error"]) for row in texture_rows
            ),
            "p95_source_aligned_rgb_error": max(
                float(row["p95_source_aligned_rgb_error"]) for row in texture_rows
            ),
            "endpoint_raw_rgba_mismatched_pixels": max(
                int(row["endpoint_raw_rgba_mismatched_pixels"])
                for row in texture_rows
            ),
            "endpoint_registered_rgba_mismatched_pixels": max(
                int(row["endpoint_registered_rgba_mismatched_pixels"])
                for row in texture_rows
            ),
        },
    }


def _empty_delivery_measurements() -> dict[str, Any]:
    return {
        "width": None,
        "height": None,
        "fps": None,
        "encoded_frame_count": None,
        "decoded_frame_count": None,
        "codec": None,
        "pixel_format": None,
        "stream_count": None,
        "video_stream_count": None,
        "audio_stream_count": None,
        "r_frame_rate": None,
        "avg_frame_rate": None,
        "stream_duration_rational": None,
        "container_duration_error_seconds": None,
        "full_decode": False,
        "per_frame_subject_roi_psnr_db": None,
        "per_frame_subject_roi_ssim": None,
        "decoded_face_crop_psnr_db": None,
        "decoded_face_crop_ssim": None,
        "decoded_laplacian_variance_ratio": None,
        "decoded_laplacian_variance_ratio__maximum": None,
        "decoded_first_last_subject_roi_psnr_db": None,
        "decoded_review_frame_count": None,
        "contact_sheet_from_decoded_frames": False,
        "identity_strip_from_decoded_frames": False,
        "seam_sheet_from_decoded_frames": False,
        "video_file": False,
        "report_file": False,
    }


def _run_textured_preflight(
    contract: dict[str, Any],
    *,
    keep_delivery_cache: bool,
    progress: Any | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    _validate_contract(contract)
    _verify_external_evidence(contract)
    phase30_contract, phase31_contract, patches, source, environment = _prepare_dependencies(
        contract
    )
    _assert_locked_frame_inputs(contract, patches, source, environment)
    reference_registered, _, _ = _registered_character(source, phase31_contract)
    frame_rows: list[dict[str, Any]] = []
    material_histories: dict[str, list[np.ndarray]] = {
        identifier: [] for identifier in REGION_IDS
    }
    cache: dict[str, Any] | None = None
    if keep_delivery_cache:
        cache = {
            "beauty_frames": [],
            "subject_masks_output": [],
            "face_boxes_source": [],
            "review_metadata": {},
            "all_seam_pair_boxes_source": {},
        }
    review_frames = set(int(row) for row in contract["delivery"]["review_frames"])
    for frame_number in range(
        int(contract["timing"]["frame_start"]),
        int(contract["timing"]["frame_end"]) + 1,
    ):
        rendered = render_textured_mechanics_frame(
            contract,
            patches,
            frame_number,
            phase31_contract=phase31_contract,
            source_reconstruction=source,
            environment_rgb=environment,
            reference_registered=reference_registered,
            _prepared_dependencies_verified=True,
        )
        try:
            frame_rows.append(
                {
                    "frame": frame_number,
                    "geometry": rendered.geometry_metrics,
                    "texture": rendered.texture_metrics,
                    "ownership": rendered.seam_metrics,
                    "deformation": rendered.deformation_metrics,
                    "reference_beauty_rgb_sha256": hashlib.sha256(
                        rendered.beauty_rgb.tobytes()
                    ).hexdigest(),
                }
            )
            for identifier in REGION_IDS:
                material_histories[identifier].append(
                    rendered.material_points_preview[identifier].copy()
                )
            if cache is not None:
                metadata = _frame_review_metadata(rendered)
                cache["beauty_frames"].append(rendered.beauty_rgb.copy())
                cache["subject_masks_output"].append(
                    cv2.resize(
                        metadata["subject_mask_source"].astype(np.uint8),
                        OUTPUT_SIZE,
                        interpolation=cv2.INTER_NEAREST,
                    )
                    > 0
                )
                cache["face_boxes_source"].append(metadata["face_box_source"])
                cache["all_seam_pair_boxes_source"][frame_number] = metadata[
                    "seam_pair_boxes_source"
                ]
                if frame_number in review_frames:
                    cache["review_metadata"][frame_number] = {
                        "face_box_source": metadata["face_box_source"],
                        "seam_boxes_source": metadata["seam_boxes_source"],
                    }
            if progress is not None:
                progress(frame_number, int(contract["timing"]["frame_count"]))
        finally:
            rendered.close()
    measurements = _aggregate_frame_measurements(frame_rows, material_histories)
    if cache is not None:
        cache["seam_pair_argmax_evidence"] = measurements["ownership"][
            "seam_pair_argmax_evidence"
        ]
    measurements["delivery"] = _empty_delivery_measurements()
    gate_results = _gate_results(contract, measurements)
    preflight_results = [
        row for row in gate_results if not row["id"].startswith("delivery.")
    ]
    preflight_passed = bool(preflight_results) and all(
        bool(row["passed"]) for row in preflight_results
    )
    report = {
        "contract_id": contract["contract_id"],
        "proof": {
            "type": contract["proof_type"],
            "delivery_attempt_version": contract["delivery_attempt_version"],
            "frame_count": len(frame_rows),
            "fps": int(contract["timing"]["fps"]),
            "provenance": _phase32_provenance(contract),
            "frames": frame_rows,
        },
        "dependencies": measurements["dependencies"],
        "geometry": measurements["geometry"],
        "premultiplication": measurements["premultiplication"],
        "ownership": measurements["ownership"],
        "deformation": measurements["deformation"],
        "texture": measurements["texture"],
        "delivery": {
            "status": "not_evaluated",
            **measurements["delivery"],
        },
        "gate_results": gate_results,
        "preflight_passed": preflight_passed,
        "machine_passed": False,
        "audience_quality": {
            "status": "machine_preflight_only_not_audience_approval",
            "human_full_size_review_required": True,
            "next_required_proof": contract["promotion_rule"]["next_if_passed"],
        },
        "cash_cost": 0,
        "paid_runtime_dependency": False,
    }
    return report, cache


def evaluate_reconstruction_locked_textured_mechanics(
    contract: dict[str, Any], require_delivery: bool = False
) -> dict[str, Any]:
    """Evaluate every in-memory Phase 32 frame without encoding by default."""
    if require_delivery:
        raise ReconstructionLockedTexturedMechanicsError(
            "delivery evaluation is transactional; use render_reconstruction_locked_textured_mechanics"
        )
    report, _ = _run_textured_preflight(
        contract, keep_delivery_cache=False
    )
    return report


def _encode_h264_once(
    frames: list[np.ndarray],
    output_path: Path,
    ffmpeg: str | Path,
    contract: dict[str, Any],
) -> None:
    if output_path.exists():
        raise ReconstructionLockedTexturedMechanicsError(
            f"refusing to overwrite Phase32 video: {output_path}"
        )
    encoding = contract["delivery"]["encoding"]
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s:v",
        f"{OUTPUT_SIZE[0]}x{OUTPUT_SIZE[1]}",
        "-r",
        "30",
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        str(encoding["implementation"]),
        "-preset",
        str(encoding["preset"]),
        "-tune",
        str(encoding["tune"]),
        "-crf",
        str(encoding["crf"]),
        "-g",
        str(encoding["gop"]),
        "-keyint_min",
        str(encoding["gop"]),
        "-bf",
        str(encoding["b_frames"]),
        "-pix_fmt",
        "yuv420p",
        "-video_track_timescale",
        str(encoding["video_track_timescale"]),
        "-n",
        str(output_path),
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None
    try:
        for frame in frames:
            if frame.shape != (OUTPUT_SIZE[1], OUTPUT_SIZE[0], 3) or frame.dtype != np.uint8:
                process.kill()
                raise ReconstructionLockedTexturedMechanicsError(
                    "Phase32 encoder received a non-RGB24 1920x1080 frame"
                )
            process.stdin.write(np.ascontiguousarray(frame).tobytes())
    except Exception:
        process.kill()
        process.wait()
        raise
    finally:
        if not process.stdin.closed:
            process.stdin.close()
    assert process.stderr is not None
    stderr = process.stderr.read().decode("utf-8", errors="replace")
    return_code = process.wait()
    if return_code != 0:
        raise ReconstructionLockedTexturedMechanicsError(
            f"single Phase32 H.264 encode failed ({return_code}): {stderr[-2000:]}"
        )


def _probe_video(video_path: Path, ffprobe: str | Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            "stream=index,codec_type,codec_name,pix_fmt,width,height,r_frame_rate,avg_frame_rate,nb_read_frames,duration:format=duration",
            "-of",
            "json",
            str(video_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ReconstructionLockedTexturedMechanicsError(
            f"Phase32 ffprobe failed: {completed.stderr[-2000:]}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ReconstructionLockedTexturedMechanicsError(
            "Phase32 ffprobe did not return JSON"
        ) from error


def _read_exact(stream: Any, byte_count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = byte_count
    while remaining:
        value = stream.read(remaining)
        if not value:
            break
        chunks.append(value)
        remaining -= len(value)
    return b"".join(chunks)


def _masked_psnr(first: np.ndarray, second: np.ndarray, mask: np.ndarray) -> float:
    return _vector_psnr(first[mask], second[mask])


def _masked_ssim(first: np.ndarray, second: np.ndarray, mask: np.ndarray) -> float:
    x0, y0, x1, y1 = _mask_bbox(mask, padding=6)
    return _masked_spatial_ssim(
        first[y0:y1, x0:x1],
        second[y0:y1, x0:x1],
        mask[y0:y1, x0:x1],
    )


def _source_box_to_output(
    box: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    scale_x = OUTPUT_SIZE[0] / SOURCE_SIZE[0]
    scale_y = OUTPUT_SIZE[1] / SOURCE_SIZE[1]
    x0, y0, x1, y1 = box
    return (
        max(0, int(math.floor(x0 * scale_x))),
        max(0, int(math.floor(y0 * scale_y))),
        min(OUTPUT_SIZE[0], int(math.ceil(x1 * scale_x))),
        min(OUTPUT_SIZE[1], int(math.ceil(y1 * scale_y))),
    )


def _decode_and_audit(
    video_path: Path,
    ffmpeg: str | Path,
    cache: dict[str, Any],
    contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[int, np.ndarray]]:
    process = subprocess.Popen(
        [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    frame_bytes = OUTPUT_SIZE[0] * OUTPUT_SIZE[1] * 3
    decoded_hashes: list[dict[str, Any]] = []
    subject_psnr: list[float] = []
    subject_ssim: list[float] = []
    face_psnr: list[float] = []
    face_ssim: list[float] = []
    laplacian_ratios: list[float] = []
    review_numbers = set(int(row) for row in contract["delivery"]["review_frames"])
    seam_argmax_numbers = {
        int(row["frame"])
        for row in cache.get("seam_pair_argmax_evidence", {}).values()
        if row.get("frame") is not None
    }
    retained_numbers = review_numbers | seam_argmax_numbers | {1}
    review_decoded: dict[int, np.ndarray] = {}
    decoded_count = 0
    for index, reference in enumerate(cache["beauty_frames"]):
        payload = _read_exact(process.stdout, frame_bytes)
        if len(payload) != frame_bytes:
            break
        decoded_count += 1
        frame_number = index + 1
        decoded = np.frombuffer(payload, dtype=np.uint8).reshape(
            OUTPUT_SIZE[1], OUTPUT_SIZE[0], 3
        ).copy()
        subject_mask = cache["subject_masks_output"][index]
        subject_psnr.append(_masked_psnr(reference, decoded, subject_mask))
        subject_ssim.append(_masked_ssim(reference, decoded, subject_mask))
        face_box = _source_box_to_output(cache["face_boxes_source"][index])
        face_mask = np.zeros(subject_mask.shape, dtype=bool)
        x0, y0, x1, y1 = face_box
        face_mask[y0:y1, x0:x1] = True
        face_mask &= subject_mask
        face_psnr.append(_masked_psnr(reference, decoded, face_mask))
        face_ssim.append(_masked_ssim(reference, decoded, face_mask))
        reference_gray = cv2.cvtColor(reference, cv2.COLOR_RGB2GRAY)
        decoded_gray = cv2.cvtColor(decoded, cv2.COLOR_RGB2GRAY)
        reference_variance = float(
            np.var(cv2.Laplacian(reference_gray, cv2.CV_32F)[subject_mask])
        )
        decoded_variance = float(
            np.var(cv2.Laplacian(decoded_gray, cv2.CV_32F)[subject_mask])
        )
        laplacian_ratios.append(decoded_variance / max(reference_variance, 1e-6))
        decoded_hashes.append(
            {
                "frame": frame_number,
                "rgb_sha256": hashlib.sha256(payload).hexdigest(),
                "subject_roi_psnr_db": subject_psnr[-1],
                "subject_roi_ssim": subject_ssim[-1],
                "face_crop_psnr_db": face_psnr[-1],
                "face_crop_ssim": face_ssim[-1],
                "laplacian_variance_ratio": laplacian_ratios[-1],
            }
        )
        if frame_number in retained_numbers:
            review_decoded[frame_number] = decoded
    extra = process.stdout.read(1)
    assert process.stderr is not None
    stderr = process.stderr.read().decode("utf-8", errors="replace")
    return_code = process.wait()
    full_decode = (
        return_code == 0
        and decoded_count == int(contract["delivery"]["frame_count"])
        and extra == b""
    )
    if return_code != 0:
        raise ReconstructionLockedTexturedMechanicsError(
            f"Phase32 full decode failed ({return_code}): {stderr[-2000:]}"
        )
    first = review_decoded.get(1)
    last = review_decoded.get(49)
    if first is None or last is None:
        first_last_psnr = 0.0
    else:
        endpoint_mask = cache["subject_masks_output"][0] | cache["subject_masks_output"][-1]
        first_last_psnr = _masked_psnr(first, last, endpoint_mask)
    return (
        {
            "decoded_frame_count": decoded_count,
            "full_decode": full_decode,
            "per_frame_subject_roi_psnr_db": min(subject_psnr, default=0.0),
            "per_frame_subject_roi_ssim": min(subject_ssim, default=0.0),
            "decoded_face_crop_psnr_db": min(face_psnr, default=0.0),
            "decoded_face_crop_ssim": min(face_ssim, default=0.0),
            "decoded_laplacian_variance_ratio": min(laplacian_ratios, default=0.0),
            "decoded_laplacian_variance_ratio__maximum": max(
                laplacian_ratios, default=0.0
            ),
            "decoded_first_last_subject_roi_psnr_db": first_last_psnr,
            "decoded_frames": decoded_hashes,
        },
        review_decoded,
    )


def _fit_crop_to_tile(
    frame: np.ndarray,
    box: tuple[int, int, int, int],
    tile_size: tuple[int, int],
) -> np.ndarray:
    x0, y0, x1, y1 = box
    crop = frame[y0:y1, x0:x1]
    if not crop.size:
        crop = np.zeros((1, 1, 3), dtype=np.uint8)
    tile_width, tile_height = tile_size
    scale = min(tile_width / crop.shape[1], tile_height / crop.shape[0])
    resized_width = max(1, int(round(crop.shape[1] * scale)))
    resized_height = max(1, int(round(crop.shape[0] * scale)))
    resized = cv2.resize(
        crop, (resized_width, resized_height), interpolation=cv2.INTER_LANCZOS4
    )
    tile = np.full((tile_height, tile_width, 3), 18, dtype=np.uint8)
    offset_x = (tile_width - resized_width) // 2
    offset_y = (tile_height - resized_height) // 2
    tile[offset_y : offset_y + resized_height, offset_x : offset_x + resized_width] = resized
    return tile


def _write_decoded_review_artifacts(
    stage: Path,
    decoded: dict[int, np.ndarray],
    cache: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    delivery = contract["delivery"]
    review_frames = [int(row) for row in delivery["review_frames"]]
    if not set(review_frames).issubset(decoded):
        raise ReconstructionLockedTexturedMechanicsError(
            "decoded Phase32 review-frame inventory is incomplete"
        )
    contact = np.zeros((1080, 1920, 3), dtype=np.uint8)
    for index, frame_number in enumerate(review_frames):
        row, column = divmod(index, 3)
        contact[row * 360 : (row + 1) * 360, column * 640 : (column + 1) * 640] = cv2.resize(
            decoded[frame_number], (640, 360), interpolation=cv2.INTER_AREA
        )
    contact_path = stage / delivery["contact_sheet_filename"]
    Image.fromarray(contact, mode="RGB").save(contact_path)

    identity = np.full((256, 256 * len(review_frames), 3), 18, dtype=np.uint8)
    for index, frame_number in enumerate(review_frames):
        source_box = cache["review_metadata"][frame_number]["face_box_source"]
        tile = _fit_crop_to_tile(
            decoded[frame_number], _source_box_to_output(source_box), (256, 256)
        )
        identity[:, index * 256 : (index + 1) * 256] = tile
    identity_path = stage / delivery["identity_strip_filename"]
    Image.fromarray(identity, mode="RGB").save(identity_path)

    seam_evidence = cache["seam_pair_argmax_evidence"]
    seam_pairs = list(seam_evidence)
    seam = np.full((180 * len(seam_pairs), 640, 3), 18, dtype=np.uint8)
    seam_frames: dict[str, list[int]] = {}
    for row, pair in enumerate(seam_pairs):
        argmax_frame = int(seam_evidence[pair]["frame"])
        seam_frames[pair] = [1, argmax_frame]
        for column, frame_number in enumerate((1, argmax_frame)):
            source_box = cache["all_seam_pair_boxes_source"][frame_number][pair]
            tile = _fit_crop_to_tile(
                decoded[frame_number], _source_box_to_output(source_box), (320, 180)
            )
            seam[
                row * 180 : (row + 1) * 180,
                column * 320 : (column + 1) * 320,
            ] = tile
    seam_image = Image.fromarray(seam, mode="RGB")
    draw = ImageDraw.Draw(seam_image)
    for row, pair in enumerate(seam_pairs):
        argmax_frame = seam_frames[pair][1]
        draw.rectangle((0, row * 180, 640, row * 180 + 21), fill=(18, 18, 18))
        draw.text((5, row * 180 + 4), f"{pair} | rest f1 | argmax f{argmax_frame}", fill=(245, 245, 245))
    seam_path = stage / delivery["seam_detail_sheet_filename"]
    seam_image.save(seam_path)
    seam_image.close()
    return {
        "contact_sheet": {
            "filename": contact_path.name,
            "sha256": _sha256(contact_path),
            "source": "fully_decoded_mp4_frames",
            "frames": review_frames,
        },
        "identity_strip": {
            "filename": identity_path.name,
            "sha256": _sha256(identity_path),
            "source": "fully_decoded_mp4_frames",
            "frames": review_frames,
        },
        "seam_detail_sheet": {
            "filename": seam_path.name,
            "sha256": _sha256(seam_path),
            "source": "fully_decoded_mp4_frames",
            "frames_by_pair": seam_frames,
            "selection": "rest_and_each_required_pair_candidate_disagreement_argmax",
        },
    }


def _probe_measurements(
    probe: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any]:
    streams = list(probe.get("streams", []))
    video_streams = [row for row in streams if row.get("codec_type") == "video"]
    audio_streams = [row for row in streams if row.get("codec_type") == "audio"]
    video = video_streams[0] if len(video_streams) == 1 else {}
    encoded_frames = int(video.get("nb_read_frames", 0) or 0)
    rate_text = str(video.get("r_frame_rate", "0/1"))
    try:
        rate = Fraction(rate_text)
    except (ValueError, ZeroDivisionError):
        rate = Fraction(0, 1)
    duration = float(probe.get("format", {}).get("duration", 0.0) or 0.0)
    expected_duration = Fraction(
        int(contract["delivery"]["frame_count"]), int(contract["delivery"]["fps"])
    )
    return {
        "width": int(video.get("width", 0) or 0),
        "height": int(video.get("height", 0) or 0),
        "fps": int(rate) if rate.denominator == 1 else float(rate),
        "encoded_frame_count": encoded_frames,
        "codec": video.get("codec_name"),
        "pixel_format": video.get("pix_fmt"),
        "stream_count": len(streams),
        "video_stream_count": len(video_streams),
        "audio_stream_count": len(audio_streams),
        "r_frame_rate": rate_text,
        "avg_frame_rate": str(video.get("avg_frame_rate", "")),
        "stream_duration_rational": (
            f"{expected_duration.numerator}/{expected_duration.denominator}"
            if encoded_frames == expected_duration.numerator
            and rate == expected_duration.denominator
            else "invalid"
        ),
        "container_duration_error_seconds": abs(duration - float(expected_duration)),
        "probe": probe,
    }


def _write_report_atomic(path: Path, report: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    parsed = json.loads(temporary.read_text(encoding="utf-8"))
    if parsed.get("contract_id") != report.get("contract_id"):
        raise ReconstructionLockedTexturedMechanicsError(
            "Phase32 report round-trip validation failed"
        )
    os.replace(temporary, path)


def _resolve_executable(value: str | Path, label: str) -> str:
    text = str(value)
    found = shutil.which(text)
    if found:
        return found
    path = Path(text)
    if path.is_file():
        return str(path.resolve())
    raise ReconstructionLockedTexturedMechanicsError(f"{label} executable is unavailable: {text}")


def render_reconstruction_locked_textured_mechanics(
    contract: dict[str, Any],
    *,
    ffmpeg: str | Path = "ffmpeg",
    ffprobe: str | Path = "ffprobe",
    progress: Any | None = None,
) -> dict[str, Any]:
    """Preflight 49 frames, encode once, fully decode, audit, and publish atomically."""
    _validate_contract(contract)
    ffmpeg_path = _resolve_executable(ffmpeg, "FFmpeg")
    ffprobe_path = _resolve_executable(ffprobe, "FFprobe")
    output_directory = (REPO_ROOT / contract["delivery"]["output_directory"]).resolve()
    if output_directory.exists():
        raise ReconstructionLockedTexturedMechanicsError(
            f"Phase32 output directory already exists: {output_directory}"
        )
    rejected_directory = output_directory.with_name(output_directory.name + "-rejected")
    if rejected_directory.exists():
        raise ReconstructionLockedTexturedMechanicsError(
            f"Phase32 rejected-evidence directory already exists: {rejected_directory}"
        )
    report, cache = _run_textured_preflight(
        contract,
        keep_delivery_cache=True,
        progress=progress,
    )
    assert cache is not None
    if not report["preflight_passed"]:
        failed = [
            {
                "id": row["id"],
                "measured": row["measured"],
                "operator": row["operator"],
                "threshold": row["threshold"],
            }
            for row in report["gate_results"]
            if not row["passed"] and not row["id"].startswith("delivery.")
        ]
        raise ReconstructionLockedTexturedMechanicsError(
            f"Phase32 preflight failed before encoding: {failed}"
        )
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(
            prefix=f".{output_directory.name}.staging-",
            dir=output_directory.parent,
        )
    )
    preserve_rejected = False
    try:
        video_path = stage / contract["delivery"]["video_filename"]
        _encode_h264_once(
            cache["beauty_frames"], video_path, ffmpeg_path, contract
        )
        probe = _probe_video(video_path, ffprobe_path)
        probe_metrics = _probe_measurements(probe, contract)
        decode_metrics, decoded_review = _decode_and_audit(
            video_path, ffmpeg_path, cache, contract
        )
        artifacts = _write_decoded_review_artifacts(
            stage, decoded_review, cache, contract
        )
        delivery_measurements = {
            **_empty_delivery_measurements(),
            **probe_metrics,
            **decode_metrics,
            "decoded_review_frame_count": sum(
                1
                for frame_number in contract["delivery"]["review_frames"]
                if int(frame_number) in decoded_review
            ),
            "contact_sheet_from_decoded_frames": True,
            "identity_strip_from_decoded_frames": True,
            "seam_sheet_from_decoded_frames": True,
            "video_file": video_path.is_file(),
            "report_file": True,
        }
        report["delivery"] = {
            "status": "evaluated",
            **delivery_measurements,
            "encoding_process_count": 1,
            "video": {
                "filename": video_path.name,
                "sha256": _sha256(video_path),
            },
            "review_artifacts": artifacts,
        }
        measurements = {
            section: report[section]
            for section in (
                "dependencies",
                "geometry",
                "premultiplication",
                "ownership",
                "deformation",
                "texture",
            )
        }
        measurements["delivery"] = delivery_measurements
        report["gate_results"] = _gate_results(contract, measurements)
        report["machine_passed"] = all(
            bool(row["passed"]) for row in report["gate_results"]
        )
        report["audience_quality"] = {
            "status": (
                "machine_delivery_passed_human_review_pending"
                if report["machine_passed"]
                else "decoded_delivery_rejected"
            ),
            "human_full_size_review_required": True,
            "next_required_proof": contract["promotion_rule"]["next_if_passed"],
        }
        required_top = set(contract["report_schema"]["required_top_level_fields"])
        if not required_top.issubset(report):
            raise ReconstructionLockedTexturedMechanicsError(
                f"Phase32 report is missing top-level fields: {sorted(required_top - set(report))}"
            )
        if len(report["gate_results"]) != len(_flatten_quality_gates(contract)):
            raise ReconstructionLockedTexturedMechanicsError(
                "Phase32 report gate inventory is incomplete"
            )
        report_path = stage / contract["delivery"]["report_filename"]
        _write_report_atomic(report_path, report)
        if not report["machine_passed"]:
            preserve_rejected = True
            os.replace(stage, rejected_directory)
            raise ReconstructionLockedTexturedMechanicsError(
                f"Phase32 decoded delivery failed and was preserved at {rejected_directory}"
            )
        os.replace(stage, output_directory)
        report["delivery"]["published_output_directory"] = str(output_directory)
        return report
    finally:
        if stage.exists() and not preserve_rejected:
            shutil.rmtree(stage)
