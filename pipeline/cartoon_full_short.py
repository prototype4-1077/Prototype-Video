"""Build the full Twelve-Dollar Mug review, preserving the repaired picture and closing PCM."""
from __future__ import annotations

import argparse
from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline import cartoon_story_beat as beat
from pipeline import cartoon_scene_review as media
from pipeline import cartoon_recorded_foley as foley

RECIPE = beat.ROOT / "concept/scenes/june-twelve-dollar-mug-repaired-v1.json"
COUNT, W, H, STEP, FPS = 1140, 1920, 1080, 1600, 30
RATE = STEP*FPS
PREFIX = 912
APPROVED_A = 75
PLAN = (("legacy",0,789,0,789), ("repaired",0,75,789,864),
        ("legacy",864,912,864,912), ("repaired",75,303,912,1140))
CLI = ["ffmpeg","-nostdin","-v","error","-n"]
SAMPLES = (0,129,225,396,564,678,788,789,804,863,864,899,911,912,936,1026,1074,1139)


def load_plan(recipe=RECIPE):
    plan = json.loads(recipe.read_text(encoding="utf-8"))
    if (plan["fps"],plan["sample_rate"],plan["source_frame_count"],plan["output_frame_count"],plan["review_only"]) != (
        FPS,RATE,1164,COUNT,True
    ):
        raise ValueError("unexpected complete-cut clock")
    actual = tuple((s["source"],*s["source_span"],*s["output_span"]) for s in plan["picture"])
    if actual != PLAN or plan["audio"]["procedural_audio"]:
        raise ValueError("unreviewed picture mapping or procedural sound")
    paths = {label:beat.bound_asset(plan[label]) for label in (
        "repaired","approved_pcm","approved_voice_reference","speech","cue_contract","gain_receipt")}
    sound_contract = json.loads(paths["cue_contract"].read_text(encoding="utf-8"))
    rows = sound_contract["dialogue_cues"]
    if len(rows)!=18 or rows[-1]["end_frame"]>COUNT or not any(
        s["start_frame"]==871 and s["end_frame"]==910 for s in rows
    ):
        raise ValueError("final coffee line or other dialogue missing")
    return plan, paths, sound_contract


def full_mix(plan,paths,sound_contract):
    read = foley.audio.ledger_pour._read_pcm24_wave
    source, meta = read(paths["speech"])
    approved, meta2 = read(paths["approved_pcm"])
    ref, meta3 = read(paths["approved_voice_reference"])
    if (source.shape,approved.shape,ref.shape)!=( (1164*STEP,1),(303*STEP,2),(303*STEP,2)) or any(
            m["sample_rate"] != RATE for m in (meta,meta2,meta3)):
        raise ValueError("unexpected pinned PCM geometry")
    reference_gain = json.loads(paths["gain_receipt"].read_text(encoding="utf-8"))["source_audit"]["shared_reference_gain"]
    if np.any(ref[:99*STEP]):
        raise ValueError("Phase42 introductory voice is not isolated silence")
    speech = source.astype(np.float64)/foley.audio.PCM24_MAX
    for cue in sound_contract["dialogue_cues"]:
        a,b = (cue["start_frame"]-1)*STEP,cue["end_frame"]*STEP
        if not np.any(source[a:b]):
            raise ValueError(f"silent dialogue cue {cue['id']}")
        speech[a:b] *= foley.audio._db(cue["gain_db"])
    expected = foley.audio._to_pcm24(np.repeat(speech[936*STEP:COUNT*STEP]/math.sqrt(2)*reference_gain,2,axis=1))
    if not np.array_equal(expected,ref[99*STEP:]):
        raise ValueError("the repaired closing words are not the same source and timing")
    prefix_trim = float(plan["prefix_voice_trim_db"])
    if prefix_trim != -1.0:
        raise ValueError("prefix voice level is not the audited edit")
    prefix_voice = foley.audio._to_pcm24(np.repeat(
        speech[:PREFIX*STEP]/math.sqrt(2)*reference_gain*foley.audio._db(prefix_trim),2,axis=1))
    fade = foley.FADE_SAMPLES
    # The edit falls where both mastering fade windows are already PCM zero.
    # Applying a 30ms gain ramp there is an identity; the approved tail must
    # not be processed just to make a numerical transition.
    if np.any(prefix_voice[:fade]) or np.any(prefix_voice[-fade:]) or np.any(approved[75*STEP:75*STEP+fade]) or np.any(approved[-fade:]):
        raise ValueError("edit is no longer 30ms digital silence")
    if np.any(approved[:16*STEP]) or np.any(approved[75*STEP:99*STEP]):
        raise ValueError("accepted pour moved or an audible transition bed was added")
    # First 75 frames equal recorded pour only; keep it once, beneath the
    # original continuous speech rather than importing the short's voice mute.
    prefix = prefix_voice.astype(np.int64)
    prefix[789*STEP:864*STEP] += approved[:75*STEP]
    if abs(prefix).max()>=8388608:
        raise ValueError("prefix clips")
    mixed = np.concatenate((prefix.astype(np.int32),approved[75*STEP:]))
    return mixed, {
        "frames":COUNT, "sample_count":len(mixed), "dialogue_cues_preserved":18,
        "closing_dialogue_in_isolated_reference_exact":True, "prefix_db_trim_from_reference":prefix_trim,
        "legacy_effects_used":False, "fx_used":"same two recorded Phase42 Foley excerpts",
        "source_recorded_pour_reused_once":True, "pure_pour_output_samples_half_open":[789*STEP,864*STEP],
        "exact_approved_closing_pcm_sample_count":(COUNT-PREFIX)*STEP,
        "silence_at_30ms_join_windows":True,
    }


