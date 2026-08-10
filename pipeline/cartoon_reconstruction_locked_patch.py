"""Phase 30 accepted-pixel reconstruction lock for June Oxley.

This module deliberately does not animate or encode media.  It proves that
native, overlapping patches extracted from the accepted POSE_100 foreground
can reconstruct both the raw plate and its pinned Phase 27 registration
exactly.  Rest composition uses one hard owner per source pixel; extraction
overlap is retained only for a later motion proof.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline.cartoon_pose_layers import registered_pose_layer


REPO_ROOT = Path(__file__).resolve().parents[1]
_PINNED_QUALITY_GATES_SHA256 = "c01226f871abd2c47ddd773e0005c4fbeaf9a878e605ad81e2d2e00eecb17e72"
_PINNED_REPORT_SCHEMA_SHA256 = "fac730087022538d5f250543a965e39be5aa97bdfc73cb152a626b71d78bae1c"


class ReconstructionLockError(ValueError):
    """Raised whenever the reconstruction proof cannot remain fail-closed."""


@dataclass(frozen=True)
class LockedPatch:
    identifier: str
    kind: str
    bbox_xyxy: tuple[int, int, int, int]
    rgba: np.ndarray
    source_mask: np.ndarray
    semantic_support_mask: np.ndarray
    semantic_owner_mask: np.ndarray
    rest_owner_mask: np.ndarray
    source_coordinate_hash: str

    def __getitem__(self, key: str) -> Any:
        aliases = {
            "id": self.identifier,
            "source_bbox_xyxy_exclusive": self.bbox_xyxy,
        }
        if key in aliases:
            return aliases[key]
        return getattr(self, key)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _locked_path(reference: dict[str, Any], label: str) -> Path:
    path = (REPO_ROOT / str(reference.get("path", ""))).resolve()
    if not path.is_file():
        raise ReconstructionLockError(f"{label} is missing: {path}")
    expected = str(reference.get("sha256", ""))
    actual = _sha256(path)
    if not expected or actual != expected:
        raise ReconstructionLockError(f"{label} SHA-256 mismatch: {actual} != {expected}")
    return path


def _bbox(mask: np.ndarray) -> list[int]:
    ys, xs = np.where(mask)
    if not len(xs):
        return [0, 0, 0, 0]
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def _components(mask: np.ndarray) -> int:
    count, _ = cv2.connectedComponents(np.asarray(mask, dtype=np.uint8), connectivity=8)
    return int(count - 1)


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ReconstructionLockError(f"{label} mismatch: {actual!r} != {expected!r}")


def _canonical_json_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_contract_invariants(contract: dict[str, Any]) -> None:
    """Validate non-negotiable policy even for a post-load mutable dict."""
    _require_equal(contract.get("contract_version"), 1, "contract version")
    _require_equal(contract.get("contract_id"), "june_oxley_reconstruction_locked_patch_v1", "contract id")
    _require_equal(contract.get("phase"), "phase30_reconstruction_lock", "phase")
    _require_equal(contract.get("cash_cost"), 0, "cash cost")
    _require_equal(contract.get("paid_runtime_dependency"), False, "paid dependency")
    _require_equal(contract.get("network_runtime_required"), False, "network dependency")

    extraction = contract.get("patch_extraction", {})
    _require_equal(
        extraction.get("algorithm_id"),
        "native_rgba_connected_region_polygons_with_hard_owner_partition_v1",
        "extraction algorithm",
    )
    _require_equal(extraction.get("deterministic"), True, "deterministic extraction")
    _require_equal(extraction.get("coordinate_space"), "gs030_source_pixels", "extraction coordinate space")
    _require_equal(extraction.get("pixel_sampling"), "integer_coordinate_direct_copy", "pixel sampling")
    _require_equal(extraction.get("source_alpha_threshold_exclusive"), 8, "semantic alpha threshold")
    _require_equal(extraction.get("pixel_preservation_alpha_threshold_exclusive"), 0, "preservation alpha threshold")
    _require_equal(extraction.get("mask_connectivity"), 8, "mask connectivity")
    _require_equal(
        extraction.get("low_alpha_fringe_rule"),
        "stable_8_connected_geodesic_expand_from_semantic_owners_into_native_pixels_where_0_lt_alpha_lte_8",
        "low-alpha fringe rule",
    )
    for key in (
        "generated_atlas_allowed", "atlas_repack_allowed", "resize_allowed", "resampling_allowed",
        "rotation_allowed", "warp_allowed", "color_transform_allowed", "alpha_reestimation_allowed",
        "inpainting_allowed",
    ):
        _require_equal(extraction.get(key), False, key)
    _require_equal(extraction.get("fallback_policy"), "raise", "extraction fallback")

    ownership = extraction.get("ownership", {})
    _require_equal(
        ownership.get("method"),
        "alpha_clipped_declared_region_polygons_then_stable_priority_first_claim",
        "ownership method",
    )
    _require_equal(
        ownership.get("eligibility_rule"),
        "source_alpha_greater_than_8_and_cv2_fillPoly_inclusive_integer_polygon_raster_is_nonzero",
        "polygon raster rule",
    )
    _require_equal(ownership.get("tie_break_rule"), "first_patch_id_in_stable_priority_order", "ownership tie break")
    _require_equal(ownership.get("unmatched_semantic_foreground_rule"), "raise", "unmatched semantic rule")
    _require_equal(
        ownership.get("low_alpha_fringe_assignment"),
        "stable_priority_geodesic_expansion_from_semantic_owner_masks",
        "fringe ownership",
    )
    _require_equal(ownership.get("transparent_pixel_rule"), "unowned", "transparent ownership")
    _require_equal(ownership.get("every_foreground_pixel_has_exactly_one_semantic_owner"), True, "foreground ownership")

    rest = contract.get("rest_reconstruction", {})
    _require_equal(rest.get("method"), "hard_source_pixel_ownership_direct_copy", "rest method")
    _require_equal(rest.get("owner_masks_form_exact_partition"), True, "hard owner partition")
    _require_equal(rest.get("alpha_over_between_overlapping_patches"), False, "overlap alpha-over policy")
    _require_equal(rest.get("premultiplied_blend_between_overlapping_patches"), False, "overlap blend policy")
    _require_equal(rest.get("identity_transform_only"), True, "raw rest transform")

    patch_rows = extraction.get("patches", [])
    patch_ids = [str(row.get("id")) for row in patch_rows]
    topology = contract.get("quality_gates", {}).get("topology", {})
    _require_equal(len(patch_ids), topology.get("required_patch_count"), "regional patch count")
    if len(patch_ids) != len(set(patch_ids)):
        raise ReconstructionLockError("patch identifiers must be unique")
    _require_equal(set(ownership.get("stable_priority_order", [])), set(patch_ids), "ownership inventory")
    _require_equal(rest.get("rest_owner_priority"), ownership.get("stable_priority_order"), "rest-owner priority")
    forbidden = set(topology.get("forbidden_independent_limb_patch_ids", []))
    if forbidden.intersection(patch_ids):
        raise ReconstructionLockError("forbidden split-limb patch identifiers are present")
    for specification in patch_rows:
        polygon = specification.get("polygon_xy")
        if not isinstance(polygon, list) or len(polygon) < 3:
            raise ReconstructionLockError(f"patch {specification.get('id')} has no valid region polygon")
        if any(
            not isinstance(point, list)
            or len(point) != 2
            or any(not isinstance(coordinate, int) for coordinate in point)
            for point in polygon
        ):
            raise ReconstructionLockError(f"patch {specification.get('id')} polygon is not integer xy")
        _require_equal(specification.get("required"), True, f"{specification.get('id')} required")
    for identifier in topology.get("required_atomic_patch_ids", []):
        matches = [row for row in patch_rows if row.get("id") == identifier]
        if len(matches) != 1:
            raise ReconstructionLockError(f"required atomic patch {identifier} is missing")
        _require_equal(matches[0].get("must_remain_atomic"), True, f"{identifier} atomic declaration")

    overlap = extraction.get("overlap", {})
    _require_equal(overlap.get("method"), "native_source_alpha_clipped_declared_region_polygons", "overlap method")
    _require_equal(overlap.get("overlap_pixels_are_double_composited_at_rest"), False, "overlap rest policy")
    pair_ids = [identifier for pair in overlap.get("required_adjacent_pairs", []) for identifier in pair]
    if not pair_ids or not set(pair_ids).issubset(patch_ids):
        raise ReconstructionLockError("required overlap pair inventory is invalid")

    registered = contract.get("registered_rest_equivalence", {})
    _require_equal(registered.get("required"), True, "registered equivalence requirement")
    _require_equal(registered.get("fallback_policy"), "raise", "registered fallback")
    _require_equal(registered.get("reference_operation", {}).get("function"), "registered_pose_layer", "registered operation")
    failure = contract.get("failure_policy", {})
    _require_equal(failure.get("mode"), "fail_closed", "failure policy")
    _require_equal(failure.get("fallback_allowed"), False, "fallback policy")
    _require_equal(failure.get("machine_pass_rule"), "true_only_when_every_gate_result_passes", "machine-pass rule")
    _require_equal(
        contract.get("promotion_rule", {}).get("this_contract_authorizes_media_render"),
        False,
        "media render authorization",
    )

    gate_hash = _canonical_json_hash(contract.get("quality_gates", {}))
    _require_equal(gate_hash, _PINNED_QUALITY_GATES_SHA256, "complete quality-gate inventory and values")
    schema_hash = _canonical_json_hash(contract.get("report_schema", {}))
    _require_equal(schema_hash, _PINNED_REPORT_SCHEMA_SHA256, "complete report schema")


def load_reconstruction_contract(path: str | Path) -> dict[str, Any]:
    contract_path = Path(path).resolve()
    if not contract_path.is_file():
        raise ReconstructionLockError(f"reconstruction contract is missing: {contract_path}")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    _validate_contract_invariants(contract)
    _require_equal(contract.get("contract_version"), 1, "contract version")
    _require_equal(contract.get("contract_id"), "june_oxley_reconstruction_locked_patch_v1", "contract id")
    _require_equal(contract.get("phase"), "phase30_reconstruction_lock", "phase")
    _require_equal(contract.get("cash_cost"), 0, "cash cost")
    _require_equal(contract.get("paid_runtime_dependency"), False, "paid dependency")
    _require_equal(contract.get("network_runtime_required"), False, "network dependency")

    source_lock = contract["source_lock"]
    _require_equal(source_lock.get("source_count"), 1, "RGBA source count")
    source_reference = source_lock["sole_rgba_source"]
    _require_equal(source_reference.get("sole_rgba_source"), True, "sole-source declaration")
    _require_equal(source_reference.get("pose_id"), "POSE_100_STANDING", "source pose")
    source_path = _locked_path(source_reference, "accepted pose-100 foreground")
    control_path = _locked_path(source_lock["control_contract"], "GS030 control")
    metadata_path = _locked_path(source_lock["accepted_source_metadata"], "accepted-source metadata")

    with Image.open(source_path) as source_image:
        _require_equal(source_image.mode, source_reference["mode"], "source mode")
        _require_equal(source_image.size, (source_reference["width"], source_reference["height"]), "source dimensions")
        source_rgba = np.asarray(source_image, dtype=np.uint8)
    observations = contract["source_observations"]
    preservation = source_rgba[:, :, 3] > int(contract["patch_extraction"]["pixel_preservation_alpha_threshold_exclusive"])
    semantic = source_rgba[:, :, 3] > int(contract["patch_extraction"]["source_alpha_threshold_exclusive"])
    _require_equal(int(np.count_nonzero(preservation)), observations["expected_nontransparent_pixels"], "source nontransparent pixels")
    _require_equal(_bbox(preservation), observations["expected_nontransparent_bbox_xyxy_half_open"], "source nontransparent bbox")
    _require_equal(int(np.count_nonzero(semantic)), observations["expected_semantic_foreground_pixels"], "semantic foreground pixels")
    _require_equal(_bbox(semantic), observations["expected_semantic_foreground_bbox_xyxy_half_open"], "semantic bbox")
    _require_equal(_components(semantic), observations["expected_semantic_foreground_components_8_connected"], "semantic connectivity")
    if np.any(source_rgba[:, :, :3][source_rgba[:, :, 3] == 0]):
        raise ReconstructionLockError("transparent source pixels contain nonzero RGB")

    control = json.loads(control_path.read_text(encoding="utf-8"))
    pose_reference = source_lock["control_contract"]
    poses = [row for row in control.get("poses", []) if row.get("id") == pose_reference["required_pose_id"]]
    if len(poses) != 1:
        raise ReconstructionLockError("GS030 control must contain exactly one required pose")
    pose = poses[0]
    _require_equal(pose.get("progress"), pose_reference["required_progress"], "pose progress")
    for field in ("path", "sha256", "width", "height", "mode"):
        _require_equal(pose["foreground"].get(field), source_reference.get(field), f"control foreground {field}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    endpoint = metadata["accepted_sources"]["standing_endpoint"]
    for field in ("path", "sha256"):
        _require_equal(endpoint.get(field), source_reference.get(field), f"metadata endpoint {field}")
    _require_equal(endpoint.get("role"), source_lock["accepted_source_metadata"]["required_role"], "metadata endpoint role")
    corrective = [
        row for row in metadata["runtime_asset_pack"]["corrective_sources"]
        if row.get("pose_id") == source_lock["accepted_source_metadata"]["required_corrective_pose_id"]
    ]
    if len(corrective) != 1:
        raise ReconstructionLockError("accepted metadata must contain exactly one pose-100 corrective")
    _require_equal(corrective[0]["landmarks"], contract["source_landmarks"]["points"], "source landmarks")

    extraction = contract["patch_extraction"]
    _require_equal(
        extraction.get("algorithm_id"),
        "native_rgba_connected_region_polygons_with_hard_owner_partition_v1",
        "extraction algorithm",
    )
    _require_equal(extraction.get("deterministic"), True, "deterministic extraction")
    _require_equal(extraction.get("source_alpha_threshold_exclusive"), 8, "semantic alpha threshold")
    _require_equal(extraction.get("pixel_preservation_alpha_threshold_exclusive"), 0, "preservation alpha threshold")
    _require_equal(extraction.get("mask_connectivity"), 8, "mask connectivity")
    _require_equal(
        extraction.get("low_alpha_fringe_rule"),
        "stable_8_connected_geodesic_expand_from_semantic_owners_into_native_pixels_where_0_lt_alpha_lte_8",
        "low-alpha fringe rule",
    )
    forbidden_true = (
        "generated_atlas_allowed", "atlas_repack_allowed", "resize_allowed", "resampling_allowed",
        "rotation_allowed", "warp_allowed", "color_transform_allowed", "alpha_reestimation_allowed",
        "inpainting_allowed",
    )
    if any(extraction.get(key) is not False for key in forbidden_true):
        raise ReconstructionLockError("native-pixel extraction policy was weakened")
    _require_equal(extraction.get("pixel_sampling"), "integer_coordinate_direct_copy", "pixel sampling")
    _require_equal(extraction.get("coordinate_space"), "gs030_source_pixels", "extraction coordinate space")
    _require_equal(extraction.get("fallback_policy"), "raise", "extraction fallback")
    ownership = extraction["ownership"]
    _require_equal(
        ownership.get("method"),
        "alpha_clipped_declared_region_polygons_then_stable_priority_first_claim",
        "ownership method",
    )
    _require_equal(
        ownership.get("eligibility_rule"),
        "source_alpha_greater_than_8_and_cv2_fillPoly_inclusive_integer_polygon_raster_is_nonzero",
        "polygon raster rule",
    )
    _require_equal(ownership.get("tie_break_rule"), "first_patch_id_in_stable_priority_order", "ownership tie break")
    _require_equal(ownership.get("unmatched_semantic_foreground_rule"), "raise", "unmatched semantic rule")
    _require_equal(
        ownership.get("low_alpha_fringe_assignment"),
        "stable_priority_geodesic_expansion_from_semantic_owner_masks",
        "fringe ownership",
    )
    _require_equal(ownership.get("transparent_pixel_rule"), "unowned", "transparent ownership")
    _require_equal(ownership.get("every_foreground_pixel_has_exactly_one_semantic_owner"), True, "foreground ownership")
    overlap = extraction["overlap"]
    _require_equal(overlap.get("method"), "native_source_alpha_clipped_declared_region_polygons", "overlap method")
    _require_equal(overlap.get("overlap_pixels_are_double_composited_at_rest"), False, "overlap rest policy")
    rest = contract["rest_reconstruction"]
    _require_equal(rest.get("method"), "hard_source_pixel_ownership_direct_copy", "rest method")
    _require_equal(rest.get("owner_masks_form_exact_partition"), True, "hard owner partition")
    _require_equal(rest.get("alpha_over_between_overlapping_patches"), False, "overlap alpha-over policy")
    _require_equal(rest.get("premultiplied_blend_between_overlapping_patches"), False, "overlap blend policy")
    _require_equal(rest.get("identity_transform_only"), True, "raw rest transform")
    _require_equal(contract["failure_policy"].get("mode"), "fail_closed", "failure policy")
    _require_equal(contract["failure_policy"].get("fallback_allowed"), False, "fallback policy")

    patch_ids = [str(row["id"]) for row in extraction["patches"]]
    topology = contract["quality_gates"]["topology"]
    if len(patch_ids) != len(set(patch_ids)):
        raise ReconstructionLockError("patch identifiers must be unique")
    _require_equal(len(patch_ids), topology["required_patch_count"], "regional patch count")
    _require_equal(set(ownership["stable_priority_order"]), set(patch_ids), "ownership inventory")
    _require_equal(rest["rest_owner_priority"], ownership["stable_priority_order"], "rest-owner priority")
    lower_id = contract["lower_body_stitched_region"]["patch_id"]
    if lower_id not in patch_ids:
        raise ReconstructionLockError("authoritative lower-garment patch is missing")
    forbidden = set(topology["forbidden_independent_limb_patch_ids"])
    if forbidden.intersection(patch_ids):
        raise ReconstructionLockError("forbidden split-limb patch identifiers are present")
    for specification in extraction["patches"]:
        polygon = specification.get("polygon_xy")
        if not isinstance(polygon, list) or len(polygon) < 3:
            raise ReconstructionLockError(f"patch {specification['id']} has no valid region polygon")
        if any(
            not isinstance(point, list)
            or len(point) != 2
            or any(not isinstance(coordinate, int) for coordinate in point)
            for point in polygon
        ):
            raise ReconstructionLockError(f"patch {specification['id']} polygon is not integer xy")
        if not specification.get("required", False):
            raise ReconstructionLockError(f"patch {specification['id']} was made optional")
    for identifier in topology["required_atomic_patch_ids"]:
        specification = next(row for row in extraction["patches"] if row["id"] == identifier)
        _require_equal(specification.get("must_remain_atomic"), True, f"{identifier} atomic declaration")

    operation = contract["registered_rest_equivalence"]["reference_operation"]
    _locked_path({"path": operation["module_path"], "sha256": operation["module_sha256"]}, "registered-pose operation")
    _require_equal(operation.get("function"), "registered_pose_layer", "registered operation")
    _require_equal(contract["registered_rest_equivalence"].get("fallback_policy"), "raise", "registered fallback")
    _require_equal(pose["source_contacts"], contract["registered_rest_equivalence"]["pinned_pose_contacts"], "registered pose contacts")
    _require_equal(control["contact_registration"], contract["registered_rest_equivalence"]["pinned_registration"], "registered control")
    return contract


def _polygon_mask(shape: tuple[int, int], polygon_xy: list[list[int]]) -> np.ndarray:
    """Rasterize the contract's inclusive integer polygon deterministically."""
    mask = np.zeros(shape, dtype=np.uint8)
    points = np.asarray(polygon_xy, dtype=np.int32)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3:
        raise ReconstructionLockError("region polygon must contain at least three integer xy points")
    cv2.fillPoly(mask, [points], 1, lineType=cv2.LINE_8, shift=0)
    return mask > 0


