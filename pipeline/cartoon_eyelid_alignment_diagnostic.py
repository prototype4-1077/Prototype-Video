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
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase37_eyelid_occlusion_diagnostic_v3.json"
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
    _require_equal(contract["contract_version"], 3, "contract version")
    _require_equal(
        contract["contract_id"], "june_oxley_phase37_eyelid_occlusion_diagnostic_v3", "contract id",
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


def _mask_sha256(mask: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(mask.astype(np.uint8)).tobytes()).hexdigest()


def _component_count(mask: np.ndarray) -> int:
    return int(cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)[0] - 1)


def _mask_metrics(mask: np.ndarray) -> dict[str, Any]:
    ys, xs = np.where(mask)
    return {
        "area": int(mask.sum()),
        "bbox_xyxy": list(_bbox(mask)) if len(xs) else None,
        "centroid_xy": [float(xs.mean()), float(ys.mean())] if len(xs) else None,
        "components_8_connected": _component_count(mask),
        "sha256": _mask_sha256(mask),
    }


def _topology(mask: np.ndarray) -> dict[str, int]:
    contours, hierarchy = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE,
    )
    holes = 0 if hierarchy is None else sum(1 for item in hierarchy[0] if int(item[3]) >= 0)
    return {
        "components_8_connected": _component_count(mask),
        "holes": int(holes),
        "contours": len(contours),
    }


def _combined_lid_alpha(upper: np.ndarray, lower: np.ndarray) -> np.ndarray:
    remaining = (
        (255 - upper.astype(np.uint16)) * (255 - lower.astype(np.uint16))
    ) // 255
    return (255 - remaining).astype(np.uint8)


