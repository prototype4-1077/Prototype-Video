"""Bounded seated-to-standing dual-atlas proof for June, frames 64--100."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from pipeline.cartoon_puppet_atlas_performance import (
    AtlasPerformanceRenderer,
    FPS,
    OUTPUT_SIZE,
    RENDER_SCALE,
    _alpha_iou,
    _scaled_target_bone,
)
from pipeline.cartoon_puppet_atlas_transition_proof import (
    AtlasComponent,
    _component_metrics,
    _minimum_mask_distance,
    _over,
    _premultiplied,
    _premultiplied_to_rgba,
    _similarity_affine,
    _substantial_components,
)
from pipeline.cartoon_shot_sequence import _camera_frame


REPO_ROOT = Path(__file__).resolve().parents[1]
TRANSITION_FRAMES = tuple(range(64, 101))
REVIEW_FRAMES = (64, 66, 68, 70, 71, 74, 78, 79, 82, 86, 87, 90, 91, 94, 95, 96, 98, 100)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pinned_path(specification: dict[str, Any], label: str) -> Path:
    path = (REPO_ROOT / str(specification["path"])).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    actual = _sha256(path)
    if actual != str(specification["sha256"]):
        raise ValueError(f"{label} SHA-256 mismatch: {actual}")
    return path


def _ease(value: float) -> float:
    value = min(1.0, max(0.0, float(value)))
    return value * value * (3.0 - 2.0 * value)


def _transition_weight(contract: dict[str, Any], frame: int) -> float:
    start = int(contract["proof"]["seated_hold_end_frame"])
    end = int(contract["proof"]["standing_only_start_frame"])
    if frame <= start:
        return 0.0
    if frame >= end:
        return 1.0
    return _ease((frame - start) / (end - start))


def _apply_center_mask(crop: np.ndarray, row: dict[str, Any]) -> np.ndarray:
    polygon = row.get("center_mask_polygon")
    if not polygon:
        return crop
    mask = np.zeros(crop.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [np.asarray(polygon, dtype=np.int32)], 255)
    feather = int(row.get("mask_feather_px", 0))
    if feather:
        size = feather * 2 + 1
        mask = cv2.GaussianBlur(mask, (size, size), feather / 2.0)
    result = crop.copy()
    result[:, :, 3] = np.round(result[:, :, 3].astype(np.float32) * (mask.astype(np.float32) / 255.0)).astype(np.uint8)
    return result


def _retain_largest_alpha_component(crop: np.ndarray, threshold: int = 8) -> np.ndarray:
    """Remove atlas-box spill while retaining the dominant authored part."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        np.asarray(crop[:, :, 3] > threshold, dtype=np.uint8), 8
    )
    if count <= 2:
        return crop
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    keep = cv2.dilate(np.asarray(labels == largest, dtype=np.uint8), np.ones((3, 3), np.uint8)) > 0
    result = crop.copy()
    result[~keep] = 0
    return result


def _extend_component_at_socket(
    premultiplied: np.ndarray,
    socket: np.ndarray,
    radius: int,
    extension: int,
) -> np.ndarray:
    """Propagate existing painted pixels a few pixels inside one joint ROI."""
    if radius <= 0 or extension <= 0:
        return premultiplied
    height, width = premultiplied.shape[:2]
    yy, xx = np.ogrid[:height, :width]
    roi = (xx - float(socket[0])) ** 2 + (yy - float(socket[1])) ** 2 <= float(radius * radius)
    result = premultiplied.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    for _ in range(extension):
        old_alpha = result[:, :, 3]
        expanded_alpha = cv2.dilate(old_alpha, kernel)
        new_pixels = roi & (old_alpha <= (8.0 / 255.0)) & (expanded_alpha > (8.0 / 255.0))
        if not np.any(new_pixels):
            break
        for channel in range(4):
            expanded_channel = cv2.dilate(result[:, :, channel], kernel)
            result[:, :, channel][new_pixels] = expanded_channel[new_pixels]
    return np.clip(result, 0.0, 1.0)