def _assign_low_alpha_fringe(
    preservation: np.ndarray,
    semantic: np.ndarray,
    semantic_owner_masks: dict[str, np.ndarray],
    priority_order: list[str],
) -> dict[str, np.ndarray]:
    """Assign alpha 1..8 pixels by deterministic 8-connected geodesic growth."""
    rest_owner_masks = {identifier: mask.copy() for identifier, mask in semantic_owner_masks.items()}
    unassigned = preservation & ~semantic
    frontiers = {identifier: mask.copy() for identifier, mask in semantic_owner_masks.items()}
    kernel = np.ones((3, 3), dtype=np.uint8)
    while np.any(unassigned):
        next_frontiers = {identifier: np.zeros_like(unassigned) for identifier in priority_order}
        assigned_this_round = False
        # Every candidate is calculated from the previous distance frontier;
        # sequential claiming inside this loop supplies the stable tie break.
        for identifier in priority_order:
            candidates = (
                cv2.dilate(frontiers[identifier].astype(np.uint8), kernel, iterations=1) > 0
            ) & unassigned
            if np.any(candidates):
                rest_owner_masks[identifier] |= candidates
                next_frontiers[identifier] = candidates
                unassigned &= ~candidates
                assigned_this_round = True
        if not assigned_this_round:
            raise ReconstructionLockError("low-alpha source fringe is not reachable from semantic owners")
        frontiers = next_frontiers
    return rest_owner_masks


