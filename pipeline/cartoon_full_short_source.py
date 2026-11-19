"""Rebuild the complete repaired short from tracked art, timing and audio."""
from __future__ import annotations

import argparse
from contextlib import ExitStack, closing, contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np
from PIL import Image

from pipeline import cartoon_full_short as cut
from pipeline import cartoon_golden_master as golden
from pipeline import cartoon_pose_layers as stand
from pipeline import cartoon_source_opening as opening
from pipeline import cartoon_working_model as working


ROOT = cut.beat.ROOT
MASTER = "concept/style_frames/june_golden_scene_master_v1.json"
STAND = "concept/style_frames/june_golden_scene_gs030_layered_stand_v1.json"
CONTRACT_LOCKS = {
    MASTER: "d09314e29aa1ca326f7652ce90a8c3db0ec7a1c43386b33cfb453a2b12215948",
    STAND: "3e9b1396a1d2c7a181027aacccbbb17c8ad313b6c127522a58ad3d345373c41f",
}
REFERENCE = ROOT/"collab/june_twelve_dollar_mug_repaired_v1/twelve-dollar-mug.mp4"
REFERENCE_SHA256 = "ea4a6e294e3be513be1ba33638f8277ba32e1309f83fcf05048a38cb363f737d"


def source_inputs():
    records = []
    for name, expected in CONTRACT_LOCKS.items():
        record,_ = opening._file_record(name,expected,"canonical_json_utf8")
        records.append(record)
    master, plates = golden.load_master_contract(ROOT/MASTER)
    standing = stand.load_pose_layer_contract(ROOT/STAND)
    if standing[0]["output"]["frame_count"] != 171:
        raise ValueError("original stand clock changed")
    return records, master, plates, standing


def preflight():
    records,master,plates,standing=source_inputs()
    cut.load_plan()
    repaired=working.preflight()
    return {"clock":[cut.W,cut.H,cut.FPS,cut.COUNT], "cash_cost":0,
            "legacy_master_required":False,"external_render_cache_required":False,
            "plate_count":len(plates),"stand_pose_count":len(standing[2]),
            "legacy_picture_contracts":records,"phase42_runtime":repaired["runtime"],
            "pinned_approval_inputs_used_for_verification":True}


@contextmanager
def render_inputs():
    _,master,paths,standing = source_inputs()
    pose_contract, stand_bg, pose_paths = standing
    pour_inputs = opening._inputs()
    with ExitStack() as stack:
        plates = {}
        for name,path in paths.items():
            with Image.open(path) as source:
                plates[name] = stack.enter_context(source.convert("RGB"))
        with Image.open(stand_bg) as source:
            background=stack.enter_context(source.convert("RGB"))
        spec={pose["id"]:pose for pose in pose_contract["poses"]}
        assets,steam={},{}
        for pose_id,path in pose_paths.items():
            with Image.open(path) as image, image.convert("RGBA") as art:
                layer,registration=stand.registered_pose_layer(art,spec[pose_id],pose_contract["contact_registration"])
            assets[pose_id]=stack.enter_context(layer)
            steam[pose_id]=tuple(registration["steam_origin"])
        smears={entry["to_pose_id"]:stack.enter_context(stand.directional_smear(assets[entry["to_pose_id"]]))
                for entry in pose_contract["timeline"] if entry["type"]=="smear"}
        active = opening.ledger._prepare_pour(pour_inputs["picture"],pour_inputs["assets"])
        stack.callback(opening.ledger._close_pour_assets,*active[1:])
        yield master,plates,(pose_contract,background,assets,steam,smears),active


def original_spans():
    return [(a,b) for name,a,b,_,_ in cut.PLAN if name=="legacy"]


def earlier_frames():
    """Yield precisely the 837 legacy-assigned output frames at native RGB."""
    with render_inputs() as (master,plates,standing,active):
        pose,background,assets,steam,smears = standing
        pour,pour_bg,pour_assets,pour_smears = active
        for start,stop in original_spans():
            for i in range(start,stop):
                frame=i+1
                shot=golden.shot_for_frame(master["shots"],frame)
                land=frame-int(shot["start_frame"])+1
                if shot["id"]=="GS030":
                    item=stand.timeline_entry_for_frame(pose["timeline"],land)
                    key=item["pose_id"] if item["type"]=="pose" else item["to_pose_id"]
                    cel=assets[key] if item["type"]=="pose" else smears[key]
                    image=stand.compose_pose_frame(background,cel,steam[key],pose,land)
                elif shot["id"]=="GS060":
                    item=opening.pour.timeline_entry_for_frame(pour["timeline"],land)
                    cel=pour_assets[item["pose_id"]] if item["type"]=="pose" else pour_smears[land]
                    image,metrics=opening.pour.compose_pour_frame(pour_bg,cel,pour,land)
                    if metrics["rendered_spill_pixels_source"] or metrics["spout_start_error_px_source"]!=0:
                        image.close()
                        raise ValueError("historical pour failed liquid-contact gate")
                elif shot["source"]["type"]=="plate_sequence":
                    segment=golden.segment_for_frame(shot["segments"],frame)
                    image=golden.compose_plate_frame(plates[segment["plate_id"]],segment,frame)
                else:
                    raise ValueError(f"unexpected rendered legacy shot {shot['id']}")
                with image:
                    if image.size!=(cut.W,cut.H) or image.mode!="RGB":
                        raise ValueError("unexpected native legacy frame geometry")
                    data=image.tobytes()
                yield i, data, (shot["id"], land)