def load_seated_atlas_contract(contract_path: str | Path) -> tuple[dict[str, Any], tuple[AtlasComponent, ...], int]:
    contract_file = Path(contract_path).resolve()
    contract = json.loads(contract_file.read_text(encoding="utf-8"))
    if contract.get("asset_id") != "june_oxley_puppet_atlas_seated_v1" or int(contract.get("contract_version", 0)) != 1:
        raise ValueError("unsupported seated atlas contract")
    if contract.get("cash_cost") != 0 or contract.get("paid_runtime_dependency") is not False:
        raise ValueError("dual atlas proof must remain zero cash")
    atlas_path = _pinned_path(contract["atlas"], "seated puppet atlas")
    _pinned_path(contract["standing_atlas_contract"], "standing atlas contract")
    _pinned_path(contract["phase29_target"], "Phase 29 performance contract")
    image = Image.open(atlas_path).convert("RGBA")
    try:
        rgba = np.asarray(image, dtype=np.uint8).copy()
    finally:
        image.close()
    if rgba.shape != (1024, 1536, 4):
        raise ValueError("seated atlas dimensions changed")
    count, labels, _ = _substantial_components(
        rgba[:, :, 3],
        int(contract["atlas"]["component_alpha_threshold"]),
        int(contract["atlas"]["minimum_substantial_area"]),
    )
    if count != int(contract["atlas"]["expected_substantial_connected_components"]):
        raise ValueError("seated atlas must retain exactly 14 substantial components")
    mapped_labels: list[int] = []
    components: list[AtlasComponent] = []
    for row in contract["components"]:
        x, y, width, height = (int(value) for value in row["bbox"])
        crop = rgba[y:y + height, x:x + width].copy()
        crop_labels = labels[y:y + height, x:x + width]
        values, counts = np.unique(crop_labels[crop_labels > 0], return_counts=True)
        if not len(values):
            raise ValueError(f"{row['id']} bbox contains no substantial component")
        mapped_labels.append(int(values[int(np.argmax(counts))]))
        crop = _apply_center_mask(crop, row)
        if bool(row.get("retain_largest_alpha_component", False)):
            crop = _retain_largest_alpha_component(crop)
        source = tuple(np.asarray(point, dtype=np.float32) for point in row["source_bone"])
        components.append(
            AtlasComponent(
                identifier=str(row["id"]),
                bbox=(x, y, width, height),
                rgba=crop,
                source_bone=(source[0], source[1]),
                target_bone=(str(row["target_bone"][0]), str(row["target_bone"][1])),
                proximal_underlap_px=float(row["underlap"]["proximal"]),
                distal_underlap_px=float(row["underlap"]["distal"]),
                depth=int(row["depth"]),
            )
        )
    if len(components) != 14 or len(set(mapped_labels)) != 14:
        raise ValueError("seated component boxes must map one-to-one to the alpha components")
    if {component.identifier for component in components} != {str(row["id"]) for row in contract["components"]}:
        raise ValueError("seated atlas component ids changed")
    return contract, tuple(sorted(components, key=lambda component: component.depth)), count


