"""Build the versioned June Oxley + porch .blend library as a runtime artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def _args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def main() -> None:
    args = _args()
    import bpy
    import mathutils

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from pipeline.blender import render_vertical_slice as studio

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    asset_major = int(str(manifest["asset_version"]).split(".", 1)[0])
    studio._clear(bpy)
    materials = studio._make_materials(bpy, asset_major=asset_major)
    studio._make_porch(bpy, mathutils, materials, 390)
    rig, mouth, face_controls = studio._make_june(bpy, mathutils, materials, asset_major=asset_major)
    rig["ce_asset_id"] = manifest["asset_id"]
    rig["ce_asset_version"] = manifest["asset_version"]
    rig["ce_character_id"] = manifest["character_id"]
    rig["ce_design_lock"] = manifest["design_lock"]["body"]
    mouth["ce_viseme_set"] = "ABCDEFGHX"
    for eye in face_controls["eyes"]:
        eye["ce_face_control"] = "blink_or_eye_aim"
    for lid in face_controls["upper_lids"] + face_controls["lower_lids"]:
        lid["ce_face_control_type"] = "independent_eyelid"

    library_plan = {
        "frame_end": 390,
        "shots": [
            {"frame_start": 1, "frame_end": 108},
            {"frame_start": 109, "frame_end": 249},
            {"frame_start": 250, "frame_end": 390},
        ],
        "mouth_cues": [{"frame_start": 1, "frame_end": 390, "shape": "X"}],
    }
    studio._animate_rig(bpy, rig, library_plan)
    studio._animate_mouth(mouth, library_plan)
    studio._animate_expressions(bpy.data.objects["June_Head"], library_plan, face_controls)
    studio._animate_blinks(face_controls, 390)

    june_collection = bpy.data.collections.new("CE_June_Oxley")
    porch_collection = bpy.data.collections.new("CE_June_Porch")
    props_collection = bpy.data.collections.new("CE_June_Props")
    bpy.context.scene.collection.children.link(june_collection)
    bpy.context.scene.collection.children.link(porch_collection)
    bpy.context.scene.collection.children.link(props_collection)
    june_names = {
        obj.name
        for obj in bpy.context.scene.objects
        if obj.name.startswith("June_") or obj.name == "June_Oxley_Rig"
    }
    for obj in list(bpy.context.scene.objects):
        if obj.get("ce_prop_role"):
            target = props_collection
        else:
            target = june_collection if obj.name in june_names else porch_collection
        if target.objects.get(obj.name) is None:
            target.objects.link(obj)
        for collection in list(obj.users_collection):
            if collection != target:
                collection.objects.unlink(obj)
    june_collection["ce_asset_id"] = manifest["asset_id"]
    june_collection["ce_asset_version"] = manifest["asset_version"]
    porch_collection["ce_location_id"] = "june_front_porch"
    props_collection["ce_performance_contract"] = manifest.get("performance_contract", {}).get("path", "")

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.scene["ce_asset_manifest"] = json.dumps(manifest, sort_keys=True)
    bpy.context.scene["ce_asset_library"] = True
    bpy.ops.wm.save_as_mainfile(filepath=str(output), compress=True)
    print(f"Saved June asset library: {output}")


if __name__ == "__main__":
    main()
