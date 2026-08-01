"""Half-resolution 171-frame performance preview for June's calibrated atlas rig."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from pipeline.cartoon_deformable_performance_3q import (
    DeformablePerformanceRenderer,
    compile_performance_frame,
    load_deformable_performance_contract,
)
from pipeline.cartoon_puppet_atlas_transition_proof import (
    AtlasComponent,
    AtlasProofInputs,
    _component_metrics,
    _minimum_mask_distance,
    _over,
    _premultiplied,
    _premultiplied_to_rgba,
    _similarity_affine,
    _substantial_components,
    load_puppet_atlas_contract,
)
from pipeline.cartoon_shot_sequence import _camera_frame


OUTPUT_SIZE = (960, 540)
RENDER_SCALE = 0.5
FRAME_COUNT = 171
FPS = 30
REVIEW_FRAMES = (
    1, 30, 57, 64, 70, 71, 74, 78, 79, 82, 86, 87,
    90, 91, 94, 95, 96, 100, 104, 108, 109, 130, 150, 171,
)


def _alpha_iou(left: np.ndarray, right: np.ndarray, threshold: int = 8) -> float:
    left_mask, right_mask = left > threshold, right > threshold
    union = int(np.count_nonzero(left_mask | right_mask))
    return int(np.count_nonzero(left_mask & right_mask)) / union if union else 1.0


def _scaled_target_bone(
    component: AtlasComponent,
    target_start: np.ndarray,
    target_end: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    vector = target_end - target_start
    unit = vector / max(float(np.linalg.norm(vector)), 1e-6)
    extended_start = target_start - unit * component.proximal_underlap_px
    extended_end = target_end + unit * component.distal_underlap_px
    return extended_start * RENDER_SCALE, extended_end * RENDER_SCALE


def _weighted_roi_centroid(alpha: np.ndarray, target: np.ndarray, radius: int) -> tuple[np.ndarray | None, float]:
    height, width = alpha.shape
    cx, cy = float(target[0]), float(target[1])
    x0, x1 = max(0, int(cx) - radius), min(width, int(cx) + radius + 1)
    y0, y1 = max(0, int(cy) - radius), min(height, int(cy) + radius + 1)
    region = alpha[y0:y1, x0:x1]
    ys, xs = np.where(region > 8)
    if not len(xs):
        return None, 0.0
    weights = region[ys, xs].astype(np.float64)
    centroid = np.asarray(
        [x0 + np.average(xs, weights=weights), y0 + np.average(ys, weights=weights)],
        dtype=np.float64,
    )
    presence = float(np.mean(region > 8))
    return centroid, presence


class AtlasPerformanceRenderer:
    def __init__(self, atlas_contract_path: str | Path):
        self.atlas_inputs: AtlasProofInputs = load_puppet_atlas_contract(atlas_contract_path)
        phase_path = (
            Path(__file__).resolve().parents[1]
            / str(self.atlas_inputs.contract["phase29_target"]["path"])
        ).resolve()
        self.phase_contract, self.phase_assets = load_deformable_performance_contract(phase_path)
        self.phase_renderer = DeformablePerformanceRenderer(self.phase_contract, self.phase_assets)
        self.landmark_order = list(self.phase_renderer.landmark_order)
        source_width = int(self.phase_contract["source_canvas"]["width"])
        source_height = int(self.phase_contract["source_canvas"]["height"])
        self.source_size = (round(source_width * RENDER_SCALE), round(source_height * RENDER_SCALE))
        self.background = Image.fromarray(self.atlas_inputs.porch_rgb, mode="RGB").resize(
            self.source_size,
            Image.Resampling.LANCZOS,
        )
        self.component_sources = {
            component.identifier: _premultiplied(component.rgba)
            for component in self.atlas_inputs.components
        }
        self.chair_arm_patch, self.chair_arm_mask = self._chair_patch(
            [(235, 502), (392, 526), (427, 541), (422, 568), (382, 574), (234, 543)]
        )
        self.chair_seat_patch, self.chair_seat_mask = self._chair_patch(
            [(272, 592), (603, 582), (625, 615), (606, 639), (281, 653), (261, 625)]
        )
        self.pose0_alpha = np.asarray(
            self.phase_renderer.registered_images[0].resize(self.source_size, Image.Resampling.LANCZOS),
            dtype=np.uint8,
        )[:, :, 3]
        self.pose100_alpha = np.asarray(
            self.phase_renderer.registered_images[-1].resize(self.source_size, Image.Resampling.LANCZOS),
            dtype=np.uint8,
        )[:, :, 3]

    def close(self) -> None:
        self.background.close()
        self.chair_arm_patch.close()
        self.chair_seat_patch.close()
        self.phase_renderer.close()

    def __enter__(self) -> "AtlasPerformanceRenderer":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _chair_patch(self, source_polygon: list[tuple[int, int]]) -> tuple[Image.Image, np.ndarray]:
        polygon = [(round(x * RENDER_SCALE), round(y * RENDER_SCALE)) for x, y in source_polygon]
        mask = Image.new("L", self.source_size, 0)
        ImageDraw.Draw(mask).polygon(polygon, fill=255)
        patch = self.background.convert("RGBA")
        patch.putalpha(mask)
        mask_array = np.asarray(mask, dtype=np.uint8).copy()
        mask.close()
        return patch, mask_array

    def target_landmarks(self, frame: int) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        state = compile_performance_frame(self.phase_contract, frame)
        nodes = self.phase_renderer._target_landmarks(state)
        landmarks = {
            identifier: np.asarray(point, dtype=np.float32)
            for identifier, point in zip(self.landmark_order, nodes)
        }
        left_direction = landmarks["left_hand"] - landmarks["left_elbow"]
        left_direction /= max(float(np.linalg.norm(left_direction)), 1e-6)
        landmarks["left_hand_tip"] = landmarks["left_hand"] + left_direction * 72.0
        return landmarks, state

    def _character_layer(
        self,
        landmarks: dict[str, np.ndarray],
    ) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, float], dict[str, list[float]]]:
        width, height = self.source_size
        canvas = np.zeros((height, width, 4), dtype=np.float32)
        alphas: dict[str, np.ndarray] = {}
        normalized_determinants: dict[str, float] = {}
        mapping_residuals: dict[str, list[float]] = {}
        for component in self.atlas_inputs.components:
            intended_start = landmarks[component.target_bone[0]]
            intended_end = landmarks[component.target_bone[1]]
            target_start, target_end = _scaled_target_bone(component, intended_start, intended_end)
            matrix, determinant = _similarity_affine(
                component.source_bone[0], component.source_bone[1], target_start, target_end
            )
            warped = cv2.warpAffine(
                self.component_sources[component.identifier],
                matrix,
                (width, height),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0.0, 0.0, 0.0, 0.0),
            )
            warped = np.clip(warped, 0.0, 1.0)
            canvas = _over(canvas, warped)
            alphas[component.identifier] = np.round(warped[:, :, 3] * 255.0).astype(np.uint8)
            normalized_determinants[component.identifier] = determinant / (RENDER_SCALE * RENDER_SCALE)
            rendered_start = matrix[:, :2] @ component.source_bone[0] + matrix[:, 2]
            rendered_end = matrix[:, :2] @ component.source_bone[1] + matrix[:, 2]
            mapping_residuals[component.identifier] = [
                float(np.linalg.norm(rendered_start - target_start)),
                float(np.linalg.norm(rendered_end - target_end)),
            ]
        return _premultiplied_to_rgba(canvas), alphas, normalized_determinants, mapping_residuals

    def _contact_shadow(self) -> Image.Image:
        overlay = Image.new("RGBA", self.source_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        opacity = int(self.phase_renderer.control["effects"]["contact_shadow"]["opacity"])
        registration = self.phase_renderer.control["contact_registration"]
        for identifier, radii in (
            ("target_left_support_boot", (58, 13)),
            ("target_right_boot", (50, 11)),
        ):
            point = registration[identifier]
            x, y = float(point[0]) * RENDER_SCALE, float(point[1]) * RENDER_SCALE
            rx, ry = radii[0] * RENDER_SCALE, radii[1] * RENDER_SCALE
            draw.ellipse((x - rx, y - ry, x + rx, y + ry), fill=(35, 21, 14, opacity))
        blur = float(self.phase_renderer.control["effects"]["contact_shadow"]["blur_radius"]) * RENDER_SCALE
        return overlay.filter(ImageFilter.GaussianBlur(blur))

    def _steam(self, image: Image.Image, origin: np.ndarray, frame: int) -> Image.Image:
        specification = self.phase_renderer.control["effects"]["steam"]
        overlay = Image.new("RGBA", self.source_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        time_seconds = (frame - 1) / FPS
        strength = float(specification["strength"])
        for strand in range(int(specification["strand_count"])):
            phase = strand * 0.47
            progress = (time_seconds * (0.22 + strand * 0.02) + phase) % 1.0
            points = []
            for step in range(10):
                rise = (step * 7.0 + progress * 24.0) * RENDER_SCALE
                wave = math.sin(time_seconds * 1.7 + step * 0.62 + phase * 5.0) * (3.0 + step * 0.5) * RENDER_SCALE
                points.append((origin[0] + (strand - 0.5) * 11.0 * RENDER_SCALE + wave, origin[1] - rise))
            alpha = int((72.0 - progress * 28.0) * strength)
            draw.line(points, fill=(247, 239, 224, max(5, alpha)), width=2)
        overlay = overlay.filter(ImageFilter.GaussianBlur(1.6))
        return Image.alpha_composite(image.convert("RGBA"), overlay)

    def _contact_evidence(
        self,
        state: dict[str, Any],
        landmarks: dict[str, np.ndarray],
        component_alphas: dict[str, np.ndarray],
    ) -> dict[str, dict[str, Any]]:
        evidence: dict[str, dict[str, Any]] = {}
        definitions = [
            ("left_boot", "left_boot", np.asarray(state["contacts"]["left_boot"]["point"]) * RENDER_SCALE, 28, True),
            ("right_boot", "right_boot", np.asarray(state["contacts"]["right_boot"]["point"]) * RENDER_SCALE, 28, True),
            ("chair_hand", "left_hand", np.asarray(landmarks["left_hand"]) * RENDER_SCALE, 22, bool(state["contacts"]["chair_hand"]["active"])),
            ("mug_hand", "right_hand_mug", np.asarray(landmarks["right_hand"]) * RENDER_SCALE, 22, True),
            ("mug_center", "right_hand_mug", np.asarray(landmarks["mug_center"]) * RENDER_SCALE, 25, True),
        ]
        for contact_id, component_id, target, radius, active in definitions:
            alpha = component_alphas[component_id].copy()
            if contact_id == "chair_hand" and active:
                alpha[self.chair_arm_mask > 0] = 0
            centroid, presence = _weighted_roi_centroid(alpha, target, radius)
            evidence[contact_id] = {
                "active": active,
                "target": [float(target[0]), float(target[1])],
                "rendered_centroid": None if centroid is None else [float(centroid[0]), float(centroid[1])],
                "centroid_error_px": None if centroid is None else float(np.linalg.norm(centroid - target)),
                "roi_alpha_presence": presence,
            }
        return evidence

    def render_frame(self, frame: int) -> tuple[Image.Image, dict[str, Any]]:
        if not 1 <= frame <= FRAME_COUNT:
            raise ValueError("atlas performance frame must be 1 through 171")
        landmarks, state = self.target_landmarks(frame)
        character, component_alphas, determinants, mapping_residuals = self._character_layer(landmarks)
        composed = Image.alpha_composite(self.background.convert("RGBA"), self._contact_shadow())
        composed = Image.alpha_composite(composed, Image.fromarray(character, mode="RGBA"))
        chair_arm = bool(state["contacts"]["chair_hand"]["active"])
        chair_seat = bool(state["contacts"]["chair_seat"]["active"])
        if chair_seat:
            composed = Image.alpha_composite(composed, self.chair_seat_patch)
        if chair_arm:
            composed = Image.alpha_composite(composed, self.chair_arm_patch)
        steam_origin = np.asarray(landmarks["mug_center"], dtype=np.float32) * RENDER_SCALE
        steam_origin[1] -= 50.0 * RENDER_SCALE
        composed = self._steam(composed, steam_origin, frame)
        light_strength = float(self.phase_renderer.control["effects"]["light_breathe"]["strength"])
        factor = 1.0 + light_strength * math.sin((frame - 1) / FPS * math.pi * 0.71)
        composed = ImageEnhance.Brightness(composed.convert("RGB")).enhance(factor)
        output = _camera_frame(
            composed,
            self.phase_renderer.control["camera"],
            (frame - 1) / (FRAME_COUNT - 1),
            OUTPUT_SIZE,
        )
        joint_gaps = {
            f"{left_id}__{right_id}": _minimum_mask_distance(component_alphas[left_id], component_alphas[right_id])
            for left_id, right_id in self.atlas_inputs.contract["rig"]["joint_pairs"]
        }
        contact_components = {
            identifier: _component_metrics(component_alphas[identifier])
            for identifier in self.atlas_inputs.contract["rig"]["contact_components"]
        }
        character_alpha = character[:, :, 3]
        details = {
            "frame": frame,
            "state": state,
            "semantic_channels": list(state["channels"]),
            "component_source_policy": "immutable_atlas_only_no_corrective_swaps",
            "normalized_determinants": determinants,
            "mapping_residuals_px": mapping_residuals,
            "joint_gaps_px": joint_gaps,
            "contact_components": contact_components,
            "contact_evidence": self._contact_evidence(state, landmarks, component_alphas),
            "chair_occlusion": {"arm_applied": chair_arm, "seat_applied": chair_seat},
            "character_alpha": character_alpha,
            "compose_clock": {
                "contact_shadow": True,
                "steam_time_seconds": (frame - 1) / FPS,
                "light_breathe_time_seconds": (frame - 1) / FPS,
                "camera_amount": (frame - 1) / (FRAME_COUNT - 1),
            },
        }
        return output, details


def _decoded_frame_count(video: Path) -> int:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"unable to decode atlas performance preview: {video}")
    count = 0
    try:
        while True:
            ok, _ = capture.read()
            if not ok:
                break
            count += 1
    finally:
        capture.release()
    return count


def _contact_sheet(frames: dict[int, Path], output: Path) -> None:
    sheet = Image.new("RGB", (1920, 720), (18, 20, 24))
    font = ImageFont.load_default(size=18)
    for index, (frame, path) in enumerate(sorted(frames.items())):
        image = Image.open(path).convert("RGB")
        image.thumbnail((320, 180), Image.Resampling.LANCZOS)
        x, y = (index % 6) * 320, (index // 6) * 180
        sheet.paste(image, (x, y))
        ImageDraw.Draw(sheet).text((x + 8, y + 7), f"F{frame:03d}", fill=(250, 240, 220), font=font, stroke_width=2, stroke_fill=(10, 10, 10))
        image.close()
    sheet.save(output, quality=94, subsampling=0)
    sheet.close()


def render_puppet_atlas_performance(
    atlas_contract_path: str | Path,
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
    video = output / "june-puppet-atlas-performance-preview.mp4"
    process = subprocess.Popen(
        [
            executable, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{OUTPUT_SIZE[0]}x{OUTPUT_SIZE[1]}", "-r", str(FPS), "-i", "-", "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", str(video),
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    review_paths: dict[int, Path] = {}
    minimum_determinant = math.inf
    maximum_gap = 0.0
    maximum_contact_components = 0
    minimum_contact_dominance = 1.0
    contact_errors: dict[str, list[float]] = {identifier: [] for identifier in ("left_boot", "right_boot", "chair_hand", "mug_hand", "mug_center")}
    contact_presence: dict[str, list[float]] = {identifier: [] for identifier in contact_errors}
    occlusion_arm_frames = 0
    occlusion_seat_frames = 0
    endpoint_alpha: dict[int, np.ndarray] = {}
    previous_alpha: np.ndarray | None = None
    temporal_iou: list[float] = []
    try:
        with AtlasPerformanceRenderer(atlas_contract_path) as renderer:
            for frame in range(1, FRAME_COUNT + 1):
                image, detail = renderer.render_frame(frame)
                rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
                if process.stdin is None:
                    raise RuntimeError("atlas performance ffmpeg stdin closed")
                process.stdin.write(rgb.tobytes())
                if frame in REVIEW_FRAMES:
                    path = review_dir / f"frame_{frame:04d}.png"
                    image.save(path)
                    review_paths[frame] = path
                image.close()
                minimum_determinant = min(minimum_determinant, *detail["normalized_determinants"].values())
                maximum_gap = max(maximum_gap, *detail["joint_gaps_px"].values())
                for metric in detail["contact_components"].values():
                    maximum_contact_components = max(maximum_contact_components, int(metric["significant_count"]))
                    minimum_contact_dominance = min(minimum_contact_dominance, float(metric["dominant_fraction"]))
                for identifier, evidence in detail["contact_evidence"].items():
                    if evidence["active"] and evidence["centroid_error_px"] is not None:
                        contact_errors[identifier].append(float(evidence["centroid_error_px"]))
                        contact_presence[identifier].append(float(evidence["roi_alpha_presence"]))
                occlusion_arm_frames += int(detail["chair_occlusion"]["arm_applied"])
                occlusion_seat_frames += int(detail["chair_occlusion"]["seat_applied"])
                alpha = detail["character_alpha"]
                if previous_alpha is not None:
                    temporal_iou.append(_alpha_iou(previous_alpha, alpha))
                previous_alpha = alpha.copy()
                if frame in (1, 171):
                    endpoint_alpha[frame] = alpha.copy()
            if process.stdin is not None:
                process.stdin.close()
            stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr is not None else ""
            return_code = process.wait()
            if return_code:
                raise RuntimeError(f"atlas performance encode failed: {stderr.strip()}")

            decoded = _decoded_frame_count(video)
            contact_p95 = {
                identifier: float(np.percentile(values, 95)) if values else None
                for identifier, values in contact_errors.items()
            }
            presence_min = {
                identifier: min(values) if values else None
                for identifier, values in contact_presence.items()
            }
            seated_components, _, _ = _substantial_components(endpoint_alpha[1], 8, 125)
            standing_components, _, _ = _substantial_components(endpoint_alpha[171], 8, 125)
            readability = {
                "seated": {
                    "silhouette_iou_to_pose0": _alpha_iou(endpoint_alpha[1], renderer.pose0_alpha),
                    "substantial_connected_components": seated_components,
                    "human_status": "unevaluated",
                },
                "standing": {
                    "silhouette_iou_to_pose100": _alpha_iou(endpoint_alpha[171], renderer.pose100_alpha),
                    "substantial_connected_components": standing_components,
                    "human_status": "unevaluated",
                },
            }
    except BaseException:
        if process.poll() is None:
            process.kill()
        raise

    sheet = output / "june-puppet-atlas-performance-contact-sheet.jpg"
    _contact_sheet(review_paths, sheet)
    quarter = output / "june-puppet-atlas-performance-quarter-speed.mp4"
    result = subprocess.run(
        [
            executable, "-y", "-v", "error", "-i", str(video), "-an", "-vf", "setpts=4.0*PTS",
            "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", str(quarter),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(f"atlas quarter-speed encode failed: {result.stderr.strip()}")
    gates = {
        "delivery_frame_count": 171,
        "minimum_normalized_affine_determinant": 0.0001,
        "maximum_joint_gap_preview_px": 5.0,
        "maximum_contact_significant_components": 1,
        "minimum_contact_dominant_fraction": 0.95,
        "maximum_contact_centroid_error_p95_preview_px": 18.0,
        "minimum_contact_roi_alpha_presence": 0.02,
        "minimum_temporal_alpha_iou": 0.82,
        "minimum_endpoint_silhouette_iou": 0.42,
        "maximum_endpoint_substantial_components": 3,
        "chair_arm_occlusion_frames": 78,
        "chair_seat_occlusion_frames": 70,
    }
    all_contact_p95 = [value for value in contact_p95.values() if value is not None]
    all_presence = [value for value in presence_min.values() if value is not None]
    machine_passed = (
        decoded == FRAME_COUNT
        and minimum_determinant >= gates["minimum_normalized_affine_determinant"]
        and maximum_gap <= gates["maximum_joint_gap_preview_px"]
        and maximum_contact_components <= gates["maximum_contact_significant_components"]
        and minimum_contact_dominance >= gates["minimum_contact_dominant_fraction"]
        and max(all_contact_p95) <= gates["maximum_contact_centroid_error_p95_preview_px"]
        and min(all_presence) >= gates["minimum_contact_roi_alpha_presence"]
        and min(temporal_iou) >= gates["minimum_temporal_alpha_iou"]
        and min(readability["seated"]["silhouette_iou_to_pose0"], readability["standing"]["silhouette_iou_to_pose100"]) >= gates["minimum_endpoint_silhouette_iou"]
        and max(readability["seated"]["substantial_connected_components"], readability["standing"]["substantial_connected_components"]) <= gates["maximum_endpoint_substantial_components"]
        and occlusion_arm_frames == gates["chair_arm_occlusion_frames"]
        and occlusion_seat_frames == gates["chair_seat_occlusion_frames"]
    )
    report = {
        "proof": "june_puppet_atlas_full_performance_half_resolution",
        "frame_count": FRAME_COUNT,
        "fps": FPS,
        "width": OUTPUT_SIZE[0],
        "height": OUTPUT_SIZE[1],
        "duration_seconds": FRAME_COUNT / FPS,
        "source_policy": "single calibrated 14-component atlas for all frames; zero corrective-source swaps",
        "delivery": {"decoded_frame_count": decoded, "machine_passed": decoded == FRAME_COUNT},
        "compose_clock": {
            "phase22_contact_shadow": True,
            "phase22_steam_clock": True,
            "phase22_light_breathe_clock": True,
            "phase22_camera_clock": True,
        },
        "chair_occlusion": {
            "arm_patch_frames": occlusion_arm_frames,
            "seat_patch_frames": occlusion_seat_frames,
            "source": "clean_porch_deterministic_polygon_patch",
        },
        "mechanics": {
            "minimum_normalized_affine_determinant": minimum_determinant,
            "maximum_joint_gap_preview_px": maximum_gap,
            "maximum_contact_significant_components": maximum_contact_components,
            "minimum_contact_dominant_fraction": minimum_contact_dominance,
            "minimum_temporal_alpha_iou": min(temporal_iou),
        },
        "rendered_contact_centroids": {
            "p95_error_preview_px": contact_p95,
            "minimum_roi_alpha_presence": presence_min,
            "measurement_space": "actual half-resolution pre-camera rendered component alpha after chair-hand occlusion",
        },
        "readability": readability,
        "audience_quality": {"status": "unevaluated", "may_be_inferred_from_mechanics": False},
        "gates": gates,
        "machine_passed": machine_passed,
        "cash_cost": 0,
        "paid_runtime_dependency": False,
        "video": video.name,
        "contact_sheet": sheet.name,
        "quarter_speed_review": quarter.name,
        "review_frames": [path.name for _, path in sorted(review_paths.items())],
    }
    report_path = output / "june-puppet-atlas-performance-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render June's half-resolution 171-frame atlas performance preview")
    parser.add_argument("atlas_contract")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    print(json.dumps(render_puppet_atlas_performance(args.atlas_contract, args.output_dir, ffmpeg=args.ffmpeg), indent=2))


if __name__ == "__main__":
    main()