class DualAtlasRenderer:
    def __init__(self, seated_contract_path: str | Path):
        self.contract, self.seated_components, self.seated_component_count = load_seated_atlas_contract(seated_contract_path)
        standing_path = (REPO_ROOT / str(self.contract["standing_atlas_contract"]["path"])).resolve()
        self.base = AtlasPerformanceRenderer(standing_path)
        self.seated_by_id = {component.identifier: component for component in self.seated_components}
        self.standing_by_id = {component.identifier: component for component in self.base.atlas_inputs.components}
        if set(self.seated_by_id) != set(self.standing_by_id):
            raise ValueError("seated and standing atlas component interfaces differ")
        self.seated_sources = {
            identifier: _premultiplied(component.rgba)
            for identifier, component in self.seated_by_id.items()
        }
        cleanup = set(self.contract["topology_repairs"]["largest_component_source_cleanup"])
        if cleanup != {"right_forearm"}:
            raise ValueError("dual atlas source cleanup must remain bounded to right_forearm")
        self.standing_sources = {
            identifier: _premultiplied(
                _retain_largest_alpha_component(component.rgba)
                if identifier in cleanup else component.rgba
            )
            for identifier, component in self.standing_by_id.items()
        }
        self.socket_extensions = dict(self.contract["topology_repairs"]["joint_socket_extensions"])

    def close(self) -> None:
        self.base.close()

    def __enter__(self) -> "DualAtlasRenderer":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _warp_component(
        self,
        component: AtlasComponent,
        source: np.ndarray,
        landmarks: dict[str, np.ndarray],
    ) -> tuple[np.ndarray, float]:
        target_start, target_end = _scaled_target_bone(
            component,
            landmarks[component.target_bone[0]],
            landmarks[component.target_bone[1]],
        )
        matrix, determinant = _similarity_affine(
            component.source_bone[0], component.source_bone[1], target_start, target_end
        )
        warped = cv2.warpAffine(
            source,
            matrix,
            self.base.source_size,
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0.0, 0.0, 0.0, 0.0),
        )
        return np.clip(warped, 0.0, 1.0), determinant / (RENDER_SCALE * RENDER_SCALE)

    def _dual_character(
        self,
        frame: int,
        landmarks: dict[str, np.ndarray],
    ) -> tuple[np.ndarray, dict[str, Any]]:
        weight = _transition_weight(self.contract, frame)
        width, height = self.base.source_size
        canvas = np.zeros((height, width, 4), dtype=np.float32)
        part_alphas: dict[str, np.ndarray] = {}
        aligned_iou: dict[str, float] = {}
        double_components: dict[str, int] = {}
        double_edge: dict[str, float] = {}
        determinants: list[float] = []
        for standing_component in self.base.atlas_inputs.components:
            identifier = standing_component.identifier
            seated_component = self.seated_by_id[identifier]
            seated, seated_det = self._warp_component(
                seated_component, self.seated_sources[identifier], landmarks
            )
            standing, standing_det = self._warp_component(
                standing_component, self.standing_sources[identifier], landmarks
            )
            blended = seated * (1.0 - weight) + standing * weight
            socket_repair = self.socket_extensions.get(identifier)
            if socket_repair:
                blended = _extend_component_at_socket(
                    blended,
                    np.asarray(landmarks[str(socket_repair["joint"])], dtype=np.float32) * RENDER_SCALE,
                    int(socket_repair["radius_preview_px"]),
                    int(socket_repair["extension_preview_px"]),
                )
            canvas = _over(canvas, np.clip(blended, 0.0, 1.0))
            seated_alpha = np.round(seated[:, :, 3] * 255.0).astype(np.uint8)
            standing_alpha = np.round(standing[:, :, 3] * 255.0).astype(np.uint8)
            blended_alpha = np.round(np.clip(blended[:, :, 3], 0.0, 1.0) * 255.0).astype(np.uint8)
            part_alphas[identifier] = blended_alpha
            aligned_iou[identifier] = _alpha_iou(seated_alpha, standing_alpha)
            component_count, _, _ = _substantial_components(blended_alpha, 8, 25)
            double_components[identifier] = component_count
            left_mask, right_mask = seated_alpha > 8, standing_alpha > 8
            union = left_mask | right_mask
            double_edge[identifier] = float(np.mean((left_mask ^ right_mask)[union])) if np.any(union) else 0.0
            determinants.extend((seated_det, standing_det))
        return _premultiplied_to_rgba(canvas), {
            "weight": weight,
            "part_alphas": part_alphas,
            "aligned_alpha_iou": aligned_iou,
            "blended_part_components": double_components,
            "double_edge_fraction": double_edge,
            "minimum_normalized_determinant": min(determinants),
        }

    def render_frame(self, frame: int) -> tuple[Image.Image, dict[str, Any]]:
        if frame != 1 and frame not in TRANSITION_FRAMES:
            raise ValueError("dual atlas proof supports frame 1 and frames 64 through 100")
        landmarks, state = self.base.target_landmarks(frame)
        character, dual = self._dual_character(frame, landmarks)
        component_alphas = dual["part_alphas"]
        composed = Image.alpha_composite(self.base.background.convert("RGBA"), self.base._contact_shadow())
        composed = Image.alpha_composite(composed, Image.fromarray(character, mode="RGBA"))
        chair_seat = bool(state["contacts"]["chair_seat"]["active"])
        chair_arm = bool(state["contacts"]["chair_hand"]["active"])
        if chair_seat:
            composed = Image.alpha_composite(composed, self.base.chair_seat_patch)
        if chair_arm:
            composed = Image.alpha_composite(composed, self.base.chair_arm_patch)
        steam_origin = np.asarray(landmarks["mug_center"], dtype=np.float32) * RENDER_SCALE
        steam_origin[1] -= 50.0 * RENDER_SCALE
        composed = self.base._steam(composed, steam_origin, frame)
        light_strength = float(self.base.phase_renderer.control["effects"]["light_breathe"]["strength"])
        factor = 1.0 + light_strength * math.sin((frame - 1) / FPS * math.pi * 0.71)
        composed = ImageEnhance.Brightness(composed.convert("RGB")).enhance(factor)
        output = _camera_frame(
            composed,
            self.base.phase_renderer.control["camera"],
            (frame - 1) / 170.0,
            OUTPUT_SIZE,
        )
        shoulder_knee_pairs = (
            ("left_upper_arm", "torso"), ("right_upper_arm", "torso"),
            ("left_thigh", "left_shin"), ("right_thigh", "right_shin"),
        )
        seam_gaps = {
            f"{left}__{right}": _minimum_mask_distance(component_alphas[left], component_alphas[right])
            for left, right in shoulder_knee_pairs
        }
        ankle_pairs = (("left_shin", "left_boot"), ("right_shin", "right_boot"))
        ankle_gaps = {
            f"{left}__{right}": _minimum_mask_distance(component_alphas[left], component_alphas[right])
            for left, right in ankle_pairs
        }
        contact_evidence = self.base._contact_evidence(state, landmarks, component_alphas)
        details = {
            "frame": frame,
            "state": state,
            "transition_weight": dual["weight"],
            "background_blended": False,
            "mug_hand_is_single_unit": "right_hand_mug" in component_alphas,
            "aligned_alpha_iou": dual["aligned_alpha_iou"],
            "blended_part_components": dual["blended_part_components"],
            "double_edge_fraction": dual["double_edge_fraction"],
            "minimum_normalized_determinant": dual["minimum_normalized_determinant"],
            "shoulder_knee_gaps_px": seam_gaps,
            "ankle_gaps_px": ankle_gaps,
            "contact_evidence": contact_evidence,
            "character_alpha": character[:, :, 3],
            "chair_context": {"arm_patch": chair_arm, "seat_patch": chair_seat},
        }
        return output, details