def encode_native(stream,start,stop,target,log,inventory):
    cmd=cut.media.encoder_command("ffmpeg",target)
    with log.open("wb") as err, subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=err) as proc:
        try:
            for expected in range(start,stop):
                i,data,(shot,local)=next(stream)
                if i!=expected:
                    raise ValueError(f"source frame mapping changed at {expected}")
                inventory.append({"frame":i,"shot":shot,"shot_frame_1based":local,
                                  "rgb24_sha256":sha256(data).hexdigest()})
                proc.stdin.write(data)
        finally:
            proc.stdin.close()
        if proc.wait():
            raise ValueError(f"source picture FFmpeg failed; see {log}")


def compare_review(candidate,reference):
    """Optional, read-only comparison; reference cannot feed any renderer."""
    if cut.beat.digest(reference)!=REFERENCE_SHA256:
        raise ValueError("comparison requires the pinned historical review MP4")
    sources=[cv2.VideoCapture(str(p)) for p in (candidate,reference)]
    legacy,exact=[],0
    try:
        for i in range(cut.COUNT):
            a,b=[video.read() for video in sources]
            if not a[0] or not b[0]:
                raise ValueError("comparison decode ended prematurely")
            if i<789 or 864<=i<912:
                legacy.append((i,float(cv2.PSNR(a[1],b[1]))))
            elif np.array_equal(a[1],b[1]):
                exact+=1
        if any(video.read()[0] for video in sources) or exact!=303 or len(legacy)!=837:
            raise ValueError("review comparison frame inventory changed")
    finally:
        for source in sources:
            source.release()
    worst = sorted(legacy,key=lambda p:p[1])[:8]
    if worst[0][1]<32:
        raise ValueError(f"source-build visual comparison below 32dB at {worst[0][0]}: {worst[0][1]:.2f}")
    return {"earlier_and_pot_return_frames_compared":len(legacy),"repaired_pixels_exact":exact,
            "minimum_psnr_db":worst[0][1],"median_psnr_db":float(np.median([v for _,v in legacy])),
            "worst_frames_zero_based":worst}


def build(output, *, compare=False, rebuild_repaired=False):
    output=output.resolve()
    if output.exists():
        raise FileExistsError(output)
    checked=preflight()
    plan,paths,contract=cut.load_plan()
    mix,sound=cut.full_mix(plan,paths,contract)
    output.mkdir(parents=True,exist_ok=False)
    try:
        return _build(output,compare,rebuild_repaired,checked,paths,contract,mix,sound)
    except BaseException as exc:
        cut.media._json(output/"build-failure.json",{"completed":False,"error":str(exc),"artifacts_preserved":True})
        raise


def _build(output,compare,rebuild_repaired,checked,paths,contract,mix,sound):
    repaired=paths["repaired"]
    if rebuild_repaired:
        print("Rebuilding the protected 303-frame scene from tracked artwork.",flush=True)
        sub=output/"repaired-source"
        working.build(sub)
        repaired=sub/(working.NAME+".mov")
    wav,srt=output/"mix.wav",output/"captions.srt"
    cut.foley.audio.ledger_pour._write_pcm24_wave(wav,mix,cut.RATE)
    cut.foley.audio.golden_sound.write_captions(contract,srt)
    inventory=[]
    with closing(earlier_frames()) as stream:
        for n,(kind,a,b,u,v) in enumerate(cut.PLAN,1):
            print(f"Picture {n}/4: output frames {u+1}–{v} ({kind}).",flush=True)
            target,log=output/f"shot{n:02}.mp4",output/f"encode-{n:02}.log"
            if kind=="legacy":
                encode_native(stream,a,b,target,log,inventory)
            else:
                cut.encode_or_copy(kind,repaired,a,b,target,log)
        if next(stream,None) is not None or len(inventory)!=837:
            raise ValueError("unexpected legacy source frame count")
    inv=output/"native-early-frames.json"
    cut.media._json(inv,{"index_base":0,"frames":inventory})
    listing=output/"shots.ffconcat"
    listing.write_text("ffconcat version 1.0\n"+"".join(f"file 'shot{i:02}.mp4'\n" for i in range(1,5)),
                       encoding="utf-8",newline="\n")
    mov,mp4=cut.mux(output,listing,wav,srt)
    print("Checking every timestamp, protected frame and closing sample.",flush=True)
    verification=cut.audit(output,mov,mp4,mix,paths["repaired"])
    comparison=compare_review(mp4,REFERENCE) if compare else None
    report={"completed":True,"entrypoint_sha256":cut.beat.digest(Path(__file__)),"preflight":checked,
            "policy":"review only, no human acceptance or production release",
            "repaired_render_source":"fresh tracked-art invocation" if rebuild_repaired else "tracked pixel-locked reviewed MOV",
            "legacy_frames_rendered_from_art":len(inventory),"legacy_rendered_master_read":False,
            "sound":sound,"audit":verification,"comparison_after_render":comparison,
            "sha256":{p.name:cut.beat.digest(p) for p in (mov,mp4,wav,srt,inv)}}
    cut.media._json(output/"source-build-report.json",report)
    print(f"Full review: {mp4}",flush=True)
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--output",type=Path)
    parser.add_argument("--compare-review",action="store_true",help="audit against old review only after rendering")
    parser.add_argument("--rebuild-repaired",action="store_true",help="rebuild instead of reusing the tracked protected picture")
    args=parser.parse_args()
    if args.check:
        print(json.dumps(preflight(),indent=2))
    else:
        target=args.output or ROOT/"outputs/edit"/("june-full-short-"+datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
        build(target,compare=args.compare_review,rebuild_repaired=args.rebuild_repaired)