def encode_or_copy(kind,source,first,last,target,log):
    if kind=="legacy":
        command=media.encoder_command("ffmpeg",target)
        command[command.index("-f"):command.index("-an")]=["-i",str(source),"-map","0:v:0"]
        command[command.index("-vf")+1] = (
            f"trim=start_frame={first}:end_frame={last},setpts=PTS-STARTPTS,"
            "scale=in_range=tv:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709,"
            "format=yuv420p,setsar=1,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709")
        media._run(command,log)
    else:
        seek = ["-ss","2.5"] if first==75 else []
        media._run(CLI+seek+["-i",str(source),"-map","0:v:0","-an","-c:v","copy","-frames:v",str(last-first),
                             "-video_track_timescale","30000",str(target)],log)


def render_pictures(output,legacy,repaired):
    for idx,(kind,a,b,_,_) in enumerate(PLAN,1):
        encode_or_copy(kind,legacy if kind=="legacy" else repaired,a,b,
                       output/f"shot{idx:02}.mp4",output/f"encode-{idx:02}.log")
    listing = output/"shots.ffconcat"
    listing.write_text("ffconcat version 1.0\n"+"".join(f"file 'shot{i:02}.mp4'\n" for i in range(1,5)),
                       encoding="utf-8",newline="\n")
    return listing


def mux(output,listing,wav,srt):
    mov,mp4 = output/"twelve-dollar-mug.mov",output/"twelve-dollar-mug.mp4"
    times=["-video_track_timescale","30000","-movie_timescale","48000","-movflags","+faststart+write_colr"]
    media._run(CLI+["-f","concat","-safe","1","-i",str(listing),"-i",str(wav),"-i",str(srt),
        "-map","0:v:0","-map","1:a:0","-map","2:s:0","-c:v","copy","-c:a","pcm_s24le","-c:s","mov_text",
        "-metadata:s:s:0","language=eng","-disposition:s:0","0"]+times+[str(mov)],output/"mux-mov.log")
    media._run(CLI+["-i",str(mov),"-map","0:v:0","-map","0:a:0","-map","0:s:0","-c:v","copy","-c:a","aac","-b:a","512k",
                     "-c:s","copy","-disposition:s:0","0"]+times+[str(mp4)],output/"mux-mp4.log")
    return mov,mp4


def verify_video_decode(movie,repaired,output):
    picture,original=cv2.VideoCapture(str(movie)),cv2.VideoCapture(str(repaired))
    repaired_hashes=sha256()
    matching, retained, differences = 0, {}, {}
    previous=None
    try:
        for i in range(COUNT):
            ok,frame=picture.read()
            if not ok or frame.shape!=(H,W,3):
                raise ValueError(f"could not decode F{i}")
            if 789<=i<864 or 912<=i<COUNT:
                # The original is advanced only when one of its frames is used.
                got,src=original.read()
                if not got or not np.array_equal(frame,src):
                    raise ValueError(f"restored cut altered repaired decoded pixels at F{i}")
                repaired_hashes.update(frame.tobytes())
                matching += 1
            if i in SAMPLES:
                retained[i]=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
            if i in (789,864):
                mae=float(np.abs(frame.astype(np.int16)-previous).mean())
                if mae>10:
                    raise ValueError(f"potential same-view discontinuity F{i}: {mae:.3f}")
                differences[str(i)]=mae
            previous=frame
        if picture.read()[0] or original.read()[0] or matching!=303:
            raise ValueError("unexpected decoded frame count")
    finally:
        picture.release()
        original.release()
    sheet=Image.new("RGB",(1440,223*6),"#181411")
    draw=ImageDraw.Draw(sheet)
    for n,(i,frame) in enumerate(retained.items()):
        x,y=n%4*360,n//4*223
        sheet.paste(frame.resize((360,202),Image.Resampling.LANCZOS),(x,y))
        draw.text((x+5,y+202),f"F{i:04} / {i/30:.2f}s",fill="white")
    sheet.crop((0,0,1440,math.ceil(len(retained)/4)*223)).save(output/"decoded-cuts.jpg",quality=94)
    return {"decoded_repaired_frames_exact":matching,"decoded_repaired_bgr_hash":repaired_hashes.hexdigest(),
            "same_view_join_mae":differences}


