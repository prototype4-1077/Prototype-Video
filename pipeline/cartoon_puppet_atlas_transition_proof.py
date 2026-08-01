"""Bounded June puppet-atlas rig proof for Phase 29 frames 88--94."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from pipeline.cartoon_deformable_performance_3q import (
    _registered_point,
    load_deformable_performance_contract,
)
from pipeline.cartoon_pose_layers import load_pose_layer_contract, registered_pose_layer
from pipeline.cartoon_topology_transition_proof import (
    _alpha_iou,
    _checkerboard,
    _component_metrics,
    _frame_change_metrics,
    _minimum_mask_distance,
    _over,
    _premultiplied,
    _premultiplied_to_rgba,
    _similarity_affine,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PROOF_FRAMES = tuple(range(88, 95))


@dataclass(frozen=True)
class AtlasComponent:
    identifier: str
    bbox: tuple[int, int, int, int]
    rgba: np.ndarray
    source_bone: tuple[np.ndarray, np.ndarray]
    target_bone: tuple[str, str]
    proximal_underlap_px: float
    distal_underlap_px: float
    depth: int


@dataclass(frozen=True)
class AtlasProofInputs:
    contract_path: Path
    contract: dict[str, Any]
    atlas_rgba: np.ndarray
    atlas_substantial_component_count: int
    atlas_component_labels: dict[str, int]
    components: tuple[AtlasComponent, ...]
    start_landmarks: dict[str, np.ndarray]
    end_landmarks: dict[str, np.ndarray]
    pose75_rgba: np.ndarray
    porch_rgb: np.ndarray


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pinned_path(specification: dict[str, Any], label: str) -> Path:
    path = (REPO_ROOT / str(specification.get("path", ""))).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{label} is missing: {path}")
    actual = _sha256(path)
    expected = str(specification.get("sha256", ""))
    if actual != expected:
        raise ValueError(f"{label} SHA-256 mismatch: {actual} != {expected}")
    return path


def _substantial_components(alpha: np.ndarray, threshold: int, minimum_area: int) -> tuple[int, np.ndarray, np.ndarray]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(np.asarray(alpha > threshold, dtype=np.uint8), 8)
    substantial = [index for index in range(1, count) if int(stats[index, cv2.CC_STAT_AREA]) >= minimum_area]
    remapped = np.zeros_like(labels, dtype=np.int16)
    for output_label, source_label in enumerate(substantial, start=1):
        remapped[labels == source_label] = output_label
    return len(substantial), remapped, stats


def _registered_landmarks(
    anchor: dict[str, Any],
    pose: dict[str, Any],
    registration: dict[str, Any],
    order: list[str],
) -> dict[str, np.ndarray]:
    return {
        identifier: _registered_point(anchor["landmarks"][identifier], pose, registration)
        for identifier in order
    }


def load_puppet_atlas_contract(contract_path: str | Path) -> AtlasProofInputs:
    contract_file = Path(contract_path).resolve()
    contract = json.loads(contract_file.read_text(encoding="utf-8"))
    if int(contract.get("contract_version", 0)) != 1:
        raise ValueError("unsupported puppet atlas contract version")
    if contract.get("asset_id") != "june_oxley_puppet_atlas_v1" or contract.get("character_id") != "june_oxley":
        raise ValueError("puppet atlas identity boundary changed")
    if contract.get("cash_cost") != 0 or contract.get("paid_runtime_dependency") is not False:
        raise ValueError("puppet atlas proof must remain zero cash")
    atlas_path = _pinned_path(contract["atlas"], "puppet atlas")
    phase29_path = _pinned_path(contract["phase29_target"], "Phase 29 target contract")
    atlas_image = Image.open(atlas_path).convert("RGBA")
    try:
        if atlas_image.size != (int(contract["atlas"]["width"]), int(contract["atlas"]["height"])):
            raise ValueError("puppet atlas dimensions changed")
        atlas_rgba = np.asarray(atlas_image, dtype=np.uint8).copy()
    finally:
        atlas_image.close()
    component_count, labels, _ = _substantial_components(
        atlas_rgba[:, :, 3],
        int(contract["atlas"]["component_alpha_threshold"]),
        int(contract["atlas"]["minimum_substantial_area"]),
    )
    expected_count = int(contract["atlas"]["expected_substantial_connected_components"])
    if component_count != expected_count:
        raise ValueError(f"puppet atlas has {component_count} substantial components, expected {expected_count}")

    declared = contract["rig"]["components"]
    identifiers = [str(row["id"]) for row in declared]
    depths = [int(row["depth"]) for row in declared]
    if len(declared) != expected_count or len(set(identifiers)) != expected_count or len(set(depths)) != expected_count:
        raise ValueError("puppet atlas component ids and depths must be unique and complete")
    atlas_height, atlas_width = atlas_rgba.shape[:2]
    mapped_labels: dict[str, int] = {}
    components: list[AtlasComponent] = []
    for row in declared:
        identifier = str(row["id"])
        x, y, width, height = (int(value) for value in row["bbox"])
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > atlas_width or y + height > atlas_height:
            raise ValueError(f"{identifier} bbox leaves the atlas")
        crop = atlas_rgba[y:y + height, x:x + width].copy()
        crop_labels = labels[y:y + height, x:x + width]
        values, counts = np.unique(crop_labels[crop_labels > 0], return_counts=True)
        if not len(values):
            raise ValueError(f"{identifier} bbox does not contain a substantial component")
        mapped_labels[identifier] = int(values[int(np.argmax(counts))])
        source_bone = tuple(np.asarray(point, dtype=np.float32) for point in row["source_bone"])
        for point in source_bone:
            if not 0 <= point[0] < width or not 0 <= point[1] < height:
                raise ValueError(f"{identifier} source socket leaves its crop")
        components.append(
            AtlasComponent(
                identifier=identifier,
                bbox=(x, y, width, height),
                rgba=crop,
                source_bone=(source_bone[0], source_bone[1]),
                target_bone=(str(row["target_bone"][0]), str(row["target_bone"][1])),
                proximal_underlap_px=float(row["underlap"]["proximal"]),
                distal_underlap_px=float(row["underlap"]["distal"]),
                depth=int(row["depth"]),
            )
        )
        if not 0.0 <= components[-1].proximal_underlap_px <= 10.0 or not 0.0 <= components[-1].distal_underlap_px <= 10.0:
            raise ValueError(f"{identifier} underlap override leaves the calibrated zero-to-ten-pixel range")
    if len(set(mapped_labels.values())) != expected_count:
        raise ValueError("declared atlas boxes do not map one-to-one to the 14 substantial components")

    phase29, assets = load_deformable_performance_contract(phase29_path)
    control, background_path, _ = load_pose_layer_contract(assets["gs030_control"])
    pose_by_id = {str(row["id"]): row for row in control["poses"]}
    anchor_by_progress = {
        float(row["progress"]): row for row in phase29["runtime_asset_pack"]["corrective_sources"]
    }
    order = [str(value) for value in phase29["runtime_asset_pack"]["landmark_order"]]
    start_anchor = anchor_by_progress[float(contract["phase29_target"]["start_corrective_progress"])]
    end_anchor = anchor_by_progress[float(contract["phase29_target"]["target_corrective_progress"])]
    start_pose = pose_by_id[str(start_anchor["pose_id"])]
    end_pose = pose_by_id[str(end_anchor["pose_id"])]
    start_landmarks = _registered_landmarks(start_anchor, start_pose, control["contact_registration"], order)
    end_landmarks = _registered_landmarks(end_anchor, end_pose, control["contact_registration"], order)
    end_source = Image.open(assets[str(end_anchor["source_role"])]).convert("RGBA")
    try:
        end_registered, _ = registered_pose_layer(end_source, end_pose, control["contact_registration"])
    finally:
        end_source.close()
    pose75_rgba = np.asarray(end_registered, dtype=np.uint8).copy()
    end_registered.close()
    background = Image.open(background_path).convert("RGB")
    try:
        porch_rgb = np.asarray(background, dtype=np.uint8).copy()
    finally:
        background.close()
    return AtlasProofInputs(
        contract_path=contract_file,
        contract=contract,
        atlas_rgba=atlas_rgba,
        atlas_substantial_component_count=component_count,
        atlas_component_labels=mapped_labels,
        components=tuple(sorted(components, key=lambda value: value.depth)),
        start_landmarks=start_landmarks,
        end_landmarks=end_landmarks,
        pose75_rgba=pose75_rgba,
        porch_rgb=porch_rgb,
    )


def _ease(value: float) -> float:
    value = min(1.0, max(0.0, float(value)))
    return value * value * (3.0 - 2.0 * value)


def _landmarks_at(inputs: AtlasProofInputs, frame: int) -> dict[str, np.ndarray]:
    amount = _ease((frame - PROOF_FRAMES[0]) / (PROOF_FRAMES[-1] - PROOF_FRAMES[0]))
    landmarks = {
        identifier: inputs.start_landmarks[identifier] * (1.0 - amount) + inputs.end_landmarks[identifier] * amount
        for identifier in inputs.start_landmarks
    }
    left_direction = landmarks["left_hand"] - landmarks["left_elbow"]
    left_direction /= max(float(np.linalg.norm(left_direction)), 1e-6)
    landmarks["left_hand_tip"] = landmarks["left_hand"] + left_direction * 72.0
    return landmarks


def _underlap_target_bone(
    component: AtlasComponent,
    target_start: np.ndarray,
    target_end: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    vector = target_end - target_start
    unit = vector / max(float(np.linalg.norm(vector)), 1e-6)
    return (
        target_start - unit * component.proximal_underlap_px,
        target_end + unit * component.distal_underlap_px,
    )


def render_atlas_frame(inputs: AtlasProofInputs, frame: int) -> tuple[np.ndarray, dict[str, Any]]:
    if frame not in PROOF_FRAMES:
        raise ValueError("atlas proof frame must be 88 through 94")
    landmarks = _landmarks_at(inputs, frame)
    width = int(inputs.contract["output"]["source_width"])
    height = int(inputs.contract["output"]["source_height"])
    canvas = np.zeros((height, width, 4), dtype=np.float32)
    component_alphas: dict[str, np.ndarray] = {}
    determinants: dict[str, float] = {}
    mapping_residuals: dict[str, list[float]] = {}
    authored_socket_offsets: dict[str, list[float]] = {}
    for component in inputs.components:
        intended_start = landmarks[component.target_bone[0]]
        intended_end = landmarks[component.target_bone[1]]
        render_start, render_end = _underlap_target_bone(component, intended_start, intended_end)
        matrix, determinant = _similarity_affine(
            component.source_bone[0],
            component.source_bone[1],
            render_start,
            render_end,
        )
        warped = cv2.warpAffine(
            _premultiplied(component.rgba),
            matrix,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0.0, 0.0, 0.0, 0.0),
        )
        warped = np.clip(warped, 0.0, 1.0)
        canvas = _over(canvas, warped)
        component_alphas[component.identifier] = np.round(warped[:, :, 3] * 255.0).astype(np.uint8)
        determinants[component.identifier] = determinant
        rendered_start = matrix[:, :2] @ component.source_bone[0] + matrix[:, 2]
        rendered_end = matrix[:, :2] @ component.source_bone[1] + matrix[:, 2]
        mapping_residuals[component.identifier] = [
            float(np.linalg.norm(rendered_start - render_start)),
            float(np.linalg.norm(rendered_end - render_end)),
        ]
        authored_socket_offsets[component.identifier] = [
            float(np.linalg.norm(render_start - intended_start)),
            float(np.linalg.norm(render_end - intended_end)),
        ]
    return _premultiplied_to_rgba(canvas), {
        "frame": frame,
        "landmarks": landmarks,
        "component_alphas": component_alphas,
        "determinants": determinants,
        "mapping_residuals_to_extended_target_px": mapping_residuals,
        "authored_socket_offsets_due_to_underlap_px": authored_socket_offsets,
    }


def evaluate_atlas_transition(inputs: AtlasProofInputs) -> tuple[dict[str, Any], dict[int, np.ndarray], dict[int, dict[str, Any]]]:
    frames: dict[int, np.ndarray] = {}
    details: dict[int, dict[str, Any]] = {}
    for frame in PROOF_FRAMES:
        frames[frame], details[frame] = render_atlas_frame(inputs, frame)
    contact_ids = [str(value) for value in inputs.contract["rig"]["contact_components"]]
    contact_metrics: dict[str, dict[str, Any]] = {}
    mapping_residuals: list[float] = []
    authored_socket_offsets: list[float] = []
    determinants: list[float] = []
    maximum_gap = 0.0
    overlap_rows: list[dict[str, Any]] = []
    for frame in PROOF_FRAMES:
        detail = details[frame]
        mapping_residuals.extend(value for values in detail["mapping_residuals_to_extended_target_px"].values() for value in values)
        authored_socket_offsets.extend(value for values in detail["authored_socket_offsets_due_to_underlap_px"].values() for value in values)
        determinants.extend(detail["determinants"].values())
        alphas = detail["component_alphas"]
        for identifier in contact_ids:
            metric = _component_metrics(alphas[identifier])
            previous = contact_metrics.get(identifier)
            if previous is None:
                contact_metrics[identifier] = {
                    "maximum_significant_count": metric["significant_count"],
                    "minimum_dominant_fraction": metric["dominant_fraction"],
                    "minimum_alpha_area": metric["alpha_area"],
                }
            else:
                previous["maximum_significant_count"] = max(previous["maximum_significant_count"], metric["significant_count"])
                previous["minimum_dominant_fraction"] = min(previous["minimum_dominant_fraction"], metric["dominant_fraction"])
                previous["minimum_alpha_area"] = min(previous["minimum_alpha_area"], metric["alpha_area"])
        adjacent_overlap = 0
        adjacent_union = 0
        for left_id, right_id in inputs.contract["rig"]["joint_pairs"]:
            left = alphas[str(left_id)]
            right = alphas[str(right_id)]
            maximum_gap = max(maximum_gap, _minimum_mask_distance(left, right))
            left_mask, right_mask = left > 8, right > 8
            adjacent_overlap += int(np.count_nonzero(left_mask & right_mask))
            adjacent_union += int(np.count_nonzero(left_mask | right_mask))
        overlap_rows.append({"frame": frame, "adjacent_joint_overlap_fraction": adjacent_overlap / max(1, adjacent_union)})
    changes = []
    temporal_iou = []
    for left, right in zip(PROOF_FRAMES, PROOF_FRAMES[1:]):
        row = _frame_change_metrics(frames[left], frames[right])
        row["from_frame"] = left
        row["to_frame"] = right
        changes.append(row)
        temporal_iou.append(_alpha_iou(frames[left][:, :, 3], frames[right][:, :, 3]))
    final_alpha = frames[94][:, :, 3]
    target_alpha = inputs.pose75_rgba[:, :, 3]
    final_area = int(np.count_nonzero(final_alpha > 8))
    target_area = int(np.count_nonzero(target_alpha > 8))
    final_components, _, _ = _substantial_components(final_alpha, 8, 500)
    silhouette = {
        "alpha_iou_to_pose75": _alpha_iou(final_alpha, target_alpha),
        "alpha_area_ratio_to_pose75": final_area / max(1, target_area),
        "substantial_connected_components": final_components,
        "human_readability_status": "unevaluated",
    }
    gates = inputs.contract["gates"]
    machine_passed = (
        inputs.atlas_substantial_component_count == int(inputs.contract["atlas"]["expected_substantial_connected_components"])
        and max(mapping_residuals) <= float(gates["maximum_mapping_residual_to_extended_target_px"])
        and min(determinants) >= float(gates["minimum_affine_determinant"])
        and maximum_gap <= float(gates["maximum_joint_gap_px"])
        and max(value["maximum_significant_count"] for value in contact_metrics.values()) <= int(gates["maximum_contact_significant_components"])
        and min(value["minimum_dominant_fraction"] for value in contact_metrics.values()) >= float(gates["minimum_contact_dominant_fraction"])
        and min(temporal_iou) >= float(gates["minimum_temporal_alpha_iou"])
        and silhouette["alpha_iou_to_pose75"] >= float(gates["minimum_frame94_silhouette_iou_to_pose75"])
        and float(gates["minimum_frame94_alpha_area_ratio_to_pose75"]) <= silhouette["alpha_area_ratio_to_pose75"] <= float(gates["maximum_frame94_alpha_area_ratio_to_pose75"])
    )
    report = {
        "proof": "june_puppet_atlas_transition_88_94",
        "asset_id": inputs.contract["asset_id"],
        "frame_range": [88, 94],
        "atlas_integrity": {
            "substantial_connected_component_count": inputs.atlas_substantial_component_count,
            "expected_count": inputs.contract["atlas"]["expected_substantial_connected_components"],
            "one_to_one_bbox_component_mapping": len(set(inputs.atlas_component_labels.values())) == len(inputs.components),
            "mapped_component_labels": inputs.atlas_component_labels,
        },
        "source_policy": "single immutable atlas crop per rig component; no corrective-pose pixels",
        "component_count": len(inputs.components),
        "fixed_depth_order": [component.identifier for component in inputs.components],
        "mechanics": {
            "maximum_mapping_residual_to_extended_target_px": max(mapping_residuals),
            "maximum_authored_socket_offset_due_to_underlap_px": max(authored_socket_offsets),
            "minimum_affine_determinant": min(determinants),
            "maximum_joint_gap_px": maximum_gap,
            "per_frame_joint_overlap": overlap_rows,
            "default_joint_underlap_pixels": inputs.contract["rig"]["joint_underlap_pixels"],
            "per_component_underlap": {
                component.identifier: {
                    "proximal": component.proximal_underlap_px,
                    "distal": component.distal_underlap_px,
                }
                for component in inputs.components
            },
        },
        "contact_coherence": contact_metrics,
        "temporal_continuity": {
            "minimum_adjacent_frame_alpha_iou": min(temporal_iou),
            "per_frame_changed_pixel_and_mae": changes,
            "maximum_changed_pixel_fraction_subject_union": max(row["changed_pixel_fraction_subject_union"] for row in changes),
            "maximum_mean_absolute_error_subject_union": max(row["mean_absolute_error_subject_union"] for row in changes),
        },
        "frame94_silhouette": silhouette,
        "gates": gates,
        "machine_passed": machine_passed,
        "promotion_scope": inputs.contract["promotion_scope"],
        "cash_cost": 0,
        "paid_runtime_dependency": False,
    }
    return report, frames, details


def _transparent_review(rgba: np.ndarray, frame: int, size: tuple[int, int]) -> Image.Image:
    foreground = Image.fromarray(rgba, mode="RGBA")
    matte = _checkerboard(foreground.size).convert("RGBA")
    review = Image.alpha_composite(matte, foreground).convert("RGB").resize(size, Image.Resampling.LANCZOS)
    _label_review(review, f"FRAME {frame}  |  14-COMPONENT ATLAS RIG  |  TRANSPARENT")
    return review


def _porch_review(inputs: AtlasProofInputs, rgba: np.ndarray, frame: int, size: tuple[int, int]) -> Image.Image:
    porch = Image.fromarray(inputs.porch_rgb, mode="RGB").convert("RGBA")
    foreground = Image.fromarray(rgba, mode="RGBA")
    review = Image.alpha_composite(porch, foreground).convert("RGB").resize(size, Image.Resampling.LANCZOS)
    _label_review(review, f"FRAME {frame}  |  14-COMPONENT ATLAS RIG  |  PORCH CONTEXT")
    return review


def _label_review(image: Image.Image, label: str) -> None:
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=25)
    box = draw.textbbox((0, 0), label, font=font)
    draw.rectangle((28, 24, 52 + box[2], 41 + box[3]), fill=(12, 14, 18))
    draw.text((40, 31), label, fill=(244, 238, 220), font=font)


def _contact_sheet(images: dict[int, Image.Image], output: Path) -> None:
    sheet = Image.new("RGB", (1920, 540), (18, 20, 24))
    for index, (_, source) in enumerate(sorted(images.items())):
        image = source.copy()
        image.thumbnail((480, 270), Image.Resampling.LANCZOS)
        sheet.paste(image, ((index % 4) * 480, (index // 4) * 270))
        image.close()
    sheet.save(output, quality=94, subsampling=0)
    sheet.close()


def render_puppet_atlas_transition_proof(
    contract_path: str | Path,
    output_dir: str | Path,
    *,
    ffmpeg: str = "ffmpeg",
) -> dict[str, Any]:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    inputs = load_puppet_atlas_contract(contract_path)
    report, frames, _ = evaluate_atlas_transition(inputs)
    review_size = (int(inputs.contract["output"]["review_width"]), int(inputs.contract["output"]["review_height"]))
    transparent_reviews: dict[int, Image.Image] = {}
    porch_reviews: dict[int, Image.Image] = {}
    for frame, rgba in frames.items():
        Image.fromarray(rgba, mode="RGBA").save(output / f"atlas-rgba-{frame:03d}.png")
        transparent = _transparent_review(rgba, frame, review_size)
        porch = _porch_review(inputs, rgba, frame, review_size)
        transparent_reviews[frame] = transparent
        porch_reviews[frame] = porch
        transparent.save(output / f"atlas-transparent-{frame:03d}.png")
        porch.save(output / f"atlas-porch-{frame:03d}.png")
    transparent_sheet = output / "june-puppet-atlas-transparent-contact-sheet.jpg"
    porch_sheet = output / "june-puppet-atlas-porch-contact-sheet.jpg"
    _contact_sheet(transparent_reviews, transparent_sheet)
    _contact_sheet(porch_reviews, porch_sheet)

    executable = str(Path(ffmpeg).resolve()) if Path(ffmpeg).is_file() else shutil.which(ffmpeg)
    if not executable:
        raise FileNotFoundError(f"ffmpeg executable not found: {ffmpeg}")
    video = output / "june-puppet-atlas-transition-proof.mp4"
    hold = int(inputs.contract["output"]["encoded_hold_frames_per_pose"])
    fps = int(inputs.contract["output"]["fps"])
    result = subprocess.run(
        [
            executable, "-y", "-v", "error", "-framerate", str(fps / hold),
            "-start_number", str(PROOF_FRAMES[0]), "-i", str(output / "atlas-porch-%03d.png"),
            "-vf", f"fps={fps}", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
            "-pix_fmt", str(inputs.contract["output"]["pixel_format"]), str(video),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(f"atlas proof encode failed: {result.stderr.strip()}")
    for image in [*transparent_reviews.values(), *porch_reviews.values()]:
        image.close()
    report.update(
        {
            "transparent_contact_sheet": transparent_sheet.name,
            "porch_contact_sheet": porch_sheet.name,
            "video": video.name,
            "transparent_review_frames": [f"atlas-transparent-{frame:03d}.png" for frame in PROOF_FRAMES],
            "porch_review_frames": [f"atlas-porch-{frame:03d}.png" for frame in PROOF_FRAMES],
        }
    )
    report_path = output / "june-puppet-atlas-transition-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render June's bounded 14-component puppet-atlas proof")
    parser.add_argument("contract")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    print(json.dumps(render_puppet_atlas_transition_proof(args.contract, args.output_dir, ffmpeg=args.ffmpeg), indent=2))


if __name__ == "__main__":
    main()