def _extract_state(contract: dict[str, Any], source_rgba: np.ndarray) -> tuple[dict[str, LockedPatch], dict[str, Any]]:
    extraction = contract["patch_extraction"]
    height, width = source_rgba.shape[:2]
    semantic = source_rgba[:, :, 3] > int(extraction["source_alpha_threshold_exclusive"])
    preservation = source_rgba[:, :, 3] > int(extraction["pixel_preservation_alpha_threshold_exclusive"])
    specs = {str(row["id"]): row for row in extraction["patches"]}
    order = [str(value) for value in extraction["ownership"]["stable_priority_order"]]
    if set(order) != set(specs):
        raise ReconstructionLockError("stable ownership priority does not match patch inventory")

    polygon_masks: dict[str, np.ndarray] = {}
    semantic_support_masks: dict[str, np.ndarray] = {}
    for identifier in order:
        specification = specs[identifier]
        polygon = _polygon_mask((height, width), specification["polygon_xy"])
        support = polygon & semantic
        polygon_masks[identifier] = polygon
        semantic_support_masks[identifier] = support
        _require_equal(
            int(np.count_nonzero(support)),
            specification["expected_semantic_pixels"],
            f"{identifier} semantic support pixels",
        )
        _require_equal(
            _bbox(support),
            specification["expected_semantic_bbox_xyxy_half_open"],
            f"{identifier} semantic support bbox",
        )
        _require_equal(
            _components(support),
            specification["required_connected_components"],
            f"{identifier} semantic support connectivity",
        )

    owner_index = np.full((height, width), -1, dtype=np.int16)
    for index, identifier in enumerate(order):
        eligible = semantic_support_masks[identifier] & (owner_index < 0)
        owner_index[eligible] = index
    if np.any(semantic & (owner_index < 0)):
        raise ReconstructionLockError("declared region polygons leave semantic foreground unowned")
    semantic_owner_masks = {
        identifier: owner_index == index for index, identifier in enumerate(order)
    }
    lower_contract = contract["lower_body_stitched_region"]
    lower_id = lower_contract["patch_id"]
    _require_equal(
        int(np.count_nonzero(semantic_owner_masks[lower_id])),
        lower_contract["semantic_owner_pixels_expected"],
        "lower-garment semantic owner pixels",
    )
    rest_owner_masks = _assign_low_alpha_fringe(
        preservation, semantic, semantic_owner_masks, order
    )
    # Overlap support remains the actual alpha-clipped polygon; each owner is
    # unioned in so its assigned low-alpha fringe is always extractable.
    source_masks = {
        identifier: (polygon_masks[identifier] & preservation) | rest_owner_masks[identifier]
        for identifier in order
    }
    rest_counts = np.zeros((height, width), dtype=np.uint8)
    for mask in rest_owner_masks.values():
        rest_counts += mask.astype(np.uint8)
    if np.any(rest_counts[preservation] != 1) or np.any(rest_counts[~preservation] != 0):
        raise ReconstructionLockError("rest-owner masks do not form an exact hard partition")

    patches: dict[str, LockedPatch] = {}
    for identifier, specification in specs.items():
        source_mask = source_masks[identifier]
        bbox = _bbox(source_mask)
        if bbox == [0, 0, 0, 0]:
            raise ReconstructionLockError(f"required patch {identifier} is empty")
        x0, y0, x1, y1 = bbox
        local_mask = source_mask[y0:y1, x0:x1]
        local_rgba = source_rgba[y0:y1, x0:x1].copy()
        local_rgba[~local_mask] = 0
        ys, xs = np.where(source_mask)
        coordinates = np.column_stack((xs, ys)).astype("<i4")
        coordinate_hash = hashlib.sha256(coordinates.tobytes() + source_rgba[ys, xs].tobytes()).hexdigest()
        patches[identifier] = LockedPatch(
            identifier=identifier,
            kind=str(specification["kind"]),
            bbox_xyxy=(x0, y0, x1, y1),
            rgba=local_rgba,
            source_mask=source_mask,
            semantic_support_mask=semantic_support_masks[identifier],
            semantic_owner_mask=semantic_owner_masks[identifier],
            rest_owner_mask=rest_owner_masks[identifier],
            source_coordinate_hash=coordinate_hash,
        )
    state = {
        "preservation": preservation,
        "semantic": semantic,
        "owner_index": owner_index,
        "semantic_owner_masks": semantic_owner_masks,
        "rest_owner_masks": rest_owner_masks,
        "rest_counts": rest_counts,
        "source_masks": source_masks,
        "semantic_support_masks": semantic_support_masks,
        "polygon_masks": polygon_masks,
    }
    return patches, state