def audit(output,mov,mp4,expected,repaired):
    for path in (mov,mp4):
        probe=media._probe(path,"ffprobe")
        streams={s["codec_type"]:s for s in probe["streams"]}
        if set(streams)!={"audio","video","subtitle"}:
            raise ValueError("stream set changed")
        v,a,s=(streams[k] for k in ("video","audio","subtitle"))
        if (v["width"],v["height"],v["nb_read_frames"],v["avg_frame_rate"],v.get("color_space"))!=(W,H,str(COUNT),"30/1","bt709"):
            raise ValueError("unexpected video geometry/count")
        if (a["sample_rate"],a["channels"],s["codec_name"])!=(str(RATE),2,"mov_text"):
            raise ValueError("audiovisual delivery changed")
        if any(int(row["duration_ts"])*Fraction(row["time_base"])!=Fraction(COUNT,FPS) or row["start_pts"] for row in (a,v)):
            raise ValueError("stream duration or timestamp offset")
    pts = json.loads(subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0","-show_frames",
        "-show_entries","frame=best_effort_timestamp","-of","json",str(mp4)]))["frames"]
    if [int(p["best_effort_timestamp"])*Fraction(v["time_base"]) for p in pts] != [Fraction(i,30) for i in range(COUNT)]:
        raise ValueError("picture frame timestamps differ")
    if media._video_hash(mov,"ffmpeg")!=media._video_hash(mp4,"ffmpeg"):
        raise ValueError("MP4 altered MOV picture packets")
    pcm=beat.decoded_audio(mov,"s32le","<i4")//256
    if not np.array_equal(pcm,expected):
        raise ValueError("full-short PCM lost samples")
    decoded=beat.decoded_audio(mp4,"f32le","<f4")[:len(pcm)]
    if len(decoded)!=len(pcm) or abs(decoded).max()>=1:
        raise ValueError("preview audio truncated or clipped")
    ref=pcm.astype(np.float64)/8388608
    snr=float(10*np.log10(np.mean(ref**2)/max(np.mean((ref-decoded)**2),1e-19)))
    peaks={p.suffix:beat.true_peak(p) for p in (mov,mp4)}
    if snr<40 or max(peaks.values())>-1:
        raise ValueError(f"AAC or true-peak gate failed: SNR {snr:.3f}, {peaks}")
    pictures=verify_video_decode(mp4,repaired,output)
    return {"aac_snr_db":snr,"true_peak_dbtp":peaks,"all_pts_exact":True,
            "mov_pcm_exact":True,"mp4_mov_video_packet_hash_equal":True,**pictures}


def build(legacy,output,recipe=RECIPE):
    plan,paths,contract=load_plan(recipe)
    if beat.digest(legacy)!=plan["legacy"]["sha256"]:
        raise ValueError("legacy Phase25 master bytes changed")
    if output.exists():
        raise FileExistsError(output)
    mix,sound=full_mix(plan,paths,contract)
    output.mkdir(parents=True,exist_ok=False)
    wav,srt=output/"mix.wav",output/"captions.srt"
    foley.audio.ledger_pour._write_pcm24_wave(wav,mix,RATE)
    foley.audio.golden_sound.write_captions(contract,srt)
    listing=render_pictures(output,legacy,paths["repaired"])
    mov,mp4=mux(output,listing,wav,srt)
    result={"id":plan["id"],"human_acceptance":False,"production_release":False,"cost":0,
            "recipe_sha256":beat.digest(recipe),"renderer_sha256":beat.digest(Path(__file__)),
            "legacy_sha256":plan["legacy"]["sha256"],"repaired_sha256":plan["repaired"]["sha256"],
            "picture_clock_half_open":PLAN,"sound":sound,"audit":audit(output,mov,mp4,mix,paths["repaired"]),
            "outputs_sha256":{p.name:beat.digest(p) for p in (mov,mp4,srt,wav)}}
    media._json(output/"verification.json",result)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-master",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(build(args.legacy_master,args.output),indent=2))