def _classified_sclera_masks(prepared: Any, contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    plate = prepared.face.plate
    lid_texture = prepared.face.phase33_base.lid_texture
    hsv = cv2.cvtColor(plate, cv2.COLOR_RGB2HSV)
    classifier = contract["diagnostic"]["sclera_classification"]
    saturation = int(classifier["maximum_saturation_u8"])
    value = int(classifier["minimum_value_u8"])
    geometry = prepared.face.contract["semantic_geometry_native_xy"]
    result: dict[str, dict[str, Any]] = {}
    for eye_name in ("viewer_left_eye", "viewer_right_eye"):
        spec = classifier[eye_name]
        aperture = np.zeros(plate.shape[:2], dtype=np.uint8)
        cv2.fillPoly(
            aperture,
            [np.asarray(spec["aperture_polygon_xy"], dtype=np.int32)],
            255,
        )
        candidate = (
            (aperture > 0)
            & (hsv[:, :, 1] <= saturation)
            & (hsv[:, :, 2] >= value)
        )
        component_total, labels, _, _ = cv2.connectedComponentsWithStats(
            candidate.astype(np.uint8), connectivity=int(classifier["connectivity"]),
        )
        seed_labels: set[int] = set()
        for seed_x, seed_y in spec["machine_sclera_candidate_seeds_xy"]:
            label = int(labels[int(seed_y), int(seed_x)])
            if label <= 0:
                raise EyelidDiagnosticError(
                    f"{eye_name} machine-classified sclera candidate seed misses the threshold mask"
                )
            seed_labels.add(label)
        core = np.isin(labels, list(seed_labels)) & (labels > 0)
        core_metrics = _mask_metrics(core)
        _require_equal(
            core_metrics["area"], spec["expected_candidate_area"],
            f"{eye_name} machine-classified sclera candidate area",
        )
        _require_equal(
            core_metrics["bbox_xyxy"], spec["expected_candidate_bbox_xyxy"],
            f"{eye_name} machine-classified sclera candidate bbox",
        )
        _require_equal(
            core_metrics["components_8_connected"], spec["expected_candidate_components"],
            f"{eye_name} machine-classified sclera candidate components",
        )
        _require_equal(
            core_metrics["sha256"], spec["expected_candidate_mask_sha256"],
            f"{eye_name} machine-classified sclera candidate hash",
        )

        eye = geometry[eye_name]
        center = tuple(int(item) for item in eye["center"])
        radius = tuple(int(item) for item in eye["radius"])
        upper, lower, _ = phase35.phase34_candidate09._semantic_lid_alpha_masks(
            plate.shape[:2], center, radius, 1.0,
        )
        planning_alpha = _combined_lid_alpha(upper, lower)
        leak = core & (planning_alpha < 255)
        cx, cy = center
        rx, ry = radius
        yy, xx = np.indices(plate.shape[:2], dtype=np.float32)
        planning_hard_owner = (
            ((xx - cx) / float(rx)) ** 2 + ((yy - cy) / float(ry)) ** 2
        ) <= 1.0
        registered_patch = np.zeros(plate.shape[:2], dtype=bool)
        registered_patch[cy - ry:cy + ry + 1, cx - rx:cx + rx + 1] = True
        if np.any(leak & ~registered_patch):
            raise EyelidDiagnosticError(f"{eye_name} sclera leak escapes registered blink patch provenance")
        if np.any(np.all(lid_texture[leak] == plate[leak], axis=1)):
            raise EyelidDiagnosticError(f"{eye_name} sclera leak resolves to neutral-plate fallback pixels")
        fringe = (
            cv2.dilate(leak.astype(np.uint8), np.ones((3, 3), dtype=np.uint8), iterations=1) > 0
        ) & (aperture > 0) & registered_patch & ~leak
        protected_non_candidate = registered_patch & ~core
        disputed_canthus = np.zeros(plate.shape[:2], dtype=bool)
        if "disputed_medial_canthus" in spec:
            disputed_spec = spec["disputed_medial_canthus"]
            seed_x, seed_y = disputed_spec["seed_xy"]
            full_candidate = (hsv[:, :, 1] <= saturation) & (hsv[:, :, 2] >= value)
            old_aperture = np.zeros(plate.shape[:2], dtype=np.uint8)
            cv2.fillPoly(
                old_aperture,
                [np.asarray(disputed_spec["classification_aperture_polygon_xy"], dtype=np.int32)],
                255,
            )
            _, disputed_labels = cv2.connectedComponents(
                (full_candidate & (old_aperture > 0)).astype(np.uint8),
                connectivity=int(classifier["connectivity"]),
            )
            disputed_label = int(disputed_labels[int(seed_y), int(seed_x)])
            if disputed_label <= 0:
                raise EyelidDiagnosticError("disputed medial-canthus seed misses its threshold component")
            disputed_canthus = disputed_labels == disputed_label
            disputed_metrics = _mask_metrics(disputed_canthus)
            _require_equal(
                disputed_metrics["area"], disputed_spec["expected_component_area"],
                "disputed medial-canthus component area",
            )
            _require_equal(
                disputed_metrics["bbox_xyxy"], disputed_spec["expected_component_bbox_xyxy"],
                "disputed medial-canthus component bbox",
            )
            _require_equal(
                disputed_metrics["sha256"], disputed_spec["expected_component_mask_sha256"],
                "disputed medial-canthus component hash",
            )
            if np.any(disputed_canthus & core):
                raise EyelidDiagnosticError("disputed medial canthus entered the recommended candidate mask")
            protected_non_candidate |= disputed_canthus
        else:
            disputed_metrics = _mask_metrics(disputed_canthus)
        result[eye_name] = {
            "eye_name": eye_name,
            "center": center,
            "radius": radius,
            "aperture": aperture > 0,
            "candidate": candidate,
            "core": core,
            "leak": leak,
            "registered_patch": registered_patch,
            "planning_alpha": planning_alpha,
            "planning_hard_owner": planning_hard_owner,
            "fringe": fringe,
            "protected_non_candidate": protected_non_candidate,
            "disputed_canthus": disputed_canthus,
            "seed_component_labels": sorted(seed_labels),
            "threshold_component_count": int(component_total - 1),
            "core_metrics": core_metrics,
            "leak_metrics": _mask_metrics(leak),
            "planning_hard_owner_addition_metrics": _mask_metrics(leak & ~planning_hard_owner),
            "planning_alpha_strengthening_metrics": _mask_metrics(leak & planning_hard_owner),
            "fringe_metrics": _mask_metrics(fringe),
            "protected_non_candidate_metrics": _mask_metrics(protected_non_candidate),
            "disputed_canthus_metrics": disputed_metrics,
            "minimum_planning_alpha_on_candidate": int(planning_alpha[core].min()),
            "minimum_planning_alpha_on_leak": int(planning_alpha[leak].min()),
            "registered_texture_delta_mean_on_leak": float(
                np.abs(lid_texture[leak].astype(np.int16) - plate[leak].astype(np.int16)).mean()
            ),
        }
    return result


@contextmanager
def _full_closure_variant(
    sclera: dict[str, dict[str, Any]],
    *,
    suppress_crease: bool,
    expand_sclera: bool,
) -> Iterator[dict[str, Any]]:
    phase33 = phase35.phase34_candidate09.phase33
    original_compose = phase33._compose_eye_lids
    phase34 = phase35.phase34_candidate09
    original_masks = phase34._semantic_lid_alpha_masks
    audit: dict[str, Any] = {
        "crease_suppressions": [],
        "sclera_expansions": [],
        "eye_calls": [],
    }
    by_center = {tuple(data["center"]): data for data in sclera.values()}

    def semantic_masks_with_variant(
        shape: tuple[int, int],
        center: tuple[int, int],
        radius: tuple[int, int],
        closure: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        upper, lower, crease = original_masks(shape, center, radius, closure)
        if closure < FULL_CLOSURE_THRESHOLD:
            return upper, lower, crease
        data = by_center.get(tuple(center))
        if data is None:
            raise EyelidDiagnosticError(f"unclassified eye center: {center}")
        if expand_sclera:
            lower = lower.copy()
            lower[data["leak"]] = 255
        if suppress_crease:
            crease = np.zeros_like(crease)
        return upper, lower, crease

    def compose_with_variant(
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
        data = by_center.get(tuple(center))
        if data is None:
            raise EyelidDiagnosticError(f"unclassified eye center: {center}")
        original_blend = phase33._blend_color
        original_blend_source = phase33._blend_source
        source_calls = 0
        call_records: list[dict[str, Any]] = []
        owner_before_suppressed_crease: np.ndarray | None = None
        cx, cy = center
        rx, ry = radius
        x1, y1 = cx - rx - 5, cy - ry - 12
        x2, y2 = cx + rx + 6, cy + ry + 12
        expected_upper, expected_lower, _ = original_masks(
            plate.shape[:2], center, radius, closure,
        )
        expected_source_alphas = [
            expected_upper[y1:y2, x1:x2], expected_lower[y1:y2, x1:x2],
        ]

        def blend_except_fixed_crease(target: np.ndarray, color: np.ndarray, alpha: np.ndarray) -> None:
            nonlocal owner_before_suppressed_crease
            if (
                suppress_crease
                and
                color.ndim == 3
                and color.shape[2] == 3
                and np.array_equal(color[0, 0], FIXED_CREASE_RGB)
                and bool(np.all(color == FIXED_CREASE_RGB))
            ):
                owner_before_suppressed_crease = owner.copy()
                audit["crease_suppressions"].append({
                    "center": list(center),
                    "radius": list(radius),
                    "closure": float(closure),
                    "nonzero_alpha_pixels": int((alpha > 0).sum()),
                    "maximum_alpha": int(alpha.max()),
                })
                return
            original_blend(target, color, alpha)

        def blend_source_with_sclera(target: np.ndarray, source: np.ndarray, alpha: np.ndarray) -> None:
            nonlocal source_calls
            source_calls += 1
            if source_calls > 2 or not np.array_equal(alpha, expected_source_alphas[source_calls - 1]):
                raise EyelidDiagnosticError("unexpected Phase33 lid _blend_source call structure")
            if not np.shares_memory(target, canvas):
                raise EyelidDiagnosticError("Phase33 lid target is not a view of the actual F173 canvas")
            if not np.shares_memory(source, lid_texture):
                raise EyelidDiagnosticError("Phase33 lid source is not a view of the registered lid texture")
            if source.shape != lid_texture[y1:y2, x1:x2].shape or not np.array_equal(
                source, lid_texture[y1:y2, x1:x2],
            ):
                raise EyelidDiagnosticError("Phase33 lid source ROI/register mapping changed")
            input_alpha = alpha.copy()
            if expand_sclera and source_calls == 2:
                local_leak = data["leak"][y1:y2, x1:x2]
                if local_leak.shape != alpha.shape:
                    raise EyelidDiagnosticError("sclera expansion/alpha shape mismatch")
                alpha = alpha.copy()
                alpha[local_leak] = 255
            call_records.append({
                "index": source_calls,
                "input_alpha": input_alpha,
                "applied_alpha": alpha.copy(),
                "source": source.copy(),
                "source_shares_registered_texture_memory": True,
            })
            original_blend_source(target, source, alpha)

        phase33._blend_color = blend_except_fixed_crease
        phase33._blend_source = blend_source_with_sclera
        try:
            ratio, area = original_compose(canvas, plate, lid_texture, owner, center, radius, closure)
            if source_calls != 2:
                raise EyelidDiagnosticError(
                    f"expected exactly two Phase33 lid _blend_source calls, observed {source_calls}"
                )
            raw_final_owner = owner.copy()
            restored_crease_owner_pixels = 0
            if suppress_crease:
                if owner_before_suppressed_crease is None:
                    raise EyelidDiagnosticError("suppressed crease did not capture its pre-write owner map")
                stale_crease_owner = owner == 9
                restored_crease_owner_pixels = int(stale_crease_owner.sum())
                owner[stale_crease_owner] = owner_before_suppressed_crease[stale_crease_owner]
            owner_before_expansion = owner.copy()
            if expand_sclera:
                owner[data["leak"]] = 8
                actual_prior_lid_owner = np.isin(owner_before_expansion, (7, 8, 9))
                new_owner = data["leak"] & ~actual_prior_lid_owner
                strengthened = data["leak"] & actual_prior_lid_owner
                area += int(new_owner.sum())
                audit["sclera_expansions"].append({
                    "eye_name": data["eye_name"],
                    "center": list(center),
                    "radius": list(radius),
                    "closure": float(closure),
                    "under_occluded_machine_candidate_pixels": int(data["leak"].sum()),
                    "new_hard_owner_pixels": int(new_owner.sum()),
                    "existing_hard_owner_alpha_strengthened_pixels": int(strengthened.sum()),
                })
            upper_map = np.zeros(plate.shape[:2], dtype=np.uint8)
            lower_map = np.zeros(plate.shape[:2], dtype=np.uint8)
            upper_map[y1:y2, x1:x2] = call_records[0]["applied_alpha"]
            lower_map[y1:y2, x1:x2] = call_records[1]["applied_alpha"]
            provenance_rows = []
            for global_y, global_x in zip(*np.where(data["leak"])):
                local_x, local_y = int(global_x - x1), int(global_y - y1)
                source_rgb = call_records[1]["source"][local_y, local_x]
                registered_rgb = lid_texture[global_y, global_x]
                plate_rgb = plate[global_y, global_x]
                inside_authored_registered_patch = (
                    cx - rx <= global_x < cx + rx + 1
                    and cy - ry <= global_y < cy + ry + 1
                )
                provenance_rows.append({
                    "global_xy": [int(global_x), int(global_y)],
                    "local_source_xy": [local_x, local_y],
                    "source_rgb": source_rgb.tolist(),
                    "registered_texture_rgb": registered_rgb.tolist(),
                    "neutral_plate_rgb": plate_rgb.tolist(),
                    "source_matches_registered_texture": bool(np.array_equal(source_rgb, registered_rgb)),
                    "inside_authored_registered_patch": bool(inside_authored_registered_patch),
                    "neutral_plate_fallback": bool(np.array_equal(source_rgb, plate_rgb)),
                })
            audit["eye_calls"].append({
                "eye_name": data["eye_name"],
                "center": list(center),
                "radius": list(radius),
                "closure": float(closure),
                "roi_xyxy": [x1, y1, x2, y2],
                "source_call_count": source_calls,
                "source_call_order": ["upper_lid_registered_texture", "lower_lid_registered_texture"],
                "upper_alpha_map": upper_map,
                "lower_alpha_map": lower_map,
                "raw_upstream_final_owner_map": raw_final_owner,
                "final_owner_map": owner.copy(),
                "suppressed_crease_owner_pixels_restored": restored_crease_owner_pixels,
                "source_coordinate_rows": provenance_rows,
                "source_call_metrics": [
                    {
                        "index": int(record["index"]),
                        "input_alpha_sha256": _mask_sha256(record["input_alpha"]),
                        "applied_alpha_sha256": _mask_sha256(record["applied_alpha"]),
                        "input_alpha_nonzero_pixels": int((record["input_alpha"] > 0).sum()),
                        "applied_alpha_nonzero_pixels": int((record["applied_alpha"] > 0).sum()),
                        "source_rgb_sha256": hashlib.sha256(
                            np.ascontiguousarray(record["source"]).tobytes()
                        ).hexdigest(),
                        "source_shares_registered_texture_memory": bool(
                            record["source_shares_registered_texture_memory"]
                        ),
                    }
                    for record in call_records
                ],
            })
            return ratio, area
        finally:
            phase33._blend_source = original_blend_source
            phase33._blend_color = original_blend

    phase33._compose_eye_lids = compose_with_variant
    phase34._semantic_lid_alpha_masks = semantic_masks_with_variant
    try:
        yield audit
    finally:
        phase34._semantic_lid_alpha_masks = original_masks
        phase33._compose_eye_lids = original_compose


@contextmanager
def _full_closure_crease_suppressed() -> Iterator[list[dict[str, Any]]]:
    prepared = phase35.prepare_direct_address()
    sclera = _classified_sclera_masks(prepared, load_contract())
    with _full_closure_variant(sclera, suppress_crease=True, expand_sclera=False) as audit:
        yield audit["crease_suppressions"]


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


def _four_state_comparison(
    states: dict[str, np.ndarray],
    box: tuple[int, int, int, int],
    scale: int,
    frame_label: str,
) -> Image.Image:
    order = ("baseline", "crease_only", "mask_only", "combined")
    panels: list[Image.Image] = []
    for name in order:
        panel = _crop(states[name], box)
        if scale != 1:
            panel = panel.resize((panel.width * scale, panel.height * scale), Image.Resampling.NEAREST)
        panels.append(_label(panel, f"{frame_label} {name.replace('_', ' ').upper()}"))
    width = max(panel.width for panel in panels)
    height = max(panel.height for panel in panels)
    sheet = Image.new("RGB", (width * 2, height * 2), (0, 0, 0))
    for index, panel in enumerate(panels):
        sheet.paste(panel, ((index % 2) * width, (index // 2) * height))
    return sheet


def _overlay(frame: np.ndarray, mask: np.ndarray, color: tuple[int, int, int]) -> np.ndarray:
    result = frame.copy()
    tint = np.zeros_like(result)
    tint[:] = np.asarray(color, dtype=np.uint8)
    result[mask] = np.clip(
        result[mask].astype(np.float32) * 0.35 + tint[mask].astype(np.float32) * 0.65,
        0, 255,
    ).astype(np.uint8)
    return result


def _prospective_support_to_phase35(
    prepared: Any,
    frame_number: int,
    support: np.ndarray,
    kernel_contract: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    cubic_radius = int(kernel_contract["phase35_head_warp"]["input_support_radius_px"])
    camera_radius = int(kernel_contract["phase35_camera_resize"]["input_support_radius_px"])
    head_input = _dilate_chebyshev(support, cubic_radius)
    mask = Image.fromarray(
        np.repeat(head_input.astype(np.uint8)[:, :, None] * 255, 3, axis=2), "RGB",
    )
    motion = prepared.motion[frame_number - 1]
    phase35._warp_region(
        mask,
        prepared.scene_contract["rig_regions"]["head"],
        dx=float(motion["head_x_px"]),
        dy=float(motion["head_y_px"]),
        rotation_deg=float(motion["head_tilt_deg"]),
    )
    head_output = np.any(np.asarray(mask, dtype=np.uint8) > 0, axis=2)
    camera_input = _dilate_chebyshev(head_output, camera_radius)
    camera_mask = Image.fromarray(
        np.repeat(camera_input.astype(np.uint8)[:, :, None] * 255, 3, axis=2), "RGB",
    )
    transformed = phase35._camera_frame(
        camera_mask, float(motion["camera_push"]), prepared.scene_contract,
    ).convert("RGB")
    final = np.any(np.asarray(transformed, dtype=np.uint8) > 0, axis=2)
    return final, {
        "selection_policy": kernel_contract["selection_policy"],
        "native_exact_support_pixels": int(support.sum()),
        "head_input_kernel_radius_px": cubic_radius,
        "head_input_support_pixels": int(head_input.sum()),
        "head_output_support_pixels": int(head_output.sum()),
        "camera_input_kernel_radius_px": camera_radius,
        "camera_input_support_pixels": int(camera_input.sum()),
        "phase35_final_support_pixels": int(final.sum()),
    }


def _prospective_support_to_phase36(
    phase35_support: np.ndarray,
    camera: dict[str, Any],
    source_frame: int,
    kernel_contract: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    camera_radius = int(kernel_contract["phase36_camera_resize"]["input_support_radius_px"])
    camera_input = _dilate_chebyshev(phase35_support, camera_radius)
    transformed_rgb, _ = phase36.compassion_camera(
        np.repeat(camera_input.astype(np.uint8)[:, :, None] * 255, 3, axis=2),
        camera,
        source_frame,
    )
    final = np.any(transformed_rgb > 0, axis=2)
    return final, {
        "phase35_input_support_pixels": int(phase35_support.sum()),
        "camera_input_kernel_radius_px": camera_radius,
        "camera_input_support_pixels": int(camera_input.sum()),
        "phase36_final_support_pixels": int(final.sum()),
    }


def _dilate_chebyshev(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius < 0:
        raise EyelidDiagnosticError("support guard radius must be non-negative")
    if radius == 0:
        return mask.copy()
    kernel = np.ones((radius * 2 + 1, radius * 2 + 1), dtype=np.uint8)
    return cv2.dilate(mask.astype(np.uint8), kernel, iterations=1) > 0


def _outside_support_count(difference: np.ndarray, prospective_support: np.ndarray) -> int:
    if difference.shape != prospective_support.shape:
        raise EyelidDiagnosticError("difference/support shape mismatch")
    return int((difference & ~prospective_support).sum())


def _require_prospective_containment(
    difference: np.ndarray, prospective_support: np.ndarray, label: str,
) -> None:
    outside = _outside_support_count(difference, prospective_support)
    if outside:
        raise EyelidDiagnosticError(
            f"{label} has {outside} changed pixel(s) outside the predeclared kernel support"
        )


def _sclera_decomposition(
    plate: np.ndarray,
    lid_texture: np.ndarray,
    states: dict[str, np.ndarray],
    sclera: dict[str, dict[str, Any]],
    box: tuple[int, int, int, int],
) -> Image.Image:
    x1, y1, x2, y2 = box
    core = np.zeros(plate.shape[:2], dtype=bool)
    leak = np.zeros_like(core)
    fringe = np.zeros_like(core)
    protected = np.zeros_like(core)
    disputed = np.zeros_like(core)
    aperture = np.zeros_like(core)
    candidate = np.zeros_like(core)
    for data in sclera.values():
        core |= data["core"]
        leak |= data["leak"]
        fringe |= data["fringe"]
        protected |= data["protected_non_candidate"]
        disputed |= data["disputed_canthus"]
        aperture |= data["aperture"]
        candidate |= data["candidate"]
    classification = _overlay(plate, aperture, (35, 80, 255))
    classification = _overlay(classification, candidate, (255, 215, 30))
    classification = _overlay(classification, core, (30, 235, 255))
    classification = _overlay(classification, disputed, (255, 35, 210))
    ownership = _overlay(plate, protected, (30, 150, 60))
    ownership = _overlay(ownership, fringe, (255, 215, 30))
    ownership = _overlay(ownership, leak, (255, 35, 35))
    panels = [
        (plate, "LOCKED OPEN-EYE SOURCE PLATE"),
        (classification, "CYAN MACHINE CANDIDATE / MAGENTA DISPUTED CANTHUS"),
        (ownership, "GREEN PROTECTED / YELLOW FRINGE / RED UNDER-OCCLUDED"),
        (lid_texture, "REGISTERED BLINK TEXTURE PROVENANCE"),
        (states["baseline"], "BASELINE"),
        (states["crease_only"], "CREASE ONLY"),
        (states["mask_only"], "MASK ONLY"),
        (states["combined"], "COMBINED PROPOSAL"),
    ]
    rendered = [
        _label(
            _crop(image, box).resize(((x2 - x1) * 2, (y2 - y1) * 2), Image.Resampling.NEAREST),
            label,
        )
        for image, label in panels
    ]
    width = max(panel.width for panel in rendered)
    height = max(panel.height for panel in rendered)
    sheet = Image.new("RGB", (width * 2, height * 4), (0, 0, 0))
    for index, panel in enumerate(rendered):
        sheet.paste(panel, ((index % 2) * width, (index // 2) * height))
    return sheet


def _actual_map_decomposition(
    plate: np.ndarray,
    lid_texture: np.ndarray,
    baseline_calls: list[dict[str, Any]],
    combined_calls: list[dict[str, Any]],
    sclera: dict[str, dict[str, Any]],
    combined_frame: np.ndarray,
    box: tuple[int, int, int, int],
) -> Image.Image:
    baseline_alpha = np.zeros(plate.shape[:2], dtype=np.uint8)
    combined_alpha = np.zeros_like(baseline_alpha)
    combined_owner = np.zeros_like(baseline_alpha)
    for call in baseline_calls:
        baseline_alpha = np.maximum(
            baseline_alpha, _combined_lid_alpha(call["upper_alpha_map"], call["lower_alpha_map"]),
        )
    for call in combined_calls:
        combined_alpha = np.maximum(
            combined_alpha, _combined_lid_alpha(call["upper_alpha_map"], call["lower_alpha_map"]),
        )
        combined_owner = np.maximum(combined_owner, call["final_owner_map"])
    candidate = np.zeros(plate.shape[:2], dtype=bool)
    disputed = np.zeros_like(candidate)
    for data in sclera.values():
        candidate |= data["core"]
        disputed |= data["disputed_canthus"]
    classification = _overlay(plate, candidate, (30, 235, 255))
    classification = _overlay(classification, disputed, (255, 35, 210))
    owner_palette = np.zeros_like(plate)
    owner_palette[combined_owner == 7] = (40, 145, 255)
    owner_palette[combined_owner == 8] = (255, 165, 35)
    owner_palette[combined_owner == 9] = (210, 55, 230)
    baseline_alpha_rgb = np.repeat(baseline_alpha[:, :, None], 3, axis=2)
    combined_alpha_rgb = np.repeat(combined_alpha[:, :, None], 3, axis=2)
    panels = [
        (classification, "MACHINE CANDIDATE + PRESERVED CANTHUS"),
        (lid_texture, "ACTUAL REGISTERED LID SOURCE"),
        (baseline_alpha_rgb, "ACTUAL BASELINE UPPER+LOWER ALPHA"),
        (combined_alpha_rgb, "ACTUAL COMBINED UPPER+LOWER ALPHA"),
        (owner_palette, "ACTUAL FINAL OWNER 7 UPPER / 8 LOWER / 9 CREASE"),
        (combined_frame, "RECOMMENDED STILL (HUMAN REVIEW REQUIRED)"),
    ]
    x1, y1, x2, y2 = box
    rendered = [
        _label(
            _crop(image, box).resize(((x2 - x1) * 2, (y2 - y1) * 2), Image.Resampling.NEAREST),
            label,
        )
        for image, label in panels
    ]
    width = max(panel.width for panel in rendered)
    height = max(panel.height for panel in rendered)
    sheet = Image.new("RGB", (width * 2, height * 3), (0, 0, 0))
    for index, panel in enumerate(rendered):
        sheet.paste(panel, ((index % 2) * width, (index // 2) * height))
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


def _eye_calls_by_name(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    calls = audit.get("eye_calls", [])
    result = {str(call["eye_name"]): call for call in calls}
    _require_equal(len(calls), 2, "captured full-closure eye call count")
    _require_equal(
        set(result), {"viewer_left_eye", "viewer_right_eye"},
        "captured full-closure eye call identities",
    )
    return result


def _public_write_audit(audit: dict[str, Any]) -> dict[str, Any]:
    public = {
        "crease_suppressions": audit["crease_suppressions"],
        "sclera_expansions": audit["sclera_expansions"],
        "eye_calls": [],
    }
    for call in audit["eye_calls"]:
        public["eye_calls"].append({
            "eye_name": call["eye_name"],
            "center": call["center"],
            "radius": call["radius"],
            "closure": call["closure"],
            "roi_xyxy": call["roi_xyxy"],
            "source_call_count": call["source_call_count"],
            "source_call_order": call["source_call_order"],
            "upper_alpha_map_sha256": _mask_sha256(call["upper_alpha_map"]),
            "upper_alpha_nonzero_pixels": int((call["upper_alpha_map"] > 0).sum()),
            "lower_alpha_map_sha256": _mask_sha256(call["lower_alpha_map"]),
            "lower_alpha_nonzero_pixels": int((call["lower_alpha_map"] > 0).sum()),
            "raw_upstream_final_owner_map_sha256": _mask_sha256(call["raw_upstream_final_owner_map"]),
            "final_owner_map_sha256": _mask_sha256(call["final_owner_map"]),
            "suppressed_crease_owner_pixels_restored": call["suppressed_crease_owner_pixels_restored"],
            "final_owner_counts": {
                str(value): int((call["final_owner_map"] == value).sum())
                for value in (7, 8, 9)
            },
            "source_call_metrics": call["source_call_metrics"],
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
    phase37_v2_report = _strict_json(
        _repo_path(contract["locks"]["phase37_v2_machine_report"]["path"]), "Phase37 V2 report",
    )
    phase36_frames = [int(value) for value in contract["diagnostic"]["phase36_frames"]]
    source_frames = [int(value) for value in contract["diagnostic"]["source_frames"]]
    archived, archive_audit = _read_picture_archive(contract, phase36_manifest, set(phase36_frames))
    phase35_hashes = {int(row["frame"]): str(row["rgb_sha256"]) for row in phase35_manifest["frame_hashes"]}
    phase36_hashes = {int(row["frame"]): str(row["rgb_sha256"]) for row in phase36_manifest["frame_hashes"]}

    prepared = phase35.prepare_direct_address()
    sclera = _classified_sclera_masks(prepared, contract)
    focus_source = int(contract["diagnostic"]["source_focus_frame"])
    focus_output = int(contract["diagnostic"]["phase36_focus_frame"])
    variant_config = {
        "baseline": (False, False),
        "crease_only": (True, False),
        "mask_only": (False, True),
        "combined": (True, True),
    }
    native_states: dict[str, dict[int, np.ndarray]] = {}
    source_states: dict[str, dict[int, np.ndarray]] = {}
    evidence_states: dict[str, dict[int, dict[str, Any]]] = {}
    variant_audits: dict[str, dict[str, Any]] = {}
    for variant, (suppress_crease, expand_sclera) in variant_config.items():
        prepared.native_cache.clear()
        native_states[variant] = {}
        source_states[variant] = {}
        evidence_states[variant] = {}
        context = _full_closure_variant(
            sclera, suppress_crease=suppress_crease, expand_sclera=expand_sclera,
        )
        audit = context.__enter__()
        try:
            for frame_number in source_frames:
                image, native, evidence = phase35.compose_direct_address_frame(prepared, frame_number)
                final = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
                if variant == "baseline":
                    _require_equal(
                        _raw_frame_hash(final), phase35_hashes[frame_number],
                        f"reproduced Phase35 F{frame_number:03d}",
                    )
                source_states[variant][frame_number] = final
                native_states[variant][frame_number] = native.copy()
                evidence_states[variant][frame_number] = _evidence(evidence)
        finally:
            context.__exit__(None, None, None)
            variant_audits[variant] = audit
    _require_equal(
        _raw_frame_hash(source_states["baseline"][focus_source]),
        contract["diagnostic"]["expected_phase35_f173_rgb_sha256"],
        "frozen Phase35 F173 baseline",
    )

    # Render the predecessor's disputed three-pixel fill only as a labelled visual comparator.
    # It is never the recommended proposal and never enters the four-state gates.
    filled_sclera = {name: dict(data) for name, data in sclera.items()}
    filled_sclera["viewer_left_eye"]["leak"] = (
        sclera["viewer_left_eye"]["leak"] | sclera["viewer_left_eye"]["disputed_canthus"]
    )
    prepared.native_cache.clear()
    with _full_closure_variant(
        filled_sclera, suppress_crease=True, expand_sclera=True,
    ) as canthus_filled_audit:
        canthus_filled_image, canthus_filled_native, _ = phase35.compose_direct_address_frame(
            prepared, focus_source,
        )
    canthus_filled_source = np.asarray(canthus_filled_image.convert("RGB"), dtype=np.uint8).copy()
    _require_equal(
        _raw_frame_hash(canthus_filled_source),
        phase37_v2_report["four_state_variants"]["combined"]["phase35_f173_rgb_sha256"],
        "V2 disputed-canthus-filled F173 comparator",
    )

    camera = next(row["camera"] for row in phase36_contract["shots"] if row["id"] == "LP030_COMPASSION_PUNCH")
    canthus_filled_phase36, canthus_filled_transform = phase36.compassion_camera(
        canthus_filled_source, camera, focus_source,
    )
    _require_equal(
        _raw_frame_hash(canthus_filled_phase36),
        phase37_v2_report["four_state_variants"]["combined"]["phase36_f248_rgb_sha256"],
        "V2 disputed-canthus-filled F248 comparator",
    )
    phase36_states: dict[str, dict[int, np.ndarray]] = {name: {} for name in variant_config}
    transform_evidence: dict[int, dict[str, Any]] = {}
    for source_frame, output_frame in zip(source_frames, phase36_frames):
        expected_transform: dict[str, Any] | None = None
        for variant in variant_config:
            rendered, evidence = phase36.compassion_camera(
                source_states[variant][source_frame], camera, source_frame,
            )
            if expected_transform is None:
                expected_transform = evidence
            _require_equal(evidence, expected_transform, f"unchanged Phase36 camera transform F{output_frame:03d} {variant}")
            phase36_states[variant][output_frame] = rendered
        transform_evidence[output_frame] = expected_transform or {}
        baseline_output = phase36_states["baseline"][output_frame]
        _require_equal(_raw_frame_hash(baseline_output), phase36_hashes[output_frame], f"reproduced Phase36 F{output_frame:03d}")
        _require_equal(_raw_frame_hash(archived[output_frame]), phase36_hashes[output_frame], f"archived Phase36 F{output_frame:03d}")
        _require_equal(
            _raw_frame_hash(baseline_output), _raw_frame_hash(archived[output_frame]),
            f"renderer/archive identity F{output_frame:03d}",
        )

    changed_frames: dict[str, dict[str, list[int]]] = {}
    for variant in ("crease_only", "mask_only", "combined"):
        changed_frames[variant] = {
            "source": [
                frame for frame in source_frames
                if bool(np.any(source_states["baseline"][frame] != source_states[variant][frame]))
            ],
            "phase36": [
                frame for frame in phase36_frames
                if bool(np.any(phase36_states["baseline"][frame] != phase36_states[variant][frame]))
            ],
        }
        _require_equal(changed_frames[variant]["source"], [focus_source], f"{variant} source changed frames")
        _require_equal(changed_frames[variant]["phase36"], [focus_output], f"{variant} Phase36 changed frames")

    geometry = prepared.face.contract["semantic_geometry_native_xy"]
    native_support = phase35._native_eye_support_mask(prepared)
    crease_mask = np.zeros(prepared.face.plate.shape[:2], dtype=bool)
    leak_mask = np.zeros_like(crease_mask)
    core_mask = np.zeros_like(crease_mask)
    fringe_mask = np.zeros_like(crease_mask)
    protected_mask = np.zeros_like(crease_mask)
    disputed_canthus_mask = np.zeros_like(crease_mask)
    for eye_name in ("viewer_left_eye", "viewer_right_eye"):
        eye = geometry[eye_name]
        _, _, crease_alpha = phase35.phase34_candidate09._semantic_lid_alpha_masks(
            prepared.face.plate.shape[:2], tuple(eye["center"]), tuple(eye["radius"]), 1.0,
        )
        crease_mask |= crease_alpha > 0
        leak_mask |= sclera[eye_name]["leak"]
        core_mask |= sclera[eye_name]["core"]
        fringe_mask |= sclera[eye_name]["fringe"]
        protected_mask |= sclera[eye_name]["protected_non_candidate"]
        disputed_canthus_mask |= sclera[eye_name]["disputed_canthus"]
    _require_equal(int((crease_mask & leak_mask).sum()), 0, "crease/sclera support overlap")
    allowed_native = {
        "crease_only": crease_mask,
        "mask_only": leak_mask,
        "combined": crease_mask | leak_mask,
    }
    kernel_support = contract["diagnostic"]["prospective_transform_support"]
    allowed_phase35: dict[str, np.ndarray] = {}
    prospective_audit: dict[str, dict[str, Any]] = {}
    for name, mask in allowed_native.items():
        allowed_phase35[name], phase35_support_audit = _prospective_support_to_phase35(
            prepared, focus_source, mask, kernel_support,
        )
        prospective_audit[name] = {"phase35": phase35_support_audit}

    difference_audit: dict[str, dict[str, Any]] = {}
    native_diffs: dict[str, np.ndarray] = {}
    for variant in ("crease_only", "mask_only", "combined"):
        native_diff = np.any(
            native_states["baseline"][focus_source] != native_states[variant][focus_source], axis=2,
        )
        final_diff = np.any(
            source_states["baseline"][focus_source] != source_states[variant][focus_source], axis=2,
        )
        output_diff = np.any(
            phase36_states["baseline"][focus_output] != phase36_states[variant][focus_output], axis=2,
        )
        allowed_phase36, phase36_support_audit = _prospective_support_to_phase36(
            allowed_phase35[variant], camera, focus_source, kernel_support,
        )
        prospective_audit[variant]["phase36"] = phase36_support_audit
        expected_counts = contract["diagnostic"]["expected_prospective_support_counts"][variant]
        for stage_name in ("phase35", "phase36"):
            for metric_name, expected_value in expected_counts[stage_name].items():
                _require_equal(
                    prospective_audit[variant][stage_name][metric_name], expected_value,
                    f"{variant} prospective {stage_name} {metric_name}",
                )
        native_diffs[variant] = native_diff
        difference_audit[variant] = {
            "changed_pixels_native": int(native_diff.sum()),
            "changed_pixels_phase35_final": int(final_diff.sum()),
            "changed_pixels_phase36_f248": int(output_diff.sum()),
            "native_changed_outside_allowed_support": int((native_diff & ~allowed_native[variant]).sum()),
            "prospective_transform_support": prospective_audit[variant],
            "phase35_changed_outside_transformed_allowed_support": _outside_support_count(
                final_diff, allowed_phase35[variant],
            ),
            "phase36_changed_outside_twice_transformed_allowed_support": int((output_diff & ~allowed_phase36).sum()),
        }

    mask_delta_from_crease = np.any(
        native_states["crease_only"][focus_source] != native_states["combined"][focus_source], axis=2,
    )
    owner_audit: dict[str, dict[str, Any]] = {}
    hard_owner_additions = 0
    alpha_strengthened = 0
    residual_before = 0
    residual_after = 0
    actual_planning_mask_mismatch = 0
    baseline_eye_calls = _eye_calls_by_name(variant_audits["baseline"])
    combined_eye_calls = _eye_calls_by_name(variant_audits["combined"])
    for eye_name in ("viewer_left_eye", "viewer_right_eye"):
        data = sclera[eye_name]
        baseline_call = baseline_eye_calls[eye_name]
        combined_call = combined_eye_calls[eye_name]
        baseline_alpha = _combined_lid_alpha(
            baseline_call["upper_alpha_map"], baseline_call["lower_alpha_map"],
        )
        proposed_alpha = _combined_lid_alpha(
            combined_call["upper_alpha_map"], combined_call["lower_alpha_map"],
        )
        baseline_owner = np.isin(baseline_call["final_owner_map"], (7, 8, 9))
        proposed_owner = np.isin(combined_call["final_owner_map"], (7, 8, 9))
        actual_under_occluded = data["core"] & (baseline_alpha < 255)
        actual_planning_mask_mismatch += int(np.logical_xor(actual_under_occluded, data["leak"]).sum())
        new_owner_mask = data["leak"] & ~baseline_owner
        strengthened_mask = data["leak"] & baseline_owner
        ys, xs = np.where(proposed_owner)
        cx, cy = data["center"]
        rx, ry = data["radius"]
        topology = _topology(proposed_owner)
        hard = int(new_owner_mask.sum())
        strengthened = int(strengthened_mask.sum())
        hard_owner_additions += hard
        alpha_strengthened += strengthened
        residual_before += int(actual_under_occluded.sum())
        residual_after += int((data["core"] & (proposed_alpha < 255)).sum())
        provenance_rows = combined_call["source_coordinate_rows"]
        owner_audit[eye_name] = {
            "classification": {
                "aperture_polygon_xy": contract["diagnostic"]["sclera_classification"][eye_name]["aperture_polygon_xy"],
                "machine_sclera_candidate_seeds_xy": contract["diagnostic"]["sclera_classification"][eye_name]["machine_sclera_candidate_seeds_xy"],
                "status": contract["diagnostic"]["sclera_classification"]["status"],
                "seed_component_labels": data["seed_component_labels"],
                "threshold_component_count": data["threshold_component_count"],
                "machine_candidate": data["core_metrics"],
                "actual_under_occluded_candidate": data["leak_metrics"],
                "one_px_diagnostic_fringe": data["fringe_metrics"],
                "protected_non_candidate": data["protected_non_candidate_metrics"],
                "disputed_medial_canthus": data["disputed_canthus_metrics"],
            },
            "provenance": {
                "captured_from_actual_lower_lid_source_call": True,
                "local_to_global_source_coordinate_rows": provenance_rows,
                "source_matches_registered_texture_pixels": sum(
                    int(row["source_matches_registered_texture"]) for row in provenance_rows
                ),
                "inside_authored_registered_patch_pixels": sum(
                    int(row["inside_authored_registered_patch"]) for row in provenance_rows
                ),
                "neutral_plate_fallback_pixels": sum(
                    int(row["neutral_plate_fallback"]) for row in provenance_rows
                ),
                "registered_texture_delta_mean_on_leak": data["registered_texture_delta_mean_on_leak"],
            },
            "actual_compositor_alpha_and_owner": {
                "source_call_count": combined_call["source_call_count"],
                "source_call_order": combined_call["source_call_order"],
                "source_call_metrics": combined_call["source_call_metrics"],
                "upper_alpha_map_sha256": _mask_sha256(combined_call["upper_alpha_map"]),
                "lower_alpha_map_sha256": _mask_sha256(combined_call["lower_alpha_map"]),
                "final_owner_map_sha256": _mask_sha256(combined_call["final_owner_map"]),
                "minimum_baseline_alpha_on_machine_candidate": int(baseline_alpha[data["core"]].min()),
                "minimum_baseline_alpha_on_under_occluded_candidate": int(baseline_alpha[data["leak"]].min()),
                "minimum_proposed_alpha_on_machine_candidate": int(proposed_alpha[data["core"]].min()),
                "residual_under_occluded_candidate_before": int(actual_under_occluded.sum()),
                "residual_under_occluded_candidate_after": int((data["core"] & (proposed_alpha < 255)).sum()),
                "candidate_pixels_with_non_lid_final_owner": int(
                    (data["core"] & ~np.isin(combined_call["final_owner_map"], (7, 8))).sum()
                ),
                "new_hard_owner_pixels": hard,
                "existing_hard_owner_alpha_strengthened_pixels": strengthened,
                "proposed_hard_owner_area": int(proposed_owner.sum()),
            },
            "topology_and_authored_geometry": {
                **topology,
                "center_xy": list(data["center"]),
                "radius_xy": list(data["radius"]),
                "centroid_offset_in_eye_radii": [
                    float((xs.mean() - cx) / rx), float((ys.mean() - cy) / ry),
                ],
                "note": "Descriptive only; authored perspective and weathered facial asymmetry are preserved, not forced into mirror symmetry.",
            },
        }

    baseline_lid_areas = evidence_states["baseline"][focus_source]["lid_areas"]
    combined_lid_areas = evidence_states["combined"][focus_source]["lid_areas"]
    expected_combined_lid_areas = [
        baseline_lid_areas[index]
        + owner_audit[eye_name]["actual_compositor_alpha_and_owner"]["new_hard_owner_pixels"]
        for index, eye_name in enumerate(("viewer_left_eye", "viewer_right_eye"))
    ]
    deformation = geometry["deformation_roi"]
    cage_mask = np.zeros_like(native_support, dtype=bool)
    cage_mask[int(deformation[1]):int(deformation[3]), int(deformation[0]):int(deformation[2])] = True
    eye_y = np.where(native_support)[0]
    phase34_source = inspect.getsource(phase35.phase34_candidate09._native_frame)
    phase35_source = inspect.getsource(phase35.compose_direct_address_frame)
    order_audit = {
        "cage_write_precedes_lid_write": phase34_source.index("canvas[warp_support > 0]") < phase34_source.index("phase33._compose_eye_lids"),
        "complete_face_paste_precedes_head_warp": phase35_source.index("frame.paste(face_frame") < phase35_source.index('regions["head"]'),
        "native_eye_support_cage_overlap_pixels": int((native_support & cage_mask).sum()),
        "native_eye_support_to_cage_vertical_gap_px": int(deformation[1]) - int(eye_y.max()) - 1,
        "determination": (
            "F248 contains two separable source defects: a fixed-color synthetic crease over registered natural fold "
            "texture, and incomplete full-closure alpha/ownership over a machine-classified sclera candidate. The "
            "three-pixel viewer-left medial-canthus highlight is disputed and preserved. The mouth/cheek cage "
            "is spatially disjoint and written before lids; the complete face then shares one head warp and camera path."
        ),
        "remaining_upper_pale_band_classification": (
            "Registered blink-texture anatomy captured from the actual lid source call, not residual neutral-plate "
            "sclera or fallback. Its artistic acceptability remains a human picture-review decision."
        ),
    }

    gates = [
        _gate("phase35_f173_exact_baseline", _raw_frame_hash(source_states["baseline"][focus_source]), "==", contract["diagnostic"]["expected_phase35_f173_rgb_sha256"]),
        _gate("phase36_archive_verified_frames", archive_audit["verified_frames"], "==", 303),
        _gate("phase36_neighbor_frames_reproduced", len(phase36_states["baseline"]), "==", 17),
        _gate("all_variant_source_changed_frames", [changed_frames[name]["source"] for name in ("crease_only", "mask_only", "combined")], "==", [[focus_source], [focus_source], [focus_source]]),
        _gate("all_variant_phase36_changed_frames", [changed_frames[name]["phase36"] for name in ("crease_only", "mask_only", "combined")], "==", [[focus_output], [focus_output], [focus_output]]),
        _gate("crease_mask_disjoint_from_sclera_expansion", int((crease_mask & leak_mask).sum()), "==", 0),
        _gate("crease_only_native_diff_outside_crease", difference_audit["crease_only"]["native_changed_outside_allowed_support"], "==", 0),
        _gate("mask_only_native_diff_outside_machine_candidate", difference_audit["mask_only"]["native_changed_outside_allowed_support"], "==", 0),
        _gate("combined_native_diff_outside_crease_plus_sclera", difference_audit["combined"]["native_changed_outside_allowed_support"], "==", 0),
        _gate("all_phase35_diffs_inside_transformed_support", sum(value["phase35_changed_outside_transformed_allowed_support"] for value in difference_audit.values()), "==", 0),
        _gate("all_phase36_diffs_inside_twice_transformed_support", sum(value["phase36_changed_outside_twice_transformed_allowed_support"] for value in difference_audit.values()), "==", 0),
        _gate("mask_effect_separable_from_crease_toggle", int(np.logical_xor(native_diffs["mask_only"], mask_delta_from_crease).sum()), "==", 0),
        _gate("actual_vs_planning_under_occluded_candidate_mask", actual_planning_mask_mismatch, "==", 0),
        _gate("machine_candidate_under_occluded_pixels", residual_before, "==", contract["diagnostic"]["expected_under_occluded_machine_candidate_pixels"]),
        _gate("new_hard_owner_pixels", hard_owner_additions, "==", contract["diagnostic"]["expected_new_hard_owner_pixels"]),
        _gate("existing_owner_alpha_strengthened_pixels", alpha_strengthened, "==", contract["diagnostic"]["expected_existing_owner_alpha_strengthened_pixels"]),
        _gate("owner_accounting_no_double_count", hard_owner_additions + alpha_strengthened, "==", residual_before),
        _gate("residual_machine_candidate_after_combined", residual_after, "==", 0),
        _gate("combined_minimum_machine_candidate_alpha", min(item["actual_compositor_alpha_and_owner"]["minimum_proposed_alpha_on_machine_candidate"] for item in owner_audit.values()), "==", 255),
        _gate("machine_candidate_final_owner_upper_or_lower", sum(item["actual_compositor_alpha_and_owner"]["candidate_pixels_with_non_lid_final_owner"] for item in owner_audit.values()), "==", 0),
        _gate("neutral_plate_fallback_pixels", sum(item["provenance"]["neutral_plate_fallback_pixels"] for item in owner_audit.values()), "==", 0),
        _gate("actual_registered_source_match_pixels", sum(item["provenance"]["source_matches_registered_texture_pixels"] for item in owner_audit.values()), "==", residual_before),
        _gate("actual_registered_patch_coordinate_pixels", sum(item["provenance"]["inside_authored_registered_patch_pixels"] for item in owner_audit.values()), "==", residual_before),
        _gate("actual_lid_source_call_count", [item["actual_compositor_alpha_and_owner"]["source_call_count"] for item in owner_audit.values()], "==", [2, 2]),
        _gate("mask_only_protected_non_candidate_rgb_delta", int((native_diffs["mask_only"] & protected_mask).sum()), "==", 0),
        _gate("combined_vs_crease_protected_non_candidate_rgb_delta", int((mask_delta_from_crease & protected_mask).sum()), "==", 0),
        _gate("disputed_canthus_preserved_native", int((native_diffs["combined"] & disputed_canthus_mask).sum()), "==", 0),
        _gate("v2_filled_comparator_diff_is_only_disputed_canthus", int(np.logical_xor(
            np.any(canthus_filled_native != native_states["combined"][focus_source], axis=2),
            disputed_canthus_mask,
        ).sum()), "==", 0),
        _gate("v2_filled_comparator_phase36_hash", _raw_frame_hash(canthus_filled_phase36), "==", phase37_v2_report["four_state_variants"]["combined"]["phase36_f248_rgb_sha256"]),
        _gate("v2_filled_comparator_camera_unchanged", canthus_filled_transform, "==", transform_evidence[focus_output]),
        _gate("diagnostic_fringe_write_pixels", int((native_diffs["mask_only"] & fringe_mask).sum()), "==", 0),
        _gate("combined_lid_area_counts_new_owners_once", combined_lid_areas, "==", expected_combined_lid_areas),
        _gate("combined_iris_occlusion_left", evidence_states["combined"][focus_source]["iris_occlusion_ratios"][0], "==", 1.0),
        _gate("combined_iris_occlusion_right", evidence_states["combined"][focus_source]["iris_occlusion_ratios"][1], "==", 1.0),
        _gate("proposed_owner_components", [item["topology_and_authored_geometry"]["components_8_connected"] for item in owner_audit.values()], "==", [1, 1]),
        _gate("proposed_owner_holes", [item["topology_and_authored_geometry"]["holes"] for item in owner_audit.values()], "==", [0, 0]),
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
        native_focus_states = {
            name: frames[focus_source] for name, frames in native_states.items()
        }
        phase36_focus_states = {
            name: frames[focus_output] for name, frames in phase36_states.items()
        }
        for scale in (1, 2, 3):
            _four_state_comparison(native_focus_states, native_box, scale, "F173 NATIVE").save(
                stage / f"{native_stem}-{scale}x.png"
            )
            _four_state_comparison(phase36_focus_states, phase36_box, scale, "F248 PHASE36").save(
                stage / f"{phase36_stem}-{scale}x.png"
            )
        _neighbor_sweep(
            phase36_states["baseline"], phase36_states["combined"], phase36_box,
        ).save(
            stage / str(contract["output"]["phase36_sequence_filename"])
        )
        _actual_map_decomposition(
            prepared.face.plate,
            prepared.face.phase33_base.lid_texture,
            list(baseline_eye_calls.values()),
            list(combined_eye_calls.values()),
            sclera,
            native_focus_states["combined"],
            native_box,
        ).save(stage / str(contract["output"]["layer_decomposition_filename"])
        )
        _comparison(
            canthus_filled_phase36,
            phase36_focus_states["combined"],
            phase36_box,
            3,
            "V2 DISPUTED CANTHUS FILLED (NO-GO)",
            "V3 DISPUTED CANTHUS PRESERVED (RECOMMENDED FOR REVIEW)",
        ).save(stage / str(contract["output"]["canthus_comparison_filename"]))

        artifacts = _artifact_inventory(stage)
        variants_report: dict[str, Any] = {}
        for variant in variant_config:
            variants_report[variant] = {
                "configuration": {
                    "suppress_fixed_crease": variant_config[variant][0],
                    "expand_machine_classified_sclera_candidate": variant_config[variant][1],
                },
                "phase35_f173_rgb_sha256": _raw_frame_hash(source_states[variant][focus_source]),
                "phase35_f173_native_rgb_sha256": _raw_frame_hash(native_states[variant][focus_source]),
                "phase36_f248_rgb_sha256": _raw_frame_hash(phase36_states[variant][focus_output]),
                "phase35_f173_evidence": evidence_states[variant][focus_source],
                "changed_frames_vs_baseline": changed_frames.get(variant, {"source": [], "phase36": []}),
                "write_audit": _public_write_audit(variant_audits[variant]),
                "difference_vs_baseline": difference_audit.get(variant),
            }
        report = {
            "report_version": 3,
            "diagnostic_id": "phase37_eyelid_occlusion_diagnostic_v3",
            "status": "MACHINE_CANTHUS_PRESERVING_DIAGNOSTIC_PASSED_HUMAN_ALIGNMENT_REVIEW_REQUIRED",
            "machine_passed": True,
            "human_visual_acceptance_required": True,
            "scope": "still-only F173/F248 baseline, crease-only, mask-only, and canthus-preserving combined isolation with captured compositor maps and actual Phase36 F240-F256 neighbor sweep",
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
                "predecessor_commit_sha": contract["predecessor"]["commit_sha"],
                "phase37_v1_machine_report_sha256": _sha256(_repo_path(contract["locks"]["phase37_v1_machine_report"]["path"])),
                "phase37_v2_contract_sha256": _sha256(_repo_path(contract["locks"]["phase37_v2_contract"]["path"])),
                "phase37_v2_machine_report_sha256": _sha256(_repo_path(contract["locks"]["phase37_v2_machine_report"]["path"])),
                "predecessor_byte_snapshot_policy": contract["diagnostic"]["byte_snapshot"],
                "phase36_candidate01_manifest_sha256": _sha256(_repo_path(contract["locks"]["phase36_candidate01_manifest"]["path"])),
                "phase36_candidate01_rejection_receipt_sha256": _sha256(_repo_path(contract["locks"]["phase36_candidate01_rejection_receipt"]["path"])),
                "phase36_archive": archive_audit,
            },
            "baseline": {
                "phase35_f173_rgb_sha256": _raw_frame_hash(source_states["baseline"][focus_source]),
                "phase35_f173_native_rgb_sha256": _raw_frame_hash(native_states["baseline"][focus_source]),
                "phase35_f173_evidence": evidence_states["baseline"][focus_source],
                "phase35_source_frame_hashes": [
                    {"frame": frame, "rgb_sha256": _raw_frame_hash(source_states["baseline"][frame])}
                    for frame in source_frames
                ],
                "phase36_frame_hashes": [
                    {"frame": frame, "rgb_sha256": _raw_frame_hash(phase36_states["baseline"][frame])}
                    for frame in phase36_frames
                ],
            },
            "four_state_variants": variants_report,
            "combined_proposal": {
                "description": contract["diagnostic"]["proposal"],
                "phase35_f173_rgb_sha256": _raw_frame_hash(source_states["combined"][focus_source]),
                "phase35_f173_native_rgb_sha256": _raw_frame_hash(native_states["combined"][focus_source]),
                "phase36_f248_rgb_sha256": _raw_frame_hash(phase36_states["combined"][focus_output]),
                "phase35_changed_frames": changed_frames["combined"]["source"],
                "phase36_changed_frames": changed_frames["combined"]["phase36"],
                "disputed_medial_canthus_policy": "PRESERVED; V2 fill remains NO-GO without James ratification",
            },
            "v2_filled_visual_comparator": {
                "disposition": "DIAGNOSTIC_NO_GO_FOR_REBUILD_AUTHORIZATION_NOT_INVALIDATED_EVIDENCE",
                "phase35_f173_rgb_sha256": _raw_frame_hash(canthus_filled_source),
                "phase36_f248_rgb_sha256": _raw_frame_hash(canthus_filled_phase36),
                "filled_disputed_canthus_pixels_native": int(disputed_canthus_mask.sum()),
                "write_audit": _public_write_audit(canthus_filled_audit),
            },
            "machine_candidate_owner_audit": {
                "classification_color_space": contract["diagnostic"]["sclera_classification"]["color_space"],
                "classification_status": contract["diagnostic"]["sclera_classification"]["status"],
                "under_occluded_machine_candidate_pixels": residual_before,
                "new_hard_owner_pixels": hard_owner_additions,
                "existing_hard_owner_alpha_strengthened_pixels": alpha_strengthened,
                "owner_accounting_sum": hard_owner_additions + alpha_strengthened,
                "residual_under_occluded_candidate_after": residual_after,
                "diagnostic_fringe_write_pixels": int((native_diffs["mask_only"] & fringe_mask).sum()),
                "disputed_canthus_pixels_preserved": int(disputed_canthus_mask.sum()),
                "per_eye": owner_audit,
            },
            "difference_audit": {
                "explicit_crease_support_pixels_native": int(crease_mask.sum()),
                "machine_candidate_pixels_native": int(core_mask.sum()),
                "under_occluded_machine_candidate_support_pixels_native": int(leak_mask.sum()),
                "one_px_diagnostic_fringe_pixels_native": int(fringe_mask.sum()),
                "protected_non_candidate_pixels_native": int(protected_mask.sum()),
                "disputed_canthus_pixels_native": int(disputed_canthus_mask.sum()),
                "crease_candidate_overlap_pixels": int((crease_mask & leak_mask).sum()),
                "per_variant": difference_audit,
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
        report_bytes = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")
        _require_equal(b"\r\n" in report_bytes, False, "V3 report explicit LF byte domain")
        report_path.write_bytes(report_bytes)
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
        "phase35_f173_baseline_sha256": _raw_frame_hash(source_states["baseline"][focus_source]),
        "phase36_f248_combined_sha256": _raw_frame_hash(phase36_states["combined"][focus_output]),
        "under_occluded_machine_candidate_pixels": residual_before,
        "new_hard_owner_pixels": hard_owner_additions,
        "existing_owner_alpha_strengthened_pixels": alpha_strengthened,
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