def extract_locked_patches(contract: dict[str, Any]) -> dict[str, LockedPatch]:
    source_path = _locked_path(contract["source_lock"]["sole_rgba_source"], "accepted pose-100 foreground")
    with Image.open(source_path) as image:
        source_rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    patches, _ = _extract_state(contract, source_rgba)
    return patches


def recompose_locked_patches(
    patches: dict[str, LockedPatch],
    canvas_shape: tuple[int, int] | tuple[int, int, int],
) -> np.ndarray:
    """Recompose from extracted local patch pixels, never from the source plate.

    The global rest-owner masks are placement metadata only.  Pixel values are
    read exclusively from ``LockedPatch.rgba`` inside each patch's native-pixel
    bounding box.  This distinction is part of the proof: corrupting a patch
    must corrupt the reconstruction rather than being hidden by source leakage.
    """
    height, width = int(canvas_shape[0]), int(canvas_shape[1])
    reconstruction = np.zeros((height, width, 4), dtype=np.uint8)
    owner_count = np.zeros((height, width), dtype=np.uint16)
    for identifier, patch in patches.items():
        x0, y0, x1, y1 = patch.bbox_xyxy
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise ReconstructionLockError(f"patch {identifier} has an invalid native-pixel bbox")
        expected_shape = (y1 - y0, x1 - x0, 4)
        if patch.rgba.shape != expected_shape or patch.rgba.dtype != np.uint8:
            raise ReconstructionLockError(
                f"patch {identifier} RGBA shape/dtype mismatch: {patch.rgba.shape}/{patch.rgba.dtype}"
            )
        if patch.rest_owner_mask.shape != (height, width):
            raise ReconstructionLockError(f"patch {identifier} rest-owner mask has the wrong canvas shape")
        outside = patch.rest_owner_mask.copy()
        outside[y0:y1, x0:x1] = False
        if np.any(outside):
            raise ReconstructionLockError(f"patch {identifier} owns pixels outside its extracted bbox")
        local_owner = patch.rest_owner_mask[y0:y1, x0:x1]
        owner_count[y0:y1, x0:x1] += local_owner.astype(np.uint16)
        target = reconstruction[y0:y1, x0:x1]
        target[local_owner] = patch.rgba[local_owner]
    if np.any(owner_count > 1):
        raise ReconstructionLockError("rest-owner masks overlap during patch-local recomposition")
    return reconstruction


def _difference_metrics(reference: np.ndarray, candidate: np.ndarray, alpha_label: str) -> dict[str, Any]:
    delta = np.abs(reference.astype(np.int16) - candidate.astype(np.int16))
    rgba_mismatch = np.any(delta > 0, axis=2)
    alpha_mismatch = delta[:, :, 3] > 0
    alpha_subject = reference[:, :, 3] > 0
    rgb_mismatch = np.any(delta[:, :, :3] > 0, axis=2) & alpha_subject
    intersection = np.count_nonzero((reference[:, :, 3] > 0) & (candidate[:, :, 3] > 0))
    union = np.count_nonzero((reference[:, :, 3] > 0) | (candidate[:, :, 3] > 0))
    return {
        "rgba_mismatched_pixels": int(np.count_nonzero(rgba_mismatch)),
        "alpha_mismatched_pixels": int(np.count_nonzero(alpha_mismatch)),
        alpha_label: int(np.count_nonzero(rgb_mismatch)),
        "maximum_channel_error": int(np.max(delta)),
        "rgba_mean_absolute_error": float(np.mean(delta)),
        "alpha_iou": float(intersection / max(1, union)),
        "psnr_db": 999.0 if not np.any(delta) else float(cv2.PSNR(reference, candidate)),
        "exact_pixel_match": bool(not np.any(delta)),
    }


def _operator(identifier: str) -> str:
    leaf = identifier.rsplit(".", 1)[-1]
    if leaf.startswith("maximum_"):
        return "less_than_or_equal"
    if leaf.startswith("minimum_"):
        return "greater_than_or_equal"
    return "equal"


