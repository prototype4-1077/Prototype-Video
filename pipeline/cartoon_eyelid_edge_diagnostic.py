"""Still-only Phase37 V4 registered-lid edge-treatment diagnostic."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any, Iterator

import cv2
import numpy as np
from PIL import Image, ImageDraw, __version__ as PILLOW_VERSION

from pipeline import cartoon_eyelid_alignment_diagnostic as v3


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase37_eyelid_edge_diagnostic_v4.json"
IMPLEMENTATION_RELATIVE_PATH = "pipeline/cartoon_eyelid_edge_diagnostic.py"
TEST_RELATIVE_PATH = "pipeline/tests/test_cartoon_eyelid_edge_diagnostic.py"
FULL_CLOSURE_THRESHOLD = 0.999
FIXED_CREASE_RGB = v3.FIXED_CREASE_RGB
VARIANT_ORDER = ("baseline", "v3_hard", "extended_hard", "feather_1px", "feather_2px")


class EyelidEdgeDiagnosticError(RuntimeError):
    pass


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise EyelidEdgeDiagnosticError(f"V4 edge diagnostic mismatch for {label}: {actual!r} != {expected!r}")


def _sha256(path: str | Path) -> str:
    return v3._sha256(path)


def _lf_hash(path: str | Path) -> str:
    return v3._lf_hash(path)


def _raw_frame_hash(frame: np.ndarray) -> str:
    return v3._raw_frame_hash(frame)


def _mask_hash(mask: np.ndarray) -> str:
    return v3._mask_sha256(mask)


def _mask_metrics(mask: np.ndarray) -> dict[str, Any]:
    return v3._mask_metrics(mask)


def _repo_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise EyelidEdgeDiagnosticError(f"repository path escapes worktree: {relative}") from exc
    if not path.is_file():
        raise EyelidEdgeDiagnosticError(f"repository file missing: {relative}")
    return path


def load_contract(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    resolved = Path(path).resolve()
    _require_equal(resolved, (REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve(), "pinned contract path")
    contract = v3._strict_json(resolved, "Phase37 V4 edge contract")
    _require_equal(contract["contract_version"], 4, "contract version")
    _require_equal(contract["contract_id"], "june_oxley_phase37_eyelid_edge_diagnostic_v4", "contract id")
    _require_equal(contract["cash_cost"], 0, "cash cost")
    _require_equal(contract["diagnostic"]["video_encode_allowed"], False, "video encode policy")
    _require_equal(contract["diagnostic"]["accepted_source_mutation_allowed"], False, "source mutation policy")
    _require_equal(
        contract["predecessor"]["public_head"],
        "a3d48ad2d1576202cac0adcf7345156570bbd0da",
        "full predecessor public HEAD",
    )
    for name, reference in contract["locks"].items():
        locked = _repo_path(str(reference["path"]))
        actual = _lf_hash(locked) if reference.get("hash_domain") == "lf_normalized_text" else _sha256(locked)
        _require_equal(actual, reference["sha256"], f"locked {name} SHA-256")
    return contract


def _connected_seed_component(mask: np.ndarray, seed_xy: tuple[int, int]) -> np.ndarray:
    _, labels = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
    label = int(labels[int(seed_xy[1]), int(seed_xy[0])])
    if label <= 0:
        raise EyelidEdgeDiagnosticError(f"seed {seed_xy} misses candidate mask")
    return labels == label


def _edge_masks(prepared: Any, contract: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    v3_contract = v3.load_contract()
    sclera = v3._classified_sclera_masks(prepared, v3_contract)
    right = sclera["viewer_right_eye"]
    probe = contract["diagnostic"]["residual_band_probe"]
    plate = prepared.face.plate
    hsv = cv2.cvtColor(plate, cv2.COLOR_RGB2HSV)
    threshold = (
        (hsv[:, :, 1] <= int(probe["maximum_saturation_u8"]))
        & (hsv[:, :, 2] >= int(probe["minimum_value_u8"]))
    )
    radius = int(probe["threshold_probe_support_radius_px"])
    search_support = v3._dilate_chebyshev(right["core"], radius) & right["registered_patch"]
    delta = threshold & search_support & ~right["core"]
    seed = tuple(int(value) for value in probe["seed_xy"])
    joined_component = _connected_seed_component(right["core"] | delta, seed)
    _require_equal(plate[seed[1], seed[0]].tolist(), probe["source_rgb"], "probe RGB")
    _require_equal(hsv[seed[1], seed[0]].tolist(), probe["source_hsv"], "probe HSV")
    for name, mask, prefix in (
        ("delta", delta, "expected_delta"),
        ("joined component", joined_component, "expected_joined_component"),
    ):
        metrics = _mask_metrics(mask)
        _require_equal(metrics["area"], probe[f"{prefix}_area"], f"probe {name} area")
        _require_equal(metrics["bbox_xyxy"], probe[f"{prefix}_bbox_xyxy"], f"probe {name} bbox")
        if name == "delta":
            _require_equal(metrics["components_8_connected"], probe["expected_delta_components"], "probe delta components")
        _require_equal(metrics["sha256"], probe[f"{prefix}_mask_sha256"], f"probe {name} hash")
    if not bool(delta[seed[1], seed[0]]):
        raise EyelidEdgeDiagnosticError("probe seed is not a member of the 21px delta")
    if np.any(delta & ~threshold) or np.any(delta & ~search_support) or np.any(delta & right["core"]):
        raise EyelidEdgeDiagnosticError("probe delta violates threshold/support/core subset contract")

    hard_by_eye = {
        "viewer_left_eye": sclera["viewer_left_eye"]["leak"].copy(),
        "viewer_right_eye": right["leak"] | delta,
    }
    hard = hard_by_eye["viewer_right_eye"]
    hard_subject = _connected_seed_component(hard, seed)
    edge = contract["diagnostic"]["edge_corridor"]
    x1, y1, x2, y2 = (int(value) for value in edge["bbox_xyxy"])
    corridor = np.zeros(plate.shape[:2], dtype=bool)
    corridor[y1:y2, x1:x2] = True
    corridor &= right["registered_patch"]
    corridor_metrics = _mask_metrics(corridor)
    _require_equal(corridor_metrics["area"], edge["expected_area"], "edge corridor area")
    _require_equal(corridor_metrics["bbox_xyxy"], edge["expected_bbox_xyxy"], "edge corridor bbox")
    _require_equal(corridor_metrics["components_8_connected"], edge["expected_components"], "edge corridor components")
    _require_equal(corridor_metrics["sha256"], edge["expected_mask_sha256"], "edge corridor hash")
    extended_core = right["core"] | delta
    original_upper, original_lower, _ = v3.phase35.phase34_candidate09._semantic_lid_alpha_masks(
        plate.shape[:2], right["center"], right["radius"], 1.0,
    )
    ring1_geometric = (
        v3._dilate_chebyshev(hard_subject, 1) & ~hard & ~extended_core & corridor
    )
    ring2_geometric = (
        v3._dilate_chebyshev(hard_subject, 2) & ~hard & ~extended_core & corridor
    )
    feather_1px = ring1_geometric & (original_lower < int(edge["feather_1px"]["alpha_u8"]))
    feather_2px_inner = ring1_geometric & (original_lower < int(edge["feather_2px_inner"]["alpha_u8"]))
    feather_2px_outer = (
        ring2_geometric & ~ring1_geometric
        & (original_lower < int(edge["feather_2px_outer"]["alpha_u8"]))
    )
    ring2_only = ring2_geometric & ~ring1_geometric
    for name, mask, spec in (
        ("extended hard write", hard, edge["extended_hard_write"]),
        ("seed-connected hard subject", hard_subject, edge["seed_connected_hard_subject"]),
        ("1px feather", feather_1px, edge["feather_1px"]),
        ("2px inner feather", feather_2px_inner, edge["feather_2px_inner"]),
        ("2px outer feather", feather_2px_outer, edge["feather_2px_outer"]),
    ):
        metrics = _mask_metrics(mask)
        _require_equal(metrics["area"], spec["expected_area"], f"{name} area")
        _require_equal(metrics["bbox_xyxy"], spec["expected_bbox_xyxy"], f"{name} bbox")
        _require_equal(metrics["sha256"], spec["expected_mask_sha256"], f"{name} hash")
    for name, mask, spec in (
        ("1px geometric exterior ring", ring1_geometric, edge["exterior_ring1_geometric"]),
        ("2px geometric exterior ring", ring2_geometric, edge["exterior_ring2_geometric"]),
        ("2px geometric exterior-only ring", ring2_only, edge["exterior_ring2_only"]),
    ):
        metrics = _mask_metrics(mask)
        _require_equal(metrics["area"], spec["expected_area"], f"{name} area")
        _require_equal(metrics["bbox_xyxy"], spec["expected_bbox_xyxy"], f"{name} bbox")
        _require_equal(metrics["components_8_connected"], spec["expected_components"], f"{name} components")
        _require_equal(metrics["sha256"], spec["expected_mask_sha256"], f"{name} hash")
    if np.any((ring1_geometric | ring2_geometric) & (hard | extended_core)):
        raise EyelidEdgeDiagnosticError("geometric exterior ring overlaps extended hard/core support")
    if np.any(feather_2px_inner & feather_2px_outer):
        raise EyelidEdgeDiagnosticError("2px inner/outer feather masks overlap")
    unions = {
        "extended_hard_plus_feather_1px": hard | feather_1px,
        "feather_2px_inner_plus_outer": feather_2px_inner | feather_2px_outer,
        "extended_hard_plus_feather_2px": hard | feather_2px_inner | feather_2px_outer,
    }
    for name, mask in unions.items():
        spec = edge["union_locks"][name]
        _require_equal(int(mask.sum()), spec["expected_area"], f"{name} union area")
        _require_equal(_mask_hash(mask), spec["expected_mask_sha256"], f"{name} union hash")

    override_spec = contract["diagnostic"]["experimental_predecessor_protection_overrides"]
    experimental_overrides: dict[str, np.ndarray] = {}
    for name, mask in (
        ("delta", delta),
        ("feather_1px", feather_1px),
        ("feather_2px_inner", feather_2px_inner),
        ("feather_2px_outer", feather_2px_outer),
    ):
        override = mask & right["protected_non_candidate"]
        spec = override_spec[name]
        _require_equal(int(override.sum()), spec["expected_override_area"], f"{name} experimental protected override area")
        _require_equal(_mask_hash(override), spec["expected_override_mask_sha256"], f"{name} experimental protected override hash")
        _require_equal(_mask_hash(override), _mask_hash(mask), f"{name} entirely overrides V3 protected_non_candidate")
        experimental_overrides[name] = override

    protection_spec = contract["diagnostic"]["declared_viewer_right_geometric_no_write_guard"]
    no_write_guard_polygon = np.zeros(plate.shape[:2], dtype=np.uint8)
    cv2.fillPoly(
        no_write_guard_polygon,
        [np.asarray(protection_spec["polygon_xy"], dtype=np.int32)],
        255,
    )
    no_write_guard = no_write_guard_polygon > 0
    protected_metrics = _mask_metrics(no_write_guard)
    _require_equal(protected_metrics["area"], protection_spec["expected_area"], "geometric no-write guard area")
    _require_equal(protected_metrics["bbox_xyxy"], protection_spec["expected_bbox_xyxy"], "geometric no-write guard bbox")
    _require_equal(protected_metrics["components_8_connected"], protection_spec["expected_components"], "geometric no-write guard components")
    _require_equal(protected_metrics["sha256"], protection_spec["expected_mask_sha256"], "geometric no-write guard hash")
    all_edge_writes = delta | hard_subject | feather_1px | feather_2px_inner | feather_2px_outer
    _require_equal(
        int((no_write_guard & all_edge_writes).sum()),
        protection_spec["required_overlap_with_delta_hard_and_all_exterior_bands"],
        "geometric no-write guard/write overlap",
    )

    tan_spec = contract["diagnostic"]["registered_lid_tan_bump_probe"]
    tan_x, tan_y = (int(value) for value in tan_spec["global_xy"])
    lid_texture = prepared.face.phase33_base.lid_texture
    lid_hsv = cv2.cvtColor(lid_texture, cv2.COLOR_RGB2HSV)
    _require_equal(plate[tan_y, tan_x].tolist(), tan_spec["neutral_plate_rgb"], "tan bump plate RGB")
    _require_equal(hsv[tan_y, tan_x].tolist(), tan_spec["neutral_plate_hsv"], "tan bump plate HSV")
    _require_equal(lid_texture[tan_y, tan_x].tolist(), tan_spec["registered_lower_lid_source_rgb"], "tan bump lid RGB")
    _require_equal(lid_hsv[tan_y, tan_x].tolist(), tan_spec["registered_lower_lid_source_hsv"], "tan bump lid HSV")
    if not bool(feather_2px_outer[tan_y, tan_x]):
        raise EyelidEdgeDiagnosticError("registered tan bump misses locked 2px exterior band")
    soft_1px = np.zeros(plate.shape[:2], dtype=np.uint8)
    soft_1px[feather_1px] = int(edge["feather_1px"]["alpha_u8"])
    soft_2px = np.zeros_like(soft_1px)
    soft_2px[feather_2px_inner] = int(edge["feather_2px_inner"]["alpha_u8"])
    soft_2px[feather_2px_outer] = int(edge["feather_2px_outer"]["alpha_u8"])
    return sclera, {
        "threshold": threshold,
        "probe_search_support": search_support,
        "delta": delta,
        "joined_component": joined_component,
        "extended_core": extended_core,
        "hard_by_eye": hard_by_eye,
        "hard_subject": hard_subject,
        "corridor": corridor,
        "ring1_geometric": ring1_geometric,
        "ring2_geometric": ring2_geometric,
        "ring2_only": ring2_only,
        "feather_1px": feather_1px,
        "feather_2px_inner": feather_2px_inner,
        "feather_2px_outer": feather_2px_outer,
        "soft_1px": soft_1px,
        "soft_2px": soft_2px,
        "original_upper": original_upper,
        "original_lower": original_lower,
        "experimental_overrides": experimental_overrides,
        "declared_geometric_no_write_guard": no_write_guard,
    }


@contextmanager
def _edge_variant(
    sclera: dict[str, dict[str, Any]],
    hard_by_eye: dict[str, np.ndarray],
    soft_by_eye: dict[str, np.ndarray],
    *,
    suppress_crease: bool,
) -> Iterator[dict[str, Any]]:
    phase33 = v3.phase35.phase34_candidate09.phase33
    phase34 = v3.phase35.phase34_candidate09
    original_compose = phase33._compose_eye_lids
    original_masks = phase34._semantic_lid_alpha_masks
    by_center = {tuple(data["center"]): data for data in sclera.values()}
    audit: dict[str, Any] = {"crease_suppressions": [], "eye_calls": []}

    def semantic_masks(
        shape: tuple[int, int], center: tuple[int, int], radius: tuple[int, int], closure: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        upper, lower, crease = original_masks(shape, center, radius, closure)
        if closure < FULL_CLOSURE_THRESHOLD:
            return upper, lower, crease
        data = by_center[tuple(center)]
        hard = hard_by_eye[data["eye_name"]]
        soft = soft_by_eye[data["eye_name"]]
        lower = lower.copy()
        lower[hard] = 255
        lower = np.maximum(lower, soft)
        if suppress_crease:
            crease = np.zeros_like(crease)
        return upper, lower, crease

    def compose(
        canvas: np.ndarray, plate: np.ndarray, lid_texture: np.ndarray, owner: np.ndarray,
        center: tuple[int, int], radius: tuple[int, int], closure: float,
    ) -> tuple[float, int]:
        if closure < FULL_CLOSURE_THRESHOLD:
            return original_compose(canvas, plate, lid_texture, owner, center, radius, closure)
        data = by_center[tuple(center)]
        eye_name = data["eye_name"]
        hard = hard_by_eye[eye_name]
        soft = soft_by_eye[eye_name]
        original_blend_color = phase33._blend_color
        original_blend_source = phase33._blend_source
        cx, cy = center
        rx, ry = radius
        x1, y1, x2, y2 = cx - rx - 5, cy - ry - 12, cx + rx + 6, cy + ry + 12
        expected_upper, expected_lower, _ = original_masks(plate.shape[:2], center, radius, closure)
        expected = [expected_upper[y1:y2, x1:x2], expected_lower[y1:y2, x1:x2]]
        calls: list[dict[str, Any]] = []
        owner_before_crease: np.ndarray | None = None

        def blend_color(target: np.ndarray, color: np.ndarray, alpha: np.ndarray) -> None:
            nonlocal owner_before_crease
            if (
                suppress_crease and color.ndim == 3 and color.shape[2] == 3
                and np.array_equal(color[0, 0], FIXED_CREASE_RGB)
                and bool(np.all(color == FIXED_CREASE_RGB))
            ):
                owner_before_crease = owner.copy()
                audit["crease_suppressions"].append({
                    "eye_name": eye_name, "center": list(center),
                    "nonzero_alpha_pixels": int((alpha > 0).sum()),
                })
                return
            original_blend_color(target, color, alpha)

        def blend_source(target: np.ndarray, source: np.ndarray, alpha: np.ndarray) -> None:
            index = len(calls)
            if index >= 2 or not np.array_equal(alpha, expected[index]):
                raise EyelidEdgeDiagnosticError("unexpected actual lower/upper source call structure")
            if not np.shares_memory(source, lid_texture) or not np.array_equal(source, lid_texture[y1:y2, x1:x2]):
                raise EyelidEdgeDiagnosticError("actual lid source is not registered lid-texture ROI")
            applied = alpha.copy()
            if index == 1:
                local_hard = hard[y1:y2, x1:x2]
                local_soft = soft[y1:y2, x1:x2]
                applied[local_hard] = 255
                applied = np.maximum(applied, local_soft)
            calls.append({
                "index": index + 1, "input_alpha": alpha.copy(), "applied_alpha": applied.copy(),
                "source": source.copy(), "source_shares_memory": True,
            })
            original_blend_source(target, source, applied)

        phase33._blend_color = blend_color
        phase33._blend_source = blend_source
        try:
            ratio, area = original_compose(canvas, plate, lid_texture, owner, center, radius, closure)
            _require_equal(len(calls), 2, f"{eye_name} actual source-call count")
            raw_owner = owner.copy()
            restored = 0
            if suppress_crease:
                if owner_before_crease is None:
                    raise EyelidEdgeDiagnosticError("suppressed crease missed pre-owner capture")
                stale = owner == 9
                restored = int(stale.sum())
                owner[stale] = owner_before_crease[stale]
            prior_owner = np.isin(owner, (7, 8, 9))
            new_owner = hard & ~prior_owner
            owner[hard] = 8
            area += int(new_owner.sum())
            upper_map = np.zeros(plate.shape[:2], dtype=np.uint8)
            lower_map = np.zeros_like(upper_map)
            lower_input_map = np.zeros_like(upper_map)
            upper_map[y1:y2, x1:x2] = calls[0]["applied_alpha"]
            lower_map[y1:y2, x1:x2] = calls[1]["applied_alpha"]
            lower_input_map[y1:y2, x1:x2] = calls[1]["input_alpha"]
            support = hard | (soft > 0)
            rows = []
            for gy, gx in zip(*np.where(support)):
                lx, ly = int(gx - x1), int(gy - y1)
                source_rgb = calls[1]["source"][ly, lx]
                rows.append({
                    "global_xy": [int(gx), int(gy)], "local_source_xy": [lx, ly],
                    "requested_alpha_u8": int(max(255 if hard[gy, gx] else 0, int(soft[gy, gx]))),
                    "applied_alpha_u8": int(lower_map[gy, gx]),
                    "source_rgb": source_rgb.tolist(),
                    "registered_texture_rgb": lid_texture[gy, gx].tolist(),
                    "source_matches_registered_texture": bool(np.array_equal(source_rgb, lid_texture[gy, gx])),
                    "neutral_plate_fallback": bool(np.array_equal(source_rgb, plate[gy, gx])),
                    "inside_registered_patch": bool(data["registered_patch"][gy, gx]),
                })
            audit["eye_calls"].append({
                "eye_name": eye_name, "center": list(center), "radius": list(radius),
                "roi_xyxy": [x1, y1, x2, y2], "source_call_count": 2,
                "source_call_order": ["upper_lid_registered_texture", "lower_lid_registered_texture"],
                "upper_alpha_map": upper_map, "lower_alpha_map": lower_map,
                "lower_input_alpha_map": lower_input_map,
                "raw_upstream_final_owner_map": raw_owner, "final_owner_map": owner.copy(),
                "hard_write_mask": hard.copy(), "soft_write_alpha": soft.copy(),
                "new_hard_owner_pixels": int(new_owner.sum()),
                "suppressed_crease_owner_pixels_restored": restored,
                "source_coordinate_rows": rows,
            })
            return ratio, area
        finally:
            phase33._blend_source = original_blend_source
            phase33._blend_color = original_blend_color

    phase33._compose_eye_lids = compose
    phase34._semantic_lid_alpha_masks = semantic_masks
    try:
        yield audit
    finally:
        phase34._semantic_lid_alpha_masks = original_masks
        phase33._compose_eye_lids = original_compose


def _maximum_adjacent_alpha_jump(
    alpha: np.ndarray, inner: np.ndarray, outer: np.ndarray,
) -> int:
    jumps: list[int] = []
    height, width = alpha.shape
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            inner_y = slice(max(0, -dy), min(height, height - dy))
            inner_x = slice(max(0, -dx), min(width, width - dx))
            outer_y = slice(max(0, dy), min(height, height + dy))
            outer_x = slice(max(0, dx), min(width, width + dx))
            pair = inner[inner_y, inner_x] & outer[outer_y, outer_x]
            if np.any(pair):
                first = alpha[inner_y, inner_x][pair].astype(np.int16)
                second = alpha[outer_y, outer_x][pair].astype(np.int16)
                jumps.extend(np.abs(first - second).tolist())
    if not jumps:
        raise EyelidEdgeDiagnosticError("alpha boundary has no adjacent pixel pairs")
    return int(max(jumps))


def _right_eye_call(audit: dict[str, Any]) -> dict[str, Any]:
    calls = [row for row in audit["eye_calls"] if row["eye_name"] == "viewer_right_eye"]
    _require_equal(len(calls), 1, "viewer-right actual compositor call count")
    return calls[0]


def _audit_actual_focus_writes(
    contract: dict[str, Any],
    masks: dict[str, Any],
    native: dict[str, np.ndarray],
    audits: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    locks = contract["diagnostic"]["actual_compositor_alpha_locks"]
    requirements = locks["requirements"]
    protection = masks["declared_geometric_no_write_guard"]
    v3_call = _right_eye_call(audits["v3_hard"])
    result: dict[str, Any] = {}
    for name in VARIANT_ORDER:
        call = _right_eye_call(audits[name])
        lower = call["lower_alpha_map"]
        lower_input = call["lower_input_alpha_map"]
        upper = call["upper_alpha_map"]
        combined = v3._combined_lid_alpha(upper, lower)
        lower_hash = hashlib.sha256(np.ascontiguousarray(lower).tobytes()).hexdigest()
        combined_hash = hashlib.sha256(np.ascontiguousarray(combined).tobytes()).hexdigest()
        _require_equal(lower_hash, locks["viewer_right_lower_alpha_sha256"][name], f"{name} actual lower alpha hash")
        _require_equal(combined_hash, locks["viewer_right_combined_lid_alpha_sha256"][name], f"{name} actual combined alpha hash")
        decrease_count = int((lower < lower_input).sum())
        _require_equal(decrease_count, requirements["maximum_alpha_decrease_count"], f"{name} lower alpha decreases")
        rows = call["source_coordinate_rows"]
        expected_support = call["hard_write_mask"] | (call["soft_write_alpha"] > 0)
        _require_equal(len(rows), int(expected_support.sum()), f"{name} actual source-coordinate row count")
        if any(
            row["neutral_plate_fallback"]
            or not row["inside_registered_patch"]
            or not row["source_matches_registered_texture"]
            or row["applied_alpha_u8"] < row["requested_alpha_u8"]
            for row in rows
        ):
            raise EyelidEdgeDiagnosticError(f"{name} has invalid registered lower-lid provenance")
        if name in ("extended_hard", "feather_1px", "feather_2px"):
            _require_equal(
                int(combined[masks["extended_core"]].min()),
                requirements["minimum_combined_alpha_on_extended_core_for_extended_variants"],
                f"{name} combined alpha on extended core",
            )
        rgb_protected_delta = int(np.any(native[name][protection] != native["v3_hard"][protection], axis=1).sum())
        owner_protected_delta = int((call["final_owner_map"][protection] != v3_call["final_owner_map"][protection]).sum())
        if name != "baseline":
            _require_equal(rgb_protected_delta, 0, f"{name} declared geometric-guard RGB delta")
            _require_equal(owner_protected_delta, 0, f"{name} declared geometric-guard owner delta")
        result[name] = {
            "viewer_right_lower_alpha_sha256": lower_hash,
            "viewer_right_combined_lid_alpha_sha256": combined_hash,
            "lower_alpha_decrease_count": decrease_count,
            "minimum_combined_alpha_on_extended_core": (
                int(combined[masks["extended_core"]].min())
                if name in ("extended_hard", "feather_1px", "feather_2px") else None
            ),
            "source_coordinate_row_count": len(rows),
            "registered_source_fallback_count": sum(int(row["neutral_plate_fallback"]) for row in rows),
            "declared_geometric_guard_rgb_delta_vs_v3_hard": rgb_protected_delta,
            "declared_geometric_guard_owner_delta_vs_v3_hard": owner_protected_delta,
        }
    if not (
        255 >= int(contract["diagnostic"]["edge_corridor"]["feather_2px_inner"]["alpha_u8"])
        >= int(contract["diagnostic"]["edge_corridor"]["feather_2px_outer"]["alpha_u8"])
    ):
        raise EyelidEdgeDiagnosticError("2px requested-alpha profile is not monotone outward")
    one_combined = v3._combined_lid_alpha(
        _right_eye_call(audits["feather_1px"])["upper_alpha_map"],
        _right_eye_call(audits["feather_1px"])["lower_alpha_map"],
    )
    two_combined = v3._combined_lid_alpha(
        _right_eye_call(audits["feather_2px"])["upper_alpha_map"],
        _right_eye_call(audits["feather_2px"])["lower_alpha_map"],
    )
    jumps = {
        "feather_1px_hard_to_first_exterior": _maximum_adjacent_alpha_jump(
            one_combined, masks["hard_subject"], masks["feather_1px"],
        ),
        "feather_2px_hard_to_first_exterior": _maximum_adjacent_alpha_jump(
            two_combined, masks["hard_subject"], masks["feather_2px_inner"],
        ),
        "feather_2px_first_to_second_exterior": _maximum_adjacent_alpha_jump(
            two_combined, masks["feather_2px_inner"], masks["feather_2px_outer"],
        ),
    }
    _require_equal(
        jumps["feather_1px_hard_to_first_exterior"],
        requirements["maximum_8_neighbor_combined_alpha_jump_hard_to_first_exterior_for_feather_1px"],
        "1px actual maximum boundary alpha jump",
    )
    _require_equal(
        jumps["feather_2px_hard_to_first_exterior"],
        requirements["maximum_8_neighbor_combined_alpha_jump_hard_to_first_exterior_for_feather_2px"],
        "2px actual hard/inner maximum boundary alpha jump",
    )
    _require_equal(
        jumps["feather_2px_first_to_second_exterior"],
        requirements["maximum_8_neighbor_combined_alpha_jump_first_to_second_exterior_for_feather_2px"],
        "2px actual inner/outer maximum boundary alpha jump",
    )
    result["boundary_jumps_u8"] = jumps
    return result


def _variant_specs(
    sclera: dict[str, dict[str, Any]], masks: dict[str, Any], shape: tuple[int, int],
) -> dict[str, dict[str, Any]]:
    zero_bool = np.zeros(shape, dtype=bool)
    zero_alpha = np.zeros(shape, dtype=np.uint8)
    old_hard = {
        "viewer_left_eye": sclera["viewer_left_eye"]["leak"],
        "viewer_right_eye": sclera["viewer_right_eye"]["leak"],
    }
    extended_hard = masks["hard_by_eye"]
    no_soft = {"viewer_left_eye": zero_alpha, "viewer_right_eye": zero_alpha}
    return {
        "baseline": {
            "hard": {"viewer_left_eye": zero_bool, "viewer_right_eye": zero_bool},
            "soft": no_soft, "suppress_crease": False,
        },
        "v3_hard": {"hard": old_hard, "soft": no_soft, "suppress_crease": True},
        "extended_hard": {"hard": extended_hard, "soft": no_soft, "suppress_crease": True},
        "feather_1px": {
            "hard": extended_hard,
            "soft": {"viewer_left_eye": zero_alpha, "viewer_right_eye": masks["soft_1px"]},
            "suppress_crease": True,
        },
        "feather_2px": {
            "hard": extended_hard,
            "soft": {"viewer_left_eye": zero_alpha, "viewer_right_eye": masks["soft_2px"]},
            "suppress_crease": True,
        },
    }


def _prospective_variant_supports(
    contract: dict[str, Any], prepared: Any, sclera: dict[str, dict[str, Any]], masks: dict[str, Any],
    camera: dict[str, Any],
) -> tuple[dict[str, dict[str, np.ndarray]], dict[str, Any]]:
    shape = prepared.face.plate.shape[:2]
    crease = np.zeros(shape, dtype=bool)
    old_hard = np.zeros(shape, dtype=bool)
    extended_hard = np.zeros(shape, dtype=bool)
    geometry = prepared.face.contract["semantic_geometry_native_xy"]
    for eye_name in ("viewer_left_eye", "viewer_right_eye"):
        eye = geometry[eye_name]
        _, _, crease_alpha = v3.phase35.phase34_candidate09._semantic_lid_alpha_masks(
            shape, tuple(eye["center"]), tuple(eye["radius"]), 1.0,
        )
        crease |= crease_alpha > 0
        old_hard |= sclera[eye_name]["leak"]
        extended_hard |= masks["hard_by_eye"][eye_name]
    zero = np.zeros(shape, dtype=bool)
    rgb_native = {
        "baseline": zero,
        "v3_hard": crease | old_hard,
        "extended_hard": crease | extended_hard,
        "feather_1px": crease | extended_hard | masks["feather_1px"],
        "feather_2px": crease | extended_hard | masks["feather_2px_inner"] | masks["feather_2px_outer"],
    }
    owner_native = {
        "baseline": zero,
        "v3_hard": crease | old_hard,
        "extended_hard": crease | extended_hard,
        "feather_1px": crease | extended_hard,
        "feather_2px": crease | extended_hard,
    }
    focus = int(contract["diagnostic"]["source_focus_frame"])
    kernel = contract["diagnostic"]["prospective_transform_support"]
    expected = contract["diagnostic"]["expected_prospective_supports"]
    arrays: dict[str, dict[str, np.ndarray]] = {}
    audit: dict[str, Any] = {}
    for name in VARIANT_ORDER:
        phase35_support, phase35_audit = v3._prospective_support_to_phase35(
            prepared, focus, rgb_native[name], kernel,
        )
        phase36_support, phase36_audit = v3._prospective_support_to_phase36(
            phase35_support, camera, focus, kernel,
        )
        arrays[name] = {
            "native_rgb": rgb_native[name],
            "native_owner": owner_native[name],
            "phase35_rgb": phase35_support,
            "phase36_rgb": phase36_support,
        }
        audit[name] = {
            "native_rgb": {"area": int(rgb_native[name].sum()), "sha256": _mask_hash(rgb_native[name])},
            "native_owner": {"area": int(owner_native[name].sum()), "sha256": _mask_hash(owner_native[name])},
            "phase35_rgb": {**phase35_audit, "sha256": _mask_hash(phase35_support)},
            "phase36_rgb": {**phase36_audit, "sha256": _mask_hash(phase36_support)},
        }
        for stage, keys in (
            ("native_rgb", ("area", "sha256")),
            ("native_owner", ("area", "sha256")),
            (
                "phase35_rgb",
                ("head_input_support_pixels", "head_output_support_pixels", "camera_input_support_pixels", "phase35_final_support_pixels", "sha256"),
            ),
            ("phase36_rgb", ("camera_input_support_pixels", "phase36_final_support_pixels", "sha256")),
        ):
            for key in keys:
                _require_equal(audit[name][stage][key], expected[name][stage][key], f"{name} prospective {stage} {key}")
    return arrays, audit


def _render_focus_states(
    contract: dict[str, Any], prepared: Any, sclera: dict[str, dict[str, Any]], masks: dict[str, Any],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, np.ndarray], dict[str, dict[str, Any]], dict[str, Any]]:
    focus = int(contract["diagnostic"]["source_focus_frame"])
    specs = _variant_specs(sclera, masks, prepared.face.plate.shape[:2])
    native: dict[str, np.ndarray] = {}
    source: dict[str, np.ndarray] = {}
    output: dict[str, np.ndarray] = {}
    audits: dict[str, dict[str, Any]] = {}
    evidence: dict[str, Any] = {}
    for name in VARIANT_ORDER:
        spec = specs[name]
        prepared.native_cache.clear()
        with _edge_variant(
            sclera, spec["hard"], spec["soft"], suppress_crease=bool(spec["suppress_crease"]),
        ) as audit:
            image, native_frame, frame_evidence = v3.phase35.compose_direct_address_frame(prepared, focus)
        native[name] = native_frame.copy()
        source[name] = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
        audits[name] = audit
        evidence[name] = v3._evidence(frame_evidence)
    _require_equal(
        _raw_frame_hash(source["baseline"]),
        contract["diagnostic"]["expected_phase35_f173_baseline_sha256"],
        "F173 baseline",
    )
    v3_report = v3._strict_json(_repo_path(contract["locks"]["phase37_v3_report"]["path"]), "V3 report")
    _require_equal(
        _raw_frame_hash(source["v3_hard"]),
        v3_report["combined_proposal"]["phase35_f173_rgb_sha256"],
        "exact V3 hard F173",
    )
    phase36_contract = v3._strict_json(
        _repo_path(contract["locks"]["phase36_picture_contract"]["path"]), "Phase36 contract",
    )
    camera = next(row["camera"] for row in phase36_contract["shots"] if row["id"] == "LP030_COMPASSION_PUNCH")
    transform: dict[str, Any] | None = None
    for name in VARIANT_ORDER:
        rendered, actual_transform = v3.phase36.compassion_camera(source[name], camera, focus)
        if transform is None:
            transform = actual_transform
        _require_equal(actual_transform, transform, f"{name} unchanged Phase36 camera")
        output[name] = rendered
    _require_equal(
        _raw_frame_hash(output["v3_hard"]),
        contract["diagnostic"]["expected_v3_f248_sha256"],
        "exact V3 hard F248",
    )
    alpha_audit = _audit_actual_focus_writes(contract, masks, native, audits)
    supports, support_audit = _prospective_variant_supports(
        contract, prepared, sclera, masks, camera,
    )
    baseline_owner = _right_eye_call(audits["baseline"])["final_owner_map"]
    containment: dict[str, Any] = {}
    for name in VARIANT_ORDER:
        native_difference = np.any(native[name] != native["baseline"], axis=2)
        source_difference = np.any(source[name] != source["baseline"], axis=2)
        output_difference = np.any(output[name] != output["baseline"], axis=2)
        owner_difference = _right_eye_call(audits[name])["final_owner_map"] != baseline_owner
        v3._require_prospective_containment(native_difference, supports[name]["native_rgb"], f"{name} native RGB")
        v3._require_prospective_containment(owner_difference, supports[name]["native_owner"], f"{name} native owner")
        v3._require_prospective_containment(source_difference, supports[name]["phase35_rgb"], f"{name} Phase35 RGB")
        v3._require_prospective_containment(output_difference, supports[name]["phase36_rgb"], f"{name} Phase36 RGB")
        containment[name] = {
            "native_rgb_changed_pixels": int(native_difference.sum()),
            "native_rgb_changed_outside_prospective_support": v3._outside_support_count(native_difference, supports[name]["native_rgb"]),
            "native_owner_changed_pixels": int(owner_difference.sum()),
            "native_owner_changed_outside_manual_support": v3._outside_support_count(owner_difference, supports[name]["native_owner"]),
            "phase35_rgb_changed_pixels": int(source_difference.sum()),
            "phase35_rgb_changed_outside_prospective_support": v3._outside_support_count(source_difference, supports[name]["phase35_rgb"]),
            "phase36_rgb_changed_pixels": int(output_difference.sum()),
            "phase36_rgb_changed_outside_prospective_support": v3._outside_support_count(output_difference, supports[name]["phase36_rgb"]),
        }
    return native, source, output, audits, {
        "evidence": evidence,
        "camera": camera,
        "transform": transform or {},
        "actual_alpha_audit": alpha_audit,
        "prospective_support_audit": support_audit,
        "prospective_containment": containment,
    }


def _label(image: Image.Image, label: str) -> Image.Image:
    header = 24
    panel = Image.new("RGB", (image.width, image.height + header), (10, 10, 10))
    panel.paste(image, (0, header))
    ImageDraw.Draw(panel).text((5, 6), label, fill=(245, 227, 196))
    return panel


def _grid(
    states: dict[str, np.ndarray], box: tuple[int, int, int, int], scale: int, frame_label: str,
) -> Image.Image:
    panels = []
    for name in VARIANT_ORDER:
        image = v3._crop(states[name], box)
        if scale != 1:
            image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
        variant_label = name.replace("_", " ").upper()
        if name == "feather_2px":
            variant_label += " INNER170 / OUTER85 / TAN PROBE [722,275]"
        panels.append(_label(image, f"{frame_label} {variant_label}"))
    columns = 3
    width = max(panel.width for panel in panels)
    height = max(panel.height for panel in panels)
    sheet = Image.new("RGB", (columns * width, 2 * height), (0, 0, 0))
    for index, panel in enumerate(panels):
        sheet.paste(panel, ((index % columns) * width, (index // columns) * height))
    return sheet


def _pair(
    first: np.ndarray, second: np.ndarray, box: tuple[int, int, int, int], scale: int,
    first_label: str, second_label: str,
) -> Image.Image:
    return v3._comparison(first, second, box, scale, first_label, second_label)


def _classification_overlay(
    plate: np.ndarray, lid_texture: np.ndarray, masks: dict[str, Any], box: tuple[int, int, int, int],
    contract: dict[str, Any],
) -> Image.Image:
    tan_x, tan_y = (
        int(value) for value in contract["diagnostic"]["registered_lid_tan_bump_probe"]["global_xy"]
    )
    tan_marker = np.zeros(plate.shape[:2], dtype=bool)
    tan_marker[tan_y, tan_x] = True
    classification = plate.copy()
    classification = v3._overlay(classification, masks["extended_core"], (30, 220, 245))
    classification = v3._overlay(classification, masks["delta"], (255, 45, 35))
    classification = v3._overlay(classification, masks["feather_1px"], (255, 220, 35))
    classification = v3._overlay(classification, masks["feather_2px_inner"], (255, 135, 20))
    classification = v3._overlay(classification, masks["feather_2px_outer"], (180, 65, 255))
    classification = v3._overlay(classification, tan_marker, (255, 0, 255))
    corridor = plate.copy()
    corridor = v3._overlay(corridor, masks["corridor"], (35, 100, 255))
    corridor = v3._overlay(corridor, masks["hard_by_eye"]["viewer_right_eye"], (255, 45, 35))
    corridor = v3._overlay(corridor, masks["declared_geometric_no_write_guard"], (25, 235, 80))
    panels = [
        (plate, "LOCKED NEUTRAL PLATE"),
        (lid_texture, "ACTUAL REGISTERED LID SOURCE"),
        (
            classification,
            "CYAN CORE / RED +21 / YELLOW 1PX / ORANGE INNER170 / PURPLE OUTER85 / MAGENTA TAN [722,275]",
        ),
        (
            corridor,
            "BLUE HALF-OPEN CORRIDOR / RED HARD / GREEN DECLARED GEOMETRIC NO-WRITE X>=725",
        ),
    ]
    x1, y1, x2, y2 = box
    rendered = [
        _label(
            v3._crop(image, box).resize(((x2 - x1) * 3, (y2 - y1) * 3), Image.Resampling.NEAREST),
            label,
        )
        for image, label in panels
    ]
    width = max(item.width for item in rendered)
    height = max(item.height for item in rendered)
    sheet = Image.new("RGB", (2 * width, 2 * height), (0, 0, 0))
    for index, item in enumerate(rendered):
        sheet.paste(item, ((index % 2) * width, (index // 2) * height))
    return sheet


def _public_write_audit(audit: dict[str, Any]) -> dict[str, Any]:
    public: dict[str, Any] = {
        "crease_suppressions": audit["crease_suppressions"],
        "eye_calls": [],
    }
    for call in audit["eye_calls"]:
        public["eye_calls"].append({
            "eye_name": call["eye_name"],
            "center": call["center"],
            "radius": call["radius"],
            "roi_xyxy": call["roi_xyxy"],
            "source_call_count": call["source_call_count"],
            "source_call_order": call["source_call_order"],
            "upper_alpha_map_sha256": hashlib.sha256(
                np.ascontiguousarray(call["upper_alpha_map"]).tobytes()
            ).hexdigest(),
            "lower_input_alpha_map_sha256": hashlib.sha256(
                np.ascontiguousarray(call["lower_input_alpha_map"]).tobytes()
            ).hexdigest(),
            "lower_alpha_map_sha256": hashlib.sha256(
                np.ascontiguousarray(call["lower_alpha_map"]).tobytes()
            ).hexdigest(),
            "raw_upstream_final_owner_map_sha256": _mask_hash(call["raw_upstream_final_owner_map"]),
            "final_owner_map_sha256": _mask_hash(call["final_owner_map"]),
            "hard_write_mask": _mask_metrics(call["hard_write_mask"]),
            "soft_write_support": _mask_metrics(call["soft_write_alpha"] > 0),
            "soft_write_alpha_sha256": hashlib.sha256(
                np.ascontiguousarray(call["soft_write_alpha"]).tobytes()
            ).hexdigest(),
            "new_hard_owner_pixels": call["new_hard_owner_pixels"],
            "suppressed_crease_owner_pixels_restored": call["suppressed_crease_owner_pixels_restored"],
            "source_coordinate_rows": call["source_coordinate_rows"],
        })
    return public


def run_diagnostic(output_directory: str | Path | None = None) -> dict[str, Any]:
    contract = load_contract()
    output = Path(output_directory).resolve() if output_directory else (
        REPO_ROOT / str(contract["output"]["directory"])
    ).resolve()
    try:
        output.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise EyelidEdgeDiagnosticError("diagnostic output must stay inside isolated worktree") from exc
    if output.exists():
        raise EyelidEdgeDiagnosticError(f"immutable V4 diagnostic output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    phase36_manifest = v3._strict_json(
        _repo_path(contract["locks"]["phase36_candidate01_manifest"]["path"]), "Phase36 manifest",
    )
    phase35_manifest = v3._strict_json(
        _repo_path(contract["locks"]["phase35_candidate03_manifest"]["path"]), "Phase35 manifest",
    )
    phase36_contract = v3._strict_json(
        _repo_path(contract["locks"]["phase36_picture_contract"]["path"]), "Phase36 contract",
    )
    source_frames = [int(value) for value in contract["diagnostic"]["source_frames"]]
    phase36_frames = [int(value) for value in contract["diagnostic"]["phase36_frames"]]
    focus_source = int(contract["diagnostic"]["source_focus_frame"])
    focus_output = int(contract["diagnostic"]["phase36_focus_frame"])
    archive_path = v3._outputs_path(str(contract["immutable_picture"]["external_archive_path"]))
    archive_before = {
        "bytes": archive_path.stat().st_size,
        "mtime_ns": archive_path.stat().st_mtime_ns,
        "sha256": _sha256(archive_path),
    }
    archived, archive_audit = v3._read_picture_archive(
        contract, phase36_manifest, set(phase36_frames),
    )
    phase35_hashes = {
        int(row["frame"]): str(row["rgb_sha256"])
        for row in phase35_manifest["frame_hashes"]
    }
    phase36_hashes = {
        int(row["frame"]): str(row["rgb_sha256"])
        for row in phase36_manifest["frame_hashes"]
    }

    prepared = v3.phase35.prepare_direct_address()
    sclera, masks = _edge_masks(prepared, contract)
    specs = _variant_specs(sclera, masks, prepared.face.plate.shape[:2])
    native_states: dict[str, dict[int, np.ndarray]] = {name: {} for name in VARIANT_ORDER}
    source_states: dict[str, dict[int, np.ndarray]] = {name: {} for name in VARIANT_ORDER}
    evidence_states: dict[str, dict[int, dict[str, Any]]] = {name: {} for name in VARIANT_ORDER}
    variant_audits: dict[str, dict[str, Any]] = {}
    for name in VARIANT_ORDER:
        spec = specs[name]
        prepared.native_cache.clear()
        context = _edge_variant(
            sclera, spec["hard"], spec["soft"],
            suppress_crease=bool(spec["suppress_crease"]),
        )
        audit = context.__enter__()
        try:
            for frame_number in source_frames:
                image, native, evidence = v3.phase35.compose_direct_address_frame(prepared, frame_number)
                final = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
                if name == "baseline":
                    _require_equal(
                        _raw_frame_hash(final), phase35_hashes[frame_number],
                        f"reproduced Phase35 F{frame_number:03d}",
                    )
                native_states[name][frame_number] = native.copy()
                source_states[name][frame_number] = final
                evidence_states[name][frame_number] = v3._evidence(evidence)
        finally:
            context.__exit__(None, None, None)
            variant_audits[name] = audit
    _require_equal(
        _raw_frame_hash(source_states["baseline"][focus_source]),
        contract["diagnostic"]["expected_phase35_f173_baseline_sha256"],
        "full-run F173 baseline",
    )

    camera = next(
        row["camera"] for row in phase36_contract["shots"]
        if row["id"] == "LP030_COMPASSION_PUNCH"
    )
    phase36_states: dict[str, dict[int, np.ndarray]] = {name: {} for name in VARIANT_ORDER}
    transforms: dict[int, dict[str, Any]] = {}
    for source_frame, output_frame in zip(source_frames, phase36_frames):
        expected_transform: dict[str, Any] | None = None
        for name in VARIANT_ORDER:
            rendered, transform = v3.phase36.compassion_camera(
                source_states[name][source_frame], camera, source_frame,
            )
            if expected_transform is None:
                expected_transform = transform
            _require_equal(transform, expected_transform, f"{name} unchanged camera F{output_frame:03d}")
            phase36_states[name][output_frame] = rendered
        transforms[output_frame] = expected_transform or {}
        baseline_output = phase36_states["baseline"][output_frame]
        _require_equal(
            _raw_frame_hash(baseline_output), phase36_hashes[output_frame],
            f"reproduced Phase36 F{output_frame:03d}",
        )
        _require_equal(
            _raw_frame_hash(archived[output_frame]), phase36_hashes[output_frame],
            f"archive Phase36 F{output_frame:03d}",
        )
        _require_equal(
            _raw_frame_hash(baseline_output), _raw_frame_hash(archived[output_frame]),
            f"renderer/archive identity F{output_frame:03d}",
        )
    _require_equal(
        _raw_frame_hash(phase36_states["v3_hard"][focus_output]),
        contract["diagnostic"]["expected_v3_f248_sha256"],
        "full-run exact V3 hard F248",
    )

    changed_frames: dict[str, dict[str, list[int]]] = {}
    for name in VARIANT_ORDER:
        changed_frames[name] = {
            "source": [
                frame for frame in source_frames
                if bool(np.any(source_states[name][frame] != source_states["baseline"][frame]))
            ],
            "phase36": [
                frame for frame in phase36_frames
                if bool(np.any(phase36_states[name][frame] != phase36_states["baseline"][frame]))
            ],
        }
        if name == "baseline":
            _require_equal(changed_frames[name], {"source": [], "phase36": []}, "baseline changed frames")
        else:
            _require_equal(changed_frames[name]["source"], [focus_source], f"{name} source changed frames")
            _require_equal(changed_frames[name]["phase36"], [focus_output], f"{name} Phase36 changed frames")

    native_focus = {name: native_states[name][focus_source] for name in VARIANT_ORDER}
    source_focus = {name: source_states[name][focus_source] for name in VARIANT_ORDER}
    phase36_focus = {name: phase36_states[name][focus_output] for name in VARIANT_ORDER}
    alpha_audit = _audit_actual_focus_writes(
        contract, masks, native_focus, variant_audits,
    )
    support_masks, support_audit = _prospective_variant_supports(
        contract, prepared, sclera, masks, camera,
    )
    baseline_owner = _right_eye_call(variant_audits["baseline"])["final_owner_map"]
    containment: dict[str, Any] = {}
    for name in VARIANT_ORDER:
        native_diff = np.any(native_focus[name] != native_focus["baseline"], axis=2)
        source_diff = np.any(source_focus[name] != source_focus["baseline"], axis=2)
        phase36_diff = np.any(phase36_focus[name] != phase36_focus["baseline"], axis=2)
        owner_diff = _right_eye_call(variant_audits[name])["final_owner_map"] != baseline_owner
        v3._require_prospective_containment(native_diff, support_masks[name]["native_rgb"], f"{name} native RGB")
        v3._require_prospective_containment(owner_diff, support_masks[name]["native_owner"], f"{name} native owner")
        v3._require_prospective_containment(source_diff, support_masks[name]["phase35_rgb"], f"{name} Phase35 RGB")
        v3._require_prospective_containment(phase36_diff, support_masks[name]["phase36_rgb"], f"{name} Phase36 RGB")
        containment[name] = {
            "native_rgb_changed_pixels": int(native_diff.sum()),
            "native_rgb_changed_outside_support": v3._outside_support_count(native_diff, support_masks[name]["native_rgb"]),
            "native_owner_changed_pixels": int(owner_diff.sum()),
            "native_owner_changed_outside_manual_support": v3._outside_support_count(owner_diff, support_masks[name]["native_owner"]),
            "phase35_rgb_changed_pixels": int(source_diff.sum()),
            "phase35_rgb_changed_outside_support": v3._outside_support_count(source_diff, support_masks[name]["phase35_rgb"]),
            "phase36_rgb_changed_pixels": int(phase36_diff.sum()),
            "phase36_rgb_changed_outside_support": v3._outside_support_count(phase36_diff, support_masks[name]["phase36_rgb"]),
        }

    feather_call = _right_eye_call(variant_audits["feather_2px"])
    tan_x, tan_y = contract["diagnostic"]["registered_lid_tan_bump_probe"]["global_xy"]
    tan_rows = [
        row for row in feather_call["source_coordinate_rows"]
        if row["global_xy"] == [tan_x, tan_y]
    ]
    _require_equal(len(tan_rows), 1, "captured registered tan-bump source row")
    tan_row = tan_rows[0]
    _require_equal(
        tan_row["source_rgb"],
        contract["diagnostic"]["registered_lid_tan_bump_probe"]["registered_lower_lid_source_rgb"],
        "captured tan-bump registered source RGB",
    )

    archive_after = {
        "bytes": archive_path.stat().st_size,
        "mtime_ns": archive_path.stat().st_mtime_ns,
        "sha256": _sha256(archive_path),
    }
    _require_equal(archive_after, archive_before, "immutable Candidate01 archive before/after identity")
    gates = [
        v3._gate("phase36_archive_verified_frames", archive_audit["verified_frames"], "==", 303),
        v3._gate("phase35_neighbor_frames_reproduced", len(source_states["baseline"]), "==", 17),
        v3._gate("phase36_neighbor_frames_reproduced", len(phase36_states["baseline"]), "==", 17),
        v3._gate("all_nonbaseline_source_changes_only_f173", [changed_frames[name]["source"] for name in VARIANT_ORDER[1:]], "==", [[focus_source]] * 4),
        v3._gate("all_nonbaseline_phase36_changes_only_f248", [changed_frames[name]["phase36"] for name in VARIANT_ORDER[1:]], "==", [[focus_output]] * 4),
        v3._gate("all_native_rgb_diffs_inside_prospective_support", sum(value["native_rgb_changed_outside_support"] for value in containment.values()), "==", 0),
        v3._gate("all_native_owner_diffs_inside_manual_support", sum(value["native_owner_changed_outside_manual_support"] for value in containment.values()), "==", 0),
        v3._gate("all_phase35_rgb_diffs_inside_prospective_support", sum(value["phase35_rgb_changed_outside_support"] for value in containment.values()), "==", 0),
        v3._gate("all_phase36_rgb_diffs_inside_prospective_support", sum(value["phase36_rgb_changed_outside_support"] for value in containment.values()), "==", 0),
        v3._gate("feather2_extended_core_min_combined_alpha", alpha_audit["feather_2px"]["minimum_combined_alpha_on_extended_core"], "==", 255),
        v3._gate("feather2_registered_source_fallback", alpha_audit["feather_2px"]["registered_source_fallback_count"], "==", 0),
        v3._gate("feather2_actual_source_coordinate_rows", alpha_audit["feather_2px"]["source_coordinate_row_count"], "==", 161),
        v3._gate("feather2_hard_to_inner_max_alpha_jump", alpha_audit["boundary_jumps_u8"]["feather_2px_hard_to_first_exterior"], "==", 85),
        v3._gate("feather2_inner_to_outer_max_alpha_jump", alpha_audit["boundary_jumps_u8"]["feather_2px_first_to_second_exterior"], "==", 85),
        v3._gate("geometric_guard_rgb_delta", alpha_audit["feather_2px"]["declared_geometric_guard_rgb_delta_vs_v3_hard"], "==", 0),
        v3._gate("geometric_guard_owner_delta", alpha_audit["feather_2px"]["declared_geometric_guard_owner_delta_vs_v3_hard"], "==", 0),
        v3._gate("tan_bump_inside_registered_patch", tan_row["inside_registered_patch"], "==", True),
        v3._gate("tan_bump_source_matches_registered_texture", tan_row["source_matches_registered_texture"], "==", True),
        v3._gate("tan_bump_neutral_plate_fallback", tan_row["neutral_plate_fallback"], "==", False),
        v3._gate("immutable_archive_before_after", archive_after, "==", archive_before),
        v3._gate("encoding_process_count", 0, "==", 0),
        v3._gate("paid_service_calls", 0, "==", 0),
    ]
    failed = [gate["name"] for gate in gates if not gate["passed"]]
    if failed:
        raise EyelidEdgeDiagnosticError(f"V4 machine gates failed before publication: {failed}")

    native_support = v3.phase35._native_eye_support_mask(prepared)
    native_box = v3._bbox(native_support, 16)
    phase36_box = (
        max(0, min(value["transformed_eye_roi_xyxy"][0] for value in transforms.values()) - 16),
        max(0, min(value["transformed_eye_roi_xyxy"][1] for value in transforms.values()) - 16),
        min(1920, max(value["transformed_eye_roi_xyxy"][2] for value in transforms.values()) + 16),
        min(1080, max(value["transformed_eye_roi_xyxy"][3] for value in transforms.values()) + 16),
    )
    with tempfile.TemporaryDirectory(prefix="phase37-edge-v4-", dir=output.parent) as temporary:
        stage = Path(temporary) / output.name
        stage.mkdir()
        _grid(native_focus, native_box, 1, "F173 NATIVE").save(
            stage / str(contract["output"]["native_grid_1x"])
        )
        _grid(native_focus, native_box, 3, "F173 NATIVE").save(
            stage / str(contract["output"]["native_grid_3x"])
        )
        _grid(phase36_focus, phase36_box, 1, "F248 PHASE36").save(
            stage / str(contract["output"]["phase36_grid_1x"])
        )
        _grid(phase36_focus, phase36_box, 3, "F248 PHASE36").save(
            stage / str(contract["output"]["phase36_grid_3x"])
        )
        _pair(
            phase36_focus["v3_hard"], phase36_focus["feather_2px"], phase36_box, 3,
            "V3 HARD: PALE ENDPOINT / ABRUPT STEP",
            "V4 2PX: INNER170 / OUTER85 / TAN [722,275] HUMAN REVIEW",
        ).save(stage / str(contract["output"]["phase36_recommendation_ab"]))
        _classification_overlay(
            prepared.face.plate,
            prepared.face.phase33_base.lid_texture,
            masks,
            native_box,
            contract,
        ).save(stage / str(contract["output"]["classification_overlay"]))
        v3._neighbor_sweep(
            phase36_states["baseline"], phase36_states["feather_2px"], phase36_box,
        ).save(stage / str(contract["output"]["neighbor_sweep"]))

        artifacts = v3._artifact_inventory(stage)
        variants: dict[str, Any] = {}
        for name in VARIANT_ORDER:
            variants[name] = {
                "phase35_f173_native_rgb_sha256": _raw_frame_hash(native_focus[name]),
                "phase35_f173_rgb_sha256": _raw_frame_hash(source_focus[name]),
                "phase36_f248_rgb_sha256": _raw_frame_hash(phase36_focus[name]),
                "changed_frames_vs_baseline": changed_frames[name],
                "focus_frame_evidence": evidence_states[name][focus_source],
                "actual_write_audit": _public_write_audit(variant_audits[name]),
                "actual_alpha_audit": alpha_audit[name],
                "prospective_support_audit": support_audit[name],
                "prospective_containment": containment[name],
            }
        report = {
            "report_version": 4,
            "diagnostic_id": "phase37_eyelid_registered_edge_treatment_diagnostic_v4",
            "status": "MACHINE_DIAGNOSTIC_PASSED_FEATHER_2PX_FOR_HUMAN_REVIEW_ONLY",
            "machine_passed": True,
            "human_visual_acceptance_required": True,
            "rebuild_authorized": False,
            "scope": "Still-only 303-frame archive verification plus Phase35 F165-F181 / Phase36 F240-F256 five-state edge-treatment diagnostic; only F173/F248 may change.",
            "cash_cost": 0,
            "paid_service_calls": 0,
            "network_calls": 0,
            "encoding_process_count": 0,
            "video_encoder_invoked": False,
            "contract": {"path": CONTRACT_RELATIVE_PATH, "raw_sha256": _sha256(REPO_ROOT / CONTRACT_RELATIVE_PATH)},
            "implementation": {"path": IMPLEMENTATION_RELATIVE_PATH, "raw_sha256": _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH)},
            "tests": {"path": TEST_RELATIVE_PATH, "raw_sha256": _sha256(REPO_ROOT / TEST_RELATIVE_PATH)},
            "toolchain": {"opencv": cv2.__version__, "numpy": np.__version__, "pillow": PILLOW_VERSION},
            "bindings": {
                "public_head": contract["predecessor"]["public_head"],
                "v3_commit": contract["predecessor"]["v3_commit"],
                "controlling_james_verdict_lf_sha256": _lf_hash(_repo_path(contract["locks"]["controlling_james_verdict"]["path"])),
                "claude_edge_review_lf_sha256": _lf_hash(_repo_path(contract["locks"]["claude_edge_review"]["path"])),
                "phase37_v3_contract_sha256": _sha256(_repo_path(contract["locks"]["phase37_v3_contract"]["path"])),
                "phase37_v3_report_sha256": _sha256(_repo_path(contract["locks"]["phase37_v3_report"]["path"])),
                "phase36_candidate01_manifest_sha256": _sha256(_repo_path(contract["locks"]["phase36_candidate01_manifest"]["path"])),
                "phase36_candidate01_rejection_receipt_sha256": _sha256(_repo_path(contract["locks"]["phase36_candidate01_rejection_receipt"]["path"])),
            },
            "immutable_candidate01_archive": {
                **archive_audit,
                "before": archive_before,
                "after": archive_after,
                "mutated": False,
            },
            "classification_and_edge_masks": {
                "machine_only_not_anatomy_truth": True,
                "probe_delta": _mask_metrics(masks["delta"]),
                "joined_component": _mask_metrics(masks["joined_component"]),
                "corridor": _mask_metrics(masks["corridor"]),
                "extended_hard_write": _mask_metrics(masks["hard_by_eye"]["viewer_right_eye"]),
                "feather_1px": _mask_metrics(masks["feather_1px"]),
                "feather_2px_inner_alpha170": _mask_metrics(masks["feather_2px_inner"]),
                "feather_2px_outer_alpha85": _mask_metrics(masks["feather_2px_outer"]),
                "experimental_v3_protected_non_candidate_overrides": {
                    name: _mask_metrics(mask) for name, mask in masks["experimental_overrides"].items()
                },
                "declared_geometric_no_write_guard": {
                    **_mask_metrics(masks["declared_geometric_no_write_guard"]),
                    "disclosure": contract["diagnostic"]["declared_viewer_right_geometric_no_write_guard"],
                },
                "registered_tan_bump_probe": {
                    **contract["diagnostic"]["registered_lid_tan_bump_probe"],
                    "captured_actual_source_row": tan_row,
                },
            },
            "recommended_variant": {
                "name": "feather_2px",
                "disposition": contract["diagnostic"]["recommended_variant"],
                "basis": contract["diagnostic"]["visual_recommendation_basis"],
                "human_adjudicated_endpoint_x_range": [719, 724],
                "rebuild_authorized": False,
            },
            "variants": variants,
            "baseline": {
                "phase35_source_frame_hashes": [
                    {"frame": frame, "rgb_sha256": _raw_frame_hash(source_states["baseline"][frame])}
                    for frame in source_frames
                ],
                "phase36_frame_hashes": [
                    {"frame": frame, "rgb_sha256": _raw_frame_hash(phase36_states["baseline"][frame])}
                    for frame in phase36_frames
                ],
            },
            "gates": gates,
            "gate_count": len(gates),
            "failed_gates": failed,
            "artifacts": artifacts,
            "disposition": contract["disposition"],
        }
        report_path = stage / str(contract["output"]["report_filename"])
        report_bytes = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")
        _require_equal(b"\r\n" in report_bytes, False, "V4 report LF byte domain")
        report_path.write_bytes(report_bytes)
        _require_equal(
            {path.suffix.lower() for path in stage.iterdir() if path.is_file()} <= {".png", ".json"},
            True,
            "V4 still-only artifact suffixes",
        )
        stage.rename(output)

    return {
        "output_directory": str(output),
        "report": str(output / str(contract["output"]["report_filename"])),
        "machine_passed": True,
        "human_visual_acceptance_required": True,
        "recommended_variant": "FEATHER_2PX_FOR_HUMAN_REVIEW_ONLY",
        "phase35_f173_baseline_sha256": _raw_frame_hash(source_focus["baseline"]),
        "phase36_f248_feather2_sha256": _raw_frame_hash(phase36_focus["feather_2px"]),
        "verified_archive_frames": archive_audit["verified_frames"],
        "encoding_process_count": 0,
    }


def run_preview(output_directory: str | Path) -> dict[str, Any]:
    contract = load_contract()
    output = Path(output_directory).resolve()
    try:
        output.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise EyelidEdgeDiagnosticError("preview output must stay inside worktree") from exc
    if output.exists():
        raise EyelidEdgeDiagnosticError(f"preview output already exists: {output}")
    output.mkdir(parents=True)
    prepared = v3.phase35.prepare_direct_address()
    sclera, masks = _edge_masks(prepared, contract)
    native, source, phase36_states, audits, render = _render_focus_states(contract, prepared, sclera, masks)
    native_box = v3._bbox(v3.phase35._native_eye_support_mask(prepared), 16)
    transform = render["transform"]
    eye = transform["transformed_eye_roi_xyxy"]
    phase36_box = (max(0, eye[0] - 16), max(0, eye[1] - 16), min(1920, eye[2] + 16), min(1080, eye[3] + 16))
    _grid(native, native_box, 1, "F173 NATIVE").save(output / "preview-native-grid-1x.png")
    _grid(native, native_box, 3, "F173 NATIVE").save(output / "preview-native-grid-3x.png")
    _grid(phase36_states, phase36_box, 1, "F248 PHASE36").save(output / "preview-phase36-grid-1x.png")
    _grid(phase36_states, phase36_box, 3, "F248 PHASE36").save(output / "preview-phase36-grid-3x.png")
    _classification_overlay(
        prepared.face.plate, prepared.face.phase33_base.lid_texture, masks, native_box, contract,
    ).save(output / "preview-classification.png")
    return {
        "output_directory": str(output),
        "phase35_hashes": {name: _raw_frame_hash(source[name]) for name in VARIANT_ORDER},
        "phase36_hashes": {name: _raw_frame_hash(phase36_states[name]) for name in VARIANT_ORDER},
        "native_hashes": {name: _raw_frame_hash(native[name]) for name in VARIANT_ORDER},
        "probe_delta": _mask_metrics(masks["delta"]),
        "feather_1px": _mask_metrics(masks["feather_1px"]),
        "feather_2px_inner": _mask_metrics(masks["feather_2px_inner"]),
        "feather_2px_outer": _mask_metrics(masks["feather_2px_outer"]),
        "audit_call_counts": {name: len(audits[name]["eye_calls"]) for name in VARIANT_ORDER},
        "encoding_process_count": 0,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory")
    parser.add_argument("--preview-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.preview_only:
        if not args.output_directory:
            raise EyelidEdgeDiagnosticError("--preview-only requires --output-directory")
        result = run_preview(args.output_directory)
    else:
        result = run_diagnostic(args.output_directory)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