def _sheet(paths: dict[int, Path], output: Path) -> None:
    sheet = Image.new("RGB", (1920, 540), (18, 20, 24))
    font = ImageFont.load_default(size=18)
    for index, (frame, path) in enumerate(sorted(paths.items())):
        image = Image.open(path).convert("RGB")
        image.thumbnail((320, 180), Image.Resampling.LANCZOS)
        x, y = (index % 6) * 320, (index // 6) * 180
        sheet.paste(image, (x, y))
        ImageDraw.Draw(sheet).text((x + 8, y + 7), f"F{frame:03d}", font=font, fill=(255, 244, 225), stroke_width=2, stroke_fill=(10, 10, 10))
        image.close()
    sheet.save(output, quality=94, subsampling=0)
    sheet.close()


def render_dual_atlas_performance_proof(
    seated_contract_path: str | Path,
    output_dir: str | Path,
    *,
    ffmpeg: str = "ffmpeg",
) -> dict[str, Any]:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    review_dir = output / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)
    executable = str(Path(ffmpeg).resolve()) if Path(ffmpeg).is_file() else shutil.which(ffmpeg)
    if not executable:
        raise FileNotFoundError(f"ffmpeg executable not found: {ffmpeg}")
    video = output / "june-dual-atlas-transition-proof.mp4"
    process = subprocess.Popen(
        [
            executable, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", "960x540", "-r", "30", "-i", "-", "-an", "-c:v", "libx264",
            "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", str(video),
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    review_paths: dict[int, Path] = {}
    all_iou: dict[str, list[float]] = {}
    all_double_components: dict[str, int] = {}
    all_double_edge: dict[str, float] = {}
    maximum_seam_gap = 0.0
    maximum_ankle_gap = 0.0
    minimum_determinant = math.inf
    contact_errors: dict[str, list[float]] = {key: [] for key in ("left_boot", "right_boot", "chair_hand", "mug_hand", "mug_center")}
    previous_alpha: np.ndarray | None = None
    temporal_iou: list[float] = []
    endpoint_alpha: dict[int, np.ndarray] = {}
    try:
        with DualAtlasRenderer(seated_contract_path) as renderer:
            seated_image, seated_detail = renderer.render_frame(1)
            seated_path = output / "june-dual-atlas-frame001-seated-proof.png"
            seated_image.save(seated_path)
            seated_image.close()
            endpoint_alpha[1] = seated_detail["character_alpha"].copy()
            for frame in TRANSITION_FRAMES:
                image, detail = renderer.render_frame(frame)
                rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
                if process.stdin is None:
                    raise RuntimeError("dual atlas ffmpeg stdin closed")
                process.stdin.write(rgb.tobytes())
                if frame in REVIEW_FRAMES:
                    path = review_dir / f"frame_{frame:04d}.png"
                    image.save(path)
                    review_paths[frame] = path
                image.close()
                if 0.0 < detail["transition_weight"] < 1.0:
                    for identifier, value in detail["aligned_alpha_iou"].items():
                        all_iou.setdefault(identifier, []).append(float(value))
                    for identifier, value in detail["blended_part_components"].items():
                        all_double_components[identifier] = max(all_double_components.get(identifier, 0), int(value))
                    for identifier, value in detail["double_edge_fraction"].items():
                        all_double_edge[identifier] = max(all_double_edge.get(identifier, 0.0), float(value))
                maximum_seam_gap = max(maximum_seam_gap, *detail["shoulder_knee_gaps_px"].values())
                maximum_ankle_gap = max(maximum_ankle_gap, *detail["ankle_gaps_px"].values())
                minimum_determinant = min(minimum_determinant, float(detail["minimum_normalized_determinant"]))
                for identifier, evidence in detail["contact_evidence"].items():
                    if evidence["active"] and evidence["centroid_error_px"] is not None:
                        contact_errors[identifier].append(float(evidence["centroid_error_px"]))
                alpha = detail["character_alpha"]
                if previous_alpha is not None:
                    temporal_iou.append(_alpha_iou(previous_alpha, alpha))
                previous_alpha = alpha.copy()
                if frame == 100:
                    endpoint_alpha[100] = alpha.copy()
            if process.stdin is not None:
                process.stdin.close()
            stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr is not None else ""
            code = process.wait()
            if code:
                raise RuntimeError(f"dual atlas proof encode failed: {stderr.strip()}")
            seated_iou = _alpha_iou(endpoint_alpha[1], renderer.base.pose0_alpha)
            standing_iou = _alpha_iou(endpoint_alpha[100], renderer.base.pose100_alpha)
            seated_components, _, _ = _substantial_components(endpoint_alpha[1], 8, 125)
            standing_components, _, _ = _substantial_components(endpoint_alpha[100], 8, 125)
    except BaseException:
        if process.poll() is None:
            process.kill()
        raise
    sheet = output / "june-dual-atlas-transition-contact-sheet.jpg"
    _sheet(review_paths, sheet)
    per_part_min_iou = {identifier: min(values) for identifier, values in all_iou.items()}
    contact_p95 = {
        identifier: float(np.percentile(values, 95)) if values else None
        for identifier, values in contact_errors.items()
    }
    gates = renderer.contract["gates"]
    ghost_passed = (
        max(all_double_components.values()) <= int(gates["maximum_blended_part_components"])
        and max(all_double_edge.values()) <= float(gates["maximum_double_edge_fraction"])
        and min(per_part_min_iou.values()) >= float(gates["minimum_per_part_aligned_alpha_iou"])
    )
    machine_passed = (
        seated_iou >= float(gates["minimum_pose0_seated_silhouette_iou"])
        and standing_iou >= float(gates["minimum_pose100_standing_silhouette_iou"])
        and ghost_passed
        and maximum_seam_gap <= float(gates["maximum_shoulder_or_knee_gap_preview_px"])
        and maximum_ankle_gap <= float(gates["maximum_ankle_gap_preview_px"])
        and max(value for value in contact_p95.values() if value is not None) <= float(gates["maximum_contact_centroid_error_p95_preview_px"])
        and min(temporal_iou) >= float(gates["minimum_temporal_alpha_iou"])
        and minimum_determinant > float(gates["minimum_normalized_affine_determinant"])
    )
    report = {
        "proof": "june_dual_atlas_seated_to_standing_frames64_100",
        "delivery": {"width": 960, "height": 540, "fps": 30, "frame_count": 37},
        "source_policy": {
            "seated_and_standing_components_mapped_independently_to_shared_phase29_sockets": True,
            "component_alpha_blending_only_during_action": True,
            "right_forearm_atlas_spill_removed_before_warp": True,
            "shoulder_socket_extensions_are_local_painted_pixel_propagation": True,
            "background_blended": False,
            "mug_hand_is_single_unit": True,
        },
        "seated_frame1": {
            "pose0_silhouette_iou": seated_iou,
            "substantial_connected_components": seated_components,
            "chair_context_applied": True,
            "human_readability_status": "unevaluated",
        },
        "standing_frame100": {
            "pose100_silhouette_iou": standing_iou,
            "substantial_connected_components": standing_components,
            "human_readability_status": "unevaluated",
        },
        "alignment": {"per_part_minimum_alpha_iou": per_part_min_iou},
        "ghost_tests": {
            "maximum_blended_components_per_part": all_double_components,
            "maximum_double_edge_fraction_per_part": all_double_edge,
            "passed": ghost_passed,
        },
        "mechanics": {
            "maximum_shoulder_or_knee_gap_preview_px": maximum_seam_gap,
            "maximum_ankle_gap_preview_px": maximum_ankle_gap,
            "minimum_normalized_affine_determinant": minimum_determinant,
            "minimum_temporal_alpha_iou": min(temporal_iou),
        },
        "rendered_contacts": {"p95_centroid_error_preview_px": contact_p95},
        "gates": gates,
        "machine_passed": machine_passed,
        "audience_quality": {"status": "unevaluated", "may_be_inferred_from_machine_pass": False},
        "cash_cost": 0,
        "paid_runtime_dependency": False,
        "video": video.name,
        "frame1_seated_proof": seated_path.name,
        "contact_sheet": sheet.name,
        "review_frames": [path.name for _, path in sorted(review_paths.items())],
    }
    report_path = output / "june-dual-atlas-performance-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the bounded June seated-to-standing dual-atlas proof")
    parser.add_argument("seated_contract")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    print(json.dumps(render_dual_atlas_performance_proof(args.seated_contract, args.output_dir, ffmpeg=args.ffmpeg), indent=2))


if __name__ == "__main__":
    main()