def _flatten(value: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(child, dict):
            output.update(_flatten(child, path))
        else:
            output[path] = child
    return output


def _gate_results(contract: dict[str, Any], measured: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for identifier, threshold in _flatten(contract["quality_gates"]).items():
        if identifier not in measured:
            raise ReconstructionLockError(f"gate {identifier} has no measured value")
        value = measured[identifier]
        operator = _operator(identifier)
        if identifier.endswith("forbidden_independent_limb_patch_ids"):
            operator = "none_present"
            passed = not value
        elif operator == "less_than_or_equal":
            passed = value <= threshold
        elif operator == "greater_than_or_equal":
            passed = value >= threshold
        else:
            passed = value == threshold
        results.append({"id": identifier, "measured": value, "operator": operator, "threshold": threshold, "passed": bool(passed)})
    return results


def _validate_emitted_report_schema(report: dict[str, Any], contract: dict[str, Any]) -> None:
    """Require the emitted report to match every pinned inspectable field."""
    schema = contract["report_schema"]
    _require_equal(set(report), set(schema["required_top_level_fields"]), "report top-level fields")
    section_schemas = {
        "source_lock": "source_lock_fields",
        "extraction_policy": "extraction_policy_fields",
        "topology": "topology_fields",
        "coverage": "coverage_fields",
        "overlap": "overlap_fields",
        "rest_reconstruction": "rest_reconstruction_fields",
        "registered_rest_equivalence": "registered_rest_equivalence_fields",
        "lower_body_stitched_region": "lower_body_stitched_region_fields",
        "edge_detail": "edge_detail_fields",
        "provenance": "provenance_fields",
        "audience_quality": "audience_quality_fields",
    }
    for section, schema_key in section_schemas.items():
        _require_equal(set(report[section]), set(schema[schema_key]), f"{section} report fields")
    for index, row in enumerate(report["patch_inventory"]):
        _require_equal(set(row), set(schema["patch_record_fields"]), f"patch report fields {index}")
    for index, row in enumerate(report["gate_results"]):
        _require_equal(set(row), set(schema["gate_result_fields"]), f"gate report fields {index}")


def evaluate_reconstruction_lock(
    contract: dict[str, Any],
    source_override: str | Path | Image.Image | np.ndarray | None = None,
) -> tuple[dict[str, Any], dict[str, LockedPatch], Image.Image]:
    _validate_contract_invariants(contract)
    source_reference = contract["source_lock"]["sole_rgba_source"]
    locked_source_path = _locked_path(source_reference, "accepted pose-100 foreground")
    with Image.open(locked_source_path) as image:
        locked_rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    if source_override is None:
        source_rgba = locked_rgba
    elif isinstance(source_override, (str, Path)):
        override_path = Path(source_override).resolve()
        if not override_path.is_file() or _sha256(override_path) != source_reference["sha256"]:
            raise ReconstructionLockError("source override violates the pinned source hash")
        with Image.open(override_path) as image:
            source_rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    elif isinstance(source_override, Image.Image):
        source_rgba = np.asarray(source_override.convert("RGBA"), dtype=np.uint8).copy()
    else:
        source_rgba = np.asarray(source_override, dtype=np.uint8).copy()
    if source_rgba.shape != locked_rgba.shape or not np.array_equal(source_rgba, locked_rgba):
        raise ReconstructionLockError("source override pixels do not equal the pinned accepted source")

    patches, state = _extract_state(contract, source_rgba)
    reconstruction = recompose_locked_patches(patches, source_rgba.shape)
    raw_metrics = _difference_metrics(source_rgba, reconstruction, "rgb_mismatched_pixels_where_source_alpha_nonzero")

    control_path = _locked_path(contract["source_lock"]["control_contract"], "GS030 control")
    control = json.loads(control_path.read_text(encoding="utf-8"))
    operation_contract = contract["registered_rest_equivalence"]
    pose = next(row for row in control["poses"] if row["id"] == operation_contract["reference_operation"]["pose_id"])
    source_registered_image, transform_report = registered_pose_layer(
        Image.fromarray(source_rgba, mode="RGBA"), pose, control["contact_registration"]
    )
    reconstruction_registered_image, reconstruction_transform_report = registered_pose_layer(
        Image.fromarray(reconstruction, mode="RGBA"), pose, control["contact_registration"]
    )
    try:
        source_registered = np.asarray(source_registered_image, dtype=np.uint8).copy()
        reconstruction_registered = np.asarray(reconstruction_registered_image, dtype=np.uint8).copy()
    finally:
        source_registered_image.close()
        reconstruction_registered_image.close()
    if transform_report != reconstruction_transform_report:
        raise ReconstructionLockError("registered transform reports diverged")
    registered_metrics = _difference_metrics(
        source_registered,
        reconstruction_registered,
        "rgb_mismatched_pixels_where_reference_alpha_nonzero",
    )
    source_registered_hash = hashlib.sha256(source_registered.tobytes()).hexdigest()
    reconstruction_registered_hash = hashlib.sha256(reconstruction_registered.tobytes()).hexdigest()
    expected_registered_hash = operation_contract["reference_rgba_bytes_sha256"]

    preservation = state["preservation"]
    semantic = state["semantic"]
    extraction_ids = list(patches)
    extraction_cover = np.zeros(preservation.shape, dtype=np.uint8)
    for identifier in extraction_ids:
        extraction_cover += patches[identifier].semantic_support_mask.astype(np.uint8)
    overlap_mask = semantic & (extraction_cover > 1)
    pair_overlap = {
        f"{left}__{right}": int(np.count_nonzero(
            patches[left].semantic_support_mask & patches[right].semantic_support_mask
        ))
        for left, right in contract["patch_extraction"]["overlap"]["required_adjacent_pairs"]
    }
    overlap_contract = contract["patch_extraction"]["overlap"]
    _require_equal(
        int(np.count_nonzero(overlap_mask)),
        overlap_contract["expected_semantic_overlap_pixels"],
        "semantic overlap pixels",
    )
    _require_equal(
        int(np.max(extraction_cover[semantic])),
        overlap_contract["expected_maximum_cover_count"],
        "maximum semantic cover count",
    )
    owned_transparent = int(np.count_nonzero((state["rest_counts"] > 0) & ~preservation))
    foreground_owner_counts = state["rest_counts"][preservation]

    lower_id = contract["lower_body_stitched_region"]["patch_id"]
    lower_patch = patches[lower_id]
    lower_mask = lower_patch.rest_owner_mask
    lower_delta = np.abs(source_rgba.astype(np.int16) - reconstruction.astype(np.int16))
    boot_ids = list(contract["lower_body_stitched_region"]["boot_overlap_patch_ids"])
    lower_system_support = lower_patch.source_mask.copy()
    for identifier in boot_ids:
        lower_system_support |= patches[identifier].source_mask
    included_landmarks = []
    for identifier in contract["lower_body_stitched_region"]["required_landmarks_inside_source_alpha_or_nearest_foreground_px"]:
        point = contract["source_landmarks"]["points"][identifier]
        x, y = int(round(point[0])), int(round(point[1]))
        if 0 <= x < preservation.shape[1] and 0 <= y < preservation.shape[0]:
            if lower_system_support[y, x]:
                included_landmarks.append(identifier)
                continue
        ys, xs = np.where(lower_system_support)
        if len(xs) and float(np.min((xs - x) ** 2 + (ys - y) ** 2)) <= 32.0 ** 2:
            included_landmarks.append(identifier)

    source_edge = cv2.morphologyEx((source_rgba[:, :, 3] > 0).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    reconstruction_edge = cv2.morphologyEx((reconstruction[:, :, 3] > 0).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    edge_mismatch = int(np.count_nonzero(source_edge != reconstruction_edge))
    gray_source = cv2.cvtColor(source_rgba[:, :, :3], cv2.COLOR_RGB2GRAY)
    gray_reconstruction = cv2.cvtColor(reconstruction[:, :, :3], cv2.COLOR_RGB2GRAY)
    source_laplacian = float(cv2.Laplacian(gray_source, cv2.CV_64F).var())
    reconstruction_laplacian = float(cv2.Laplacian(gray_reconstruction, cv2.CV_64F).var())
    laplacian_ratio = reconstruction_laplacian / max(source_laplacian, 1e-12)

    patch_inventory = []
    for specification in contract["patch_extraction"]["patches"]:
        patch = patches[specification["id"]]
        semantic_components = _components(patch.semantic_support_mask)
        ownership_components = _components(patch.rest_owner_mask)
        ownership_pixels = int(np.count_nonzero(patch.rest_owner_mask))
        patch_passed = bool(
            semantic_components == specification["required_connected_components"]
            and ownership_components == 1
            and ownership_pixels > 0
        )
        patch_inventory.append({
            "id": patch.identifier,
            "kind": patch.kind,
            "source_bbox_xyxy_exclusive": list(patch.bbox_xyxy),
            "source_alpha_pixels": int(np.count_nonzero(patch.source_mask)),
            "semantic_support_pixels": int(np.count_nonzero(patch.semantic_support_mask)),
            "ownership_pixels": ownership_pixels,
            "overlap_pixels": int(np.count_nonzero(patch.semantic_support_mask & (extraction_cover > 1))),
            "connected_components": semantic_components,
            "ownership_connected_components": ownership_components,
            "patch_rgba_sha256": hashlib.sha256(patch.rgba.tobytes()).hexdigest(),
            "source_coordinate_hash": patch.source_coordinate_hash,
            "passed": patch_passed,
        })

    topology_gates = contract["quality_gates"]["topology"]
    atomic_ids = [
        row["id"] for row in contract["patch_extraction"]["patches"]
        if row.get("must_remain_atomic") is True or row["id"] in topology_gates["required_atomic_patch_ids"]
    ]
    continuous_ids = [
        row["id"] for row in contract["patch_extraction"]["patches"]
        if row["id"] in topology_gates["required_continuous_patch_ids"]
    ]
    forbidden_present = sorted(
        set(patches).intersection(topology_gates["forbidden_independent_limb_patch_ids"])
    )
    disconnected_support = sorted(row["id"] for row in patch_inventory if row["connected_components"] != 1)
    disconnected_ownership = sorted(
        row["id"] for row in patch_inventory if row["ownership_connected_components"] != 1
    )
    zero_ownership = sorted(row["id"] for row in patch_inventory if row["ownership_pixels"] == 0)
    topology_report = {
        "patch_count": len(patches),
        "disconnected_semantic_support_patches": disconnected_support,
        "disconnected_ownership_patches": disconnected_ownership,
        "zero_ownership_patches": zero_ownership,
        "atomic_patch_ids": list(dict.fromkeys(atomic_ids)),
        "continuous_patch_ids": list(dict.fromkeys(continuous_ids)),
        "forbidden_patch_ids_present": forbidden_present,
        "passed": bool(
            len(patches) == topology_gates["required_patch_count"]
            and not disconnected_support
            and not disconnected_ownership
            and not zero_ownership
            and set(atomic_ids) == set(topology_gates["required_atomic_patch_ids"])
            and set(continuous_ids) == set(topology_gates["required_continuous_patch_ids"])
            and not forbidden_present
        ),
    }

    report = {
        "proof": {
            "phase": contract["phase"],
            "pose_id": "POSE_100_STANDING",
            "canvas": contract["rest_reconstruction"]["canvas"],
            "media_rendered": False,
        },
        "contract_id": contract["contract_id"],
        "source_lock": {
            "source_path": source_reference["path"],
            "source_sha256_expected": source_reference["sha256"],
            "source_sha256_actual": _sha256(locked_source_path),
            "control_path": contract["source_lock"]["control_contract"]["path"],
            "control_sha256_expected": contract["source_lock"]["control_contract"]["sha256"],
            "control_sha256_actual": _sha256(control_path),
            "metadata_path": contract["source_lock"]["accepted_source_metadata"]["path"],
            "metadata_sha256_expected": contract["source_lock"]["accepted_source_metadata"]["sha256"],
            "metadata_sha256_actual": _sha256(_locked_path(contract["source_lock"]["accepted_source_metadata"], "accepted metadata")),
            "width": int(source_rgba.shape[1]),
            "height": int(source_rgba.shape[0]),
            "mode": "RGBA",
            "source_count": 1,
            "passed": True,
        },
        "extraction_policy": {
            "algorithm_id": contract["patch_extraction"]["algorithm_id"],
            "coordinate_space": contract["patch_extraction"]["coordinate_space"],
            "pixel_sampling": contract["patch_extraction"]["pixel_sampling"],
            "region_polygon_count": len(contract["patch_extraction"]["patches"]),
            "low_alpha_fringe_rule": contract["patch_extraction"]["low_alpha_fringe_rule"],
            "generated_atlas_used": False,
            "resampling_used": False,
            "warp_used": False,
            "color_transform_used": False,
            "inpainting_used": False,
            "fallback_used": False,
            "passed": True,
        },
        "patch_inventory": patch_inventory,
        "topology": topology_report,
        "coverage": {
            "foreground_alpha_pixels": int(np.count_nonzero(preservation)),
            "covered_foreground_pixels": int(np.count_nonzero(preservation & (state["rest_counts"] > 0))),
            "uncovered_foreground_pixels": int(np.count_nonzero(preservation & (state["rest_counts"] == 0))),
            "owned_transparent_pixels": owned_transparent,
            "foreground_coverage_fraction": float(np.mean(state["rest_counts"][preservation] > 0)),
            "minimum_rest_owner_count": int(np.min(foreground_owner_counts)),
            "maximum_rest_owner_count": int(np.max(foreground_owner_counts)),
            "passed": True,
        },
        "overlap": {
            "overlap_foreground_pixels": int(np.count_nonzero(overlap_mask)),
            "overlap_fraction_of_foreground": float(np.count_nonzero(overlap_mask) / max(1, np.count_nonzero(semantic))),
            "maximum_extraction_cover_count": int(np.max(extraction_cover[semantic])),
            "required_pair_overlap_pixels": pair_overlap,
            "passed": True,
        },
        "rest_reconstruction": {**raw_metrics, "passed": raw_metrics["exact_pixel_match"]},
        "registered_rest_equivalence": {
            "operation_module_path": operation_contract["reference_operation"]["module_path"],
            "operation_module_sha256_expected": operation_contract["reference_operation"]["module_sha256"],
            "operation_module_sha256_actual": _sha256(_locked_path({"path": operation_contract["reference_operation"]["module_path"], "sha256": operation_contract["reference_operation"]["module_sha256"]}, "registered operation")),
            "source_registered_rgba_bytes_sha256": source_registered_hash,
            "reconstruction_registered_rgba_bytes_sha256": reconstruction_registered_hash,
            "reference_rgba_bytes_sha256_expected": expected_registered_hash,
            "transform_report": transform_report,
            **{key: value for key, value in registered_metrics.items() if key != "psnr_db"},
            "left_support_boot_residual_px": float(transform_report["left_support_boot_residual_px"]),
            "right_boot_residual_px": float(transform_report["right_boot_residual_px"]),
            "passed": bool(registered_metrics["exact_pixel_match"] and source_registered_hash == expected_registered_hash),
        },
        "lower_body_stitched_region": {
            "patch_id": lower_id,
            "source_bbox_xyxy_exclusive": list(lower_patch.bbox_xyxy),
            "connected_components": _components(lower_patch.semantic_owner_mask),
            "ownership_pixels": int(np.count_nonzero(lower_patch.semantic_owner_mask)),
            "support_pixels": int(np.count_nonzero(lower_patch.semantic_support_mask)),
            "included_landmarks": included_landmarks,
            "boot_overlap_patch_ids": boot_ids,
            "independent_leg_child_patch_count": 0,
            "rgba_mismatched_pixels_in_region": int(np.count_nonzero(np.any(lower_delta > 0, axis=2) & lower_mask)),
            "alpha_mismatched_pixels_in_region": int(np.count_nonzero((lower_delta[:, :, 3] > 0) & lower_mask)),
            "used_as_rest_authority": True,
            "passed": True,
        },
        "edge_detail": {
            "alpha_edge_mismatched_pixels": edge_mismatch,
            "bidirectional_edge_chamfer_p95_px": 0.0 if edge_mismatch == 0 else float("inf"),
            "source_laplacian_variance": source_laplacian,
            "reconstruction_laplacian_variance": reconstruction_laplacian,
            "laplacian_variance_ratio": laplacian_ratio,
            "rgba_ssim": 1.0 if raw_metrics["exact_pixel_match"] else 0.0,
            "passed": bool(edge_mismatch == 0 and raw_metrics["exact_pixel_match"]),
        },
        "provenance": {
            "rgba_source_paths": [source_reference["path"]],
            "rgba_source_sha256s": [source_reference["sha256"]],
            "non_source_rgba_pixel_count": 0,
            "generated_pixel_count": 0,
            "resampled_pixel_count": 0,
            "all_output_rgba_pixels_trace_to_integer_source_coordinates": True,
            "passed": True,
        },
        "gates": contract["quality_gates"],
        "gate_results": [],
        "machine_passed": False,
        "audience_quality": contract["failure_policy"]["audience_quality_default"],
        "cash_cost": 0,
        "paid_runtime_dependency": False,
    }

    measured = {
        "source.required_source_count": report["source_lock"]["source_count"],
        "source.required_sha256_match": report["source_lock"]["source_sha256_actual"] == report["source_lock"]["source_sha256_expected"],
        "source.required_control_sha256_match": report["source_lock"]["control_sha256_actual"] == report["source_lock"]["control_sha256_expected"],
        "source.required_metadata_sha256_match": report["source_lock"]["metadata_sha256_actual"] == report["source_lock"]["metadata_sha256_expected"],
        "source.required_width": report["source_lock"]["width"],
        "source.required_height": report["source_lock"]["height"],
        "source.required_mode": report["source_lock"]["mode"],
        "coverage_and_overlap.minimum_foreground_coverage_fraction": report["coverage"]["foreground_coverage_fraction"],
        "coverage_and_overlap.maximum_uncovered_foreground_pixels": report["coverage"]["uncovered_foreground_pixels"],
        "coverage_and_overlap.maximum_owned_transparent_pixels": report["coverage"]["owned_transparent_pixels"],
        "coverage_and_overlap.minimum_rest_owner_count_per_foreground_pixel": report["coverage"]["minimum_rest_owner_count"],
        "coverage_and_overlap.maximum_rest_owner_count_per_foreground_pixel": report["coverage"]["maximum_rest_owner_count"],
        "coverage_and_overlap.minimum_overlap_fraction_of_foreground": report["overlap"]["overlap_fraction_of_foreground"],
        "coverage_and_overlap.maximum_overlap_fraction_of_foreground": report["overlap"]["overlap_fraction_of_foreground"],
        "coverage_and_overlap.minimum_overlap_pixels_per_required_adjacent_pair": min(pair_overlap.values()),
        "coverage_and_overlap.maximum_extraction_cover_count_per_foreground_pixel": report["overlap"]["maximum_extraction_cover_count"],
        "topology.required_patch_count": report["topology"]["patch_count"],
        "topology.required_semantic_support_components_per_patch": max(
            row["connected_components"] for row in patch_inventory
        ),
        "topology.required_ownership_components_per_patch": max(
            row["ownership_connected_components"] for row in patch_inventory
        ),
        "topology.required_atomic_patch_ids": report["topology"]["atomic_patch_ids"],
        "topology.required_continuous_patch_ids": report["topology"]["continuous_patch_ids"],
        "topology.forbidden_independent_limb_patch_ids": report["topology"]["forbidden_patch_ids_present"],
        "topology.maximum_zero_ownership_patches": len(report["topology"]["zero_ownership_patches"]),
        "rest_rgba.maximum_rgba_mismatched_pixels": raw_metrics["rgba_mismatched_pixels"],
        "rest_rgba.maximum_alpha_mismatched_pixels": raw_metrics["alpha_mismatched_pixels"],
        "rest_rgba.maximum_rgb_mismatched_pixels_where_source_alpha_nonzero": raw_metrics["rgb_mismatched_pixels_where_source_alpha_nonzero"],
        "rest_rgba.maximum_channel_error": raw_metrics["maximum_channel_error"],
        "rest_rgba.maximum_rgba_mean_absolute_error": raw_metrics["rgba_mean_absolute_error"],
        "rest_rgba.minimum_alpha_iou": raw_metrics["alpha_iou"],
        "rest_rgba.minimum_psnr_db": raw_metrics["psnr_db"],
        "registered_rest.maximum_rgba_mismatched_pixels": registered_metrics["rgba_mismatched_pixels"],
        "registered_rest.maximum_alpha_mismatched_pixels": registered_metrics["alpha_mismatched_pixels"],
        "registered_rest.maximum_rgb_mismatched_pixels_where_reference_alpha_nonzero": registered_metrics["rgb_mismatched_pixels_where_reference_alpha_nonzero"],
        "registered_rest.maximum_channel_error": registered_metrics["maximum_channel_error"],
        "registered_rest.maximum_rgba_mean_absolute_error": registered_metrics["rgba_mean_absolute_error"],
        "registered_rest.minimum_alpha_iou": registered_metrics["alpha_iou"],
        "registered_rest.maximum_left_support_boot_residual_px": transform_report["left_support_boot_residual_px"],
        "registered_rest.maximum_right_boot_residual_px": transform_report["right_boot_residual_px"],
        "registered_rest.required_reference_rgba_bytes_sha256_match": source_registered_hash == expected_registered_hash,
        "edge_and_detail.maximum_alpha_edge_mismatched_pixels": edge_mismatch,
        "edge_and_detail.maximum_bidirectional_edge_chamfer_p95_px": report["edge_detail"]["bidirectional_edge_chamfer_p95_px"],
        "edge_and_detail.minimum_laplacian_variance_ratio": laplacian_ratio,
        "edge_and_detail.maximum_laplacian_variance_ratio": laplacian_ratio,
        "edge_and_detail.minimum_rgba_ssim": report["edge_detail"]["rgba_ssim"],
        "lower_body.required_patch_id": lower_id,
        "lower_body.required_connected_components": report["lower_body_stitched_region"]["connected_components"],
        "lower_body.minimum_semantic_owner_pixels": report["lower_body_stitched_region"]["ownership_pixels"],
        "lower_body.required_independent_leg_child_patch_count": report["lower_body_stitched_region"]["independent_leg_child_patch_count"],
        "lower_body.maximum_rest_rgba_mismatched_pixels_in_region": report["lower_body_stitched_region"]["rgba_mismatched_pixels_in_region"],
        "lower_body.maximum_rest_alpha_mismatched_pixels_in_region": report["lower_body_stitched_region"]["alpha_mismatched_pixels_in_region"],
    }
    report["gate_results"] = _gate_results(contract, measured)
    pass_sections = (
        "source_lock", "extraction_policy", "topology", "coverage", "overlap",
        "rest_reconstruction", "registered_rest_equivalence", "lower_body_stitched_region",
        "edge_detail", "provenance",
    )
    for section in pass_sections:
        report[section]["passed"] = bool(report[section].get("passed", True))
    gates_passed = all(row["passed"] for row in report["gate_results"])
    sections_passed = all(report[section]["passed"] for section in pass_sections)
    patch_records_passed = all(row["passed"] for row in report["patch_inventory"])
    report["machine_passed"] = bool(gates_passed and sections_passed and patch_records_passed)
    _validate_emitted_report_schema(report, contract)
    if not report["machine_passed"]:
        failures = [row["id"] for row in report["gate_results"] if not row["passed"]]
        failures.extend(f"section.{section}" for section in pass_sections if not report[section]["passed"])
        failures.extend(
            f"patch.{row['id']}" for row in report["patch_inventory"] if not row["passed"]
        )
        raise ReconstructionLockError(f"Phase 30 reconstruction gates failed: {failures}")
    return report, patches, Image.fromarray(reconstruction, mode="RGBA")


def build_rest_reconstruction(contract_path: str | Path) -> dict[str, Any]:
    contract = load_reconstruction_contract(contract_path)
    report, patches, reconstruction = evaluate_reconstruction_lock(contract)
    return {"contract": contract, "report": report, "patches": patches, "reconstruction": reconstruction}


def write_reconstruction_report(contract_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    result = build_rest_reconstruction(contract_path)
    report = result["report"]
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    result["reconstruction"].close()
    return report


_PATCH_COLORS = (
    (230, 79, 79),
    (67, 160, 71),
    (66, 133, 244),
    (244, 180, 0),
    (171, 71, 188),
    (0, 172, 193),
    (255, 112, 67),
    (124, 179, 66),
    (92, 107, 192),
)


def _checkerboard(size: tuple[int, int], tile: int = 24) -> Image.Image:
    width, height = size
    yy, xx = np.indices((height, width))
    cells = ((xx // tile) + (yy // tile)) % 2
    rgb = np.where(cells[:, :, None] == 0, 224, 192).astype(np.uint8)
    rgb = np.repeat(rgb, 3, axis=2)
    return Image.fromarray(rgb, mode="RGB")


def _on_checkerboard(image: Image.Image) -> Image.Image:
    background = _checkerboard(image.size)
    background.paste(image.convert("RGBA"), (0, 0), image.convert("RGBA"))
    return background


def _ownership_overlay(
    source_rgba: np.ndarray,
    patches: dict[str, LockedPatch],
    order: list[str],
) -> Image.Image:
    overlay = source_rgba.copy()
    owner_index = np.full(source_rgba.shape[:2], -1, dtype=np.int16)
    for index, identifier in enumerate(order):
        mask = patches[identifier].rest_owner_mask
        owner_index[mask] = index
        color = np.asarray(_PATCH_COLORS[index], dtype=np.float32)
        overlay[mask, :3] = np.round(
            overlay[mask, :3].astype(np.float32) * 0.42 + color * 0.58
        ).astype(np.uint8)
    boundary = np.zeros(source_rgba.shape[:2], dtype=bool)
    for dy, dx in ((0, 1), (1, 0)):
        shifted = np.roll(owner_index, shift=(dy, dx), axis=(0, 1))
        boundary |= (owner_index >= 0) & (shifted >= 0) & (owner_index != shifted)
    overlay[boundary, :3] = 255
    overlay[boundary, 3] = 255
    return Image.fromarray(overlay, mode="RGBA")


def write_reconstruction_artifacts(
    contract_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Write the bounded Phase 30 still-image proof and machine report.

    These are diagnostic PNGs derived from the pinned accepted foreground; the
    function does not animate, encode video, invent pixels, or authorize motion.
    """
    result = build_rest_reconstruction(contract_path)
    contract = result["contract"]
    report = result["report"]
    patches = result["patches"]
    reconstruction = result["reconstruction"]
    destination = Path(output_dir).resolve()
    patch_dir = destination / "patches"
    patch_dir.mkdir(parents=True, exist_ok=True)

    source_path = _locked_path(contract["source_lock"]["sole_rgba_source"], "accepted pose-100 foreground")
    with Image.open(source_path) as image:
        source = image.convert("RGBA")
        source_rgba = np.asarray(source, dtype=np.uint8).copy()

    reconstruction_path = destination / "june-pose100-reconstruction.png"
    ownership_path = destination / "june-pose100-ownership-map.png"
    difference_path = destination / "june-pose100-absolute-difference.png"
    sheet_path = destination / "june-pose100-reconstruction-proof-sheet.png"
    report_path = destination / "june-pose100-reconstruction-report.json"
    manifest_path = destination / "june-pose100-reconstruction-manifest.json"

    reconstruction.save(reconstruction_path)
    order = list(contract["patch_extraction"]["ownership"]["stable_priority_order"])
    ownership = _ownership_overlay(source_rgba, patches, order)
    ownership.save(ownership_path)
    delta = np.abs(source_rgba.astype(np.int16) - np.asarray(reconstruction, dtype=np.uint8).astype(np.int16))
    difference = np.zeros_like(source_rgba)
    difference[:, :, :3] = np.clip(delta[:, :, :3] * 16, 0, 255).astype(np.uint8)
    difference[:, :, 3] = 255
    Image.fromarray(difference, mode="RGBA").save(difference_path)

    patch_paths: list[Path] = []
    for index, identifier in enumerate(order, start=1):
        patch_path = patch_dir / f"{index:02d}-{identifier}.png"
        Image.fromarray(patches[identifier].rgba, mode="RGBA").save(patch_path)
        patch_paths.append(patch_path)

    source_bbox = contract["source_observations"]["expected_nontransparent_bbox_xyxy_half_open"]
    margin = 28
    crop_box = (
        max(0, int(source_bbox[0]) - margin),
        max(0, int(source_bbox[1]) - margin),
        min(source.width, int(source_bbox[2]) + margin),
        min(source.height, int(source_bbox[3]) + margin),
    )
    panels = [
        _on_checkerboard(source.crop(crop_box)),
        _on_checkerboard(reconstruction.crop(crop_box)),
        _on_checkerboard(ownership.crop(crop_box)),
    ]
    labels = ("ACCEPTED SOURCE", "PATCH-LOCAL RECONSTRUCTION", "9-REGION OWNERSHIP")
    header_height = 34
    legend_height = 58
    sheet = Image.new(
        "RGB",
        (sum(panel.width for panel in panels), max(panel.height for panel in panels) + header_height + legend_height),
        (27, 29, 33),
    )
    draw = ImageDraw.Draw(sheet)
    cursor_x = 0
    for panel, label in zip(panels, labels):
        draw.text((cursor_x + 10, 10), label, fill=(245, 245, 245))
        sheet.paste(panel, (cursor_x, header_height))
        cursor_x += panel.width
    legend_y = header_height + panels[0].height + 9
    legend_x = 10
    for index, identifier in enumerate(order):
        color = _PATCH_COLORS[index]
        draw.rectangle((legend_x, legend_y, legend_x + 14, legend_y + 14), fill=color)
        draw.text((legend_x + 20, legend_y + 2), identifier, fill=(235, 235, 235))
        legend_x += 150
        if index == 4:
            legend_x = 10
            legend_y += 25
    sheet.save(sheet_path, quality=95)

    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    artifact_paths = [reconstruction_path, ownership_path, difference_path, sheet_path, report_path, *patch_paths]
    manifest = {
        "proof": "phase30_reconstruction_locked_patch",
        "contract_id": contract["contract_id"],
        "machine_passed": report["machine_passed"],
        "raw_rgba_mismatched_pixels": report["rest_reconstruction"]["rgba_mismatched_pixels"],
        "registered_rgba_mismatched_pixels": report["registered_rest_equivalence"]["rgba_mismatched_pixels"],
        "patch_count": report["topology"]["patch_count"],
        "artifacts": [
            {
                "path": str(path.relative_to(destination)).replace("\\", "/"),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in artifact_paths
        ],
        "cash_cost": 0,
        "paid_runtime_dependency": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    reconstruction.close()
    source.close()
    ownership.close()
    for panel in panels:
        panel.close()
    sheet.close()
    return {"report": report, "manifest": manifest, "output_dir": str(destination)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build June Oxley's Phase 30 accepted-pixel reconstruction proof")
    parser.add_argument(
        "--contract",
        default=str(REPO_ROOT / "concept/characters/june_oxley_reconstruction_locked_patch_v1.json"),
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT.parents[1] / "outputs/edit/phase30-reconstruction-locked-patch"),
    )
    arguments = parser.parse_args()
    result = write_reconstruction_artifacts(arguments.contract, arguments.output_dir)
    print(json.dumps({
        "machine_passed": result["report"]["machine_passed"],
        "patch_count": result["report"]["topology"]["patch_count"],
        "output_dir": result["output_dir"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
