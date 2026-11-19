"""Assemble a June review beat from pinned picture and sample-aligned sound."""
from __future__ import annotations

import argparse
from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline import cartoon_recorded_foley as foley
from pipeline import cartoon_scene_review as media

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "concept/scenes/june-rest-your-hands-story-v1.json"
RATE, FPS, STEP = 48000, 30, 1600
W, H = 1280, 720


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def bound_asset(entry):
    path = (ROOT / entry["path"]).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("story asset outside repository")
    if digest(path) != entry["sha256"]:
        raise ValueError(f"source hash changed: {path.name}")
    return path


def plan_from(recipe):
    plan = json.loads(recipe.read_text(encoding="utf-8"))
    if (plan["schema_version"],plan["review_only"],plan["fps"],plan["sample_rate"],plan["canvas"]) != (1,True,FPS,RATE,[W,H]):
        raise ValueError("unsupported story format")
    assets = {kind: bound_asset(spec) for kind,spec in plan["sources"].items()}
    if [s["source"] for s in plan["shots"]] != ["dialogue","mug","dialogue"]:
        raise ValueError("expected face, action, face")
    start, end, offsets = 0, 0, []
    for shot in plan["shots"]:
        start,end = shot["span"]
        if not (type(start) is type(end) is int and 0 <= start < end <= plan["sources"][shot["source"]]["frame_count"]):
            raise ValueError("invalid source span")
        offsets.append((offsets[-1][1] if offsets else 0,
                        (offsets[-1][1] if offsets else 0) + end-start))
    count = offsets[-1][1]
    cut1,cut2 = offsets[1][0],offsets[2][0]
    pause, contact = plan["voice_pause"],plan["contact"]
    split, extra = pause["source_frame"],pause["insert_frames"]
    if (plan["shots"][0]["span"][0] != 0 or extra <= 0 or
        count != plan["sources"]["dialogue"]["frame_count"]+extra or
        not cut1 < split < start or cut2 != start+extra):
        raise ValueError("face and voice clocks disagree across the pause")
    if not (plan["shots"][1]["span"][0] <= contact["source_frame"] < plan["shots"][1]["span"][1] and
            contact["output_frame"] == cut1 + contact["source_frame"] - plan["shots"][1]["span"][0]):
        raise ValueError("sound event does not map to insert touchdown")
    cues = json.loads(assets["cues"].read_text(encoding="utf-8"))
    if cues["metadata"]["sourceAudioSha256"] != plan["sources"]["voice"]["sha256"]:
        raise ValueError("phonemes refer to different voice")
    pauses = [(Fraction(str(c["start"])),Fraction(str(c["end"]))) for c in cues["mouthCues"] if c["value"]=="X"]
    if tuple(map(Fraction,map(str,pause["certified_silent_cue_span_seconds"]))) not in pauses:
        raise ValueError("declared phrase gap not found")
    # 30 ms of guard on both sides keeps the picture joins and voice splice
    # in the known quiet phoneme gaps. Phoneme cues are not word timestamps.
    guard = Fraction(30,1000)
    for frame in (cut1,split,start):
        t = Fraction(frame,FPS)
        if not any(a + guard <= t <= b - guard for a,b in pauses):
            raise ValueError(f"edit at source frame {frame} is too close to speech")
    return plan,assets,offsets


def sound(plan,assets):
    voice, metadata = foley.audio.ledger_pour._read_pcm24_wave(assets["voice"])
    if voice.shape != (plan["sources"]["dialogue"]["frame_count"]*STEP,1) or metadata["sample_rate"]!=RATE:
        raise ValueError("unexpected voice PCM")
    pause = plan["voice_pause"]
    split,extra = pause["source_frame"]*STEP,pause["insert_frames"]*STEP
    fade = foley.FADE_SAMPLES
    if pause["fade_ms_each_side"] * RATE // 1000 != fade:
        raise ValueError("incorrect splice fade duration")
    # Both fade windows are experimentally digital zero. Check every sample
    # so a changed plan cannot safely splice speech using cues alone.
    if np.any(voice[split-fade:split+fade]):
        raise ValueError("voice splice not inside digital silence")
    gain = float(plan["voice_gain_db"])
    if not -6 <= gain <= -1:
        raise ValueError("expected fixed voice attenuation for mix headroom")
    attenuated = np.rint(voice.astype(np.float64)*foley.audio._db(gain)).astype(np.int32)
    preserved = np.concatenate((attenuated[:split],np.zeros((extra,1),np.int32),attenuated[split:]))
    preserved = np.repeat(preserved,2,axis=1)
    event = plan["contact"]
    manifest = foley._sources(foley.SOURCE_ROOT)
    spec = next(c for c in manifest["sources"] if c["id"]==event["id"]=="cup_contact")
    if not 2*fade <= event["trimmed_samples"] <= spec["decoded_sample_count"]:
        raise ValueError("invalid recorded Foley trim")
    clip_spec = dict(spec,decoded_sample_count=event["trimmed_samples"],mono_peak_dbfs=event["mono_peak_dbfs"])
    decoded = foley.audio.golden_sound._read_audio_f32(
        "ffmpeg",foley.SOURCE_ROOT/spec["file"],channels=1,sample_rate=RATE)
    clip = foley._faded_excerpt(decoded,clip_spec)
    peak = int(np.argmax(np.abs(clip)))
    if peak != event["dominant_transient_offset_samples"]:
        raise ValueError("contact recording peak moved")
    if clip[0]!=0 or clip[-1]!=0:
        raise ValueError("recording window is not faded")
    i = event["output_frame"]*STEP-peak
    j = i+len(clip)
    if not 0 < i < j < len(preserved):
        raise ValueError("contact event clipped by delivery")
    effects = np.zeros_like(preserved)
    stereo = np.repeat((clip/math.sqrt(2))[:,None],2,axis=1)
    effects[i:j] = foley.audio._to_pcm24(stereo)
    combined = preserved.astype(np.int64)+effects.astype(np.int64)
    if max(abs(combined.min()),abs(combined.max())) >= 8388608:
        raise ValueError("mix would clip the original voice")
    return combined.astype(np.int32),effects,preserved,{
        "splice_source_sample":split,"added_silence_samples":extra,"retimed_words":False,
        "voice_gain_db":gain,"word_samples_unchanged_except_fixed_gain":True,
        "event_sample_span_half_open":[i,j],"dominant_contact_sample":i+peak,
        "contact_recording":clip_spec,"peak_dbfs_pcm":float(20*np.log10(np.abs(combined).max()/8388608))}


def encode_shot(source,span,destination,log):
    first, last = span
    command = media.encoder_command("ffmpeg",destination)
    # Reuse codec/color/tracking settings, replace raw RGB stdin with source
    # trim. Input movies are already BT.709 with limited luma range.
    src = command.index("-f")
    after_input = command.index("-an")
    command[src:after_input] = ["-i",str(source),"-map","0:v:0"]
    command[command.index("-vf")+1] = (
        f"trim=start_frame={first}:end_frame={last},setpts=PTS-STARTPTS,"
        f"scale={W}:{H}:flags=lanczos:in_range=limited:out_range=limited,"
        "format=yuv420p,setsar=1,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709"
    )
    media._run(command, log)


def decoded_audio(path,fmt,dtype):
    raw = subprocess.check_output(["ffmpeg","-v","error","-i",str(path),"-map","0:a:0","-f",fmt,"pipe:1"])
    return np.frombuffer(raw,dtype=dtype).reshape(-1,2)


def true_peak(path):
    meter = subprocess.run(["ffmpeg","-nostats","-i",str(path),"-map","0:a:0",
        "-af","ebur128=peak=true","-f","null","-"],capture_output=True,text=True,check=True).stderr
    peaks = re.findall(r"True peak:\s+Peak:\s+(-?[0-9.]+) dBFS",meter)
    if not peaks:
        raise ValueError("true-peak measurement missing")
    return float(peaks[-1])


def video_audit(output,offsets,expected):
    mov,mp4 = output/"story.mov",output/"story.mp4"
    count = offsets[-1][1]
    for path in (mov,mp4):
        probe = media._probe(path,"ffprobe")
        if len(probe["streams"]) != 2:
            raise ValueError("unexpected stream count")
        v,a = probe["streams"]
        if (v["width"],v["height"],Fraction(v["avg_frame_rate"]),int(v["nb_read_frames"]),v["color_space"]) != (W,H,FPS,count,"bt709"):
            raise ValueError("unexpected encoded video geometry")
        if (a["sample_rate"],a["channels"]) != (str(RATE),2):
            raise ValueError("unexpected encoded audio geometry")
        for stream in (a,v):
            if int(stream["duration_ts"])*Fraction(stream["time_base"]) != Fraction(count,FPS):
                raise ValueError("unexpected stream duration")
    if media._video_hash(mov,"ffmpeg") != media._video_hash(mp4,"ffmpeg"):
        raise ValueError("preview altered assembled encoded picture")
    v = probe["streams"][0]
    pts = json.loads(subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0",
        "-show_frames","-show_entries","frame=best_effort_timestamp","-of","json",str(mp4)]))["frames"]
    if [int(p["best_effort_timestamp"])*Fraction(v["time_base"]) for p in pts] != [Fraction(i,FPS) for i in range(count)]:
        raise ValueError("incorrect decoded frame clocks")
    pcm = decoded_audio(mov,"s32le","<i4") // 256
    if not np.array_equal(pcm,expected):
        raise ValueError("MOV changed audio samples")
    signal = decoded_audio(mp4,"f32le","<f4")[:len(pcm)]
    if len(signal) != len(pcm) or np.abs(signal).max() >= 1:
        raise ValueError("preview audio clipped or truncated")
    ref = pcm.astype(np.float64)/8388608
    snr = float(10*np.log10(np.mean(ref**2)/max(np.mean((ref-signal)**2),1e-19)))
    if snr < 40:
        raise ValueError(f"AAC preview SNR {snr:.2f} dB")
    peaks = {p.suffix:true_peak(p) for p in (mov,mp4)}
    if max(peaks.values()) > -1:
        raise ValueError(f"true-peak margin failed: {peaks}")

    selection = sorted({0, count-1, 101, 110, 128, 182,
                        *(i for s,_ in offsets[1:] for i in (s-1,s,s+1))})
    sheet = Image.new("RGB",(1080,math.ceil(len(selection)/3)*223),"#181411")
    draw = ImageDraw.Draw(sheet)
    reader = cv2.VideoCapture(str(mp4))
    inventory = []
    try:
        for i in range(count):
            ok,img = reader.read()
            if not ok:
                raise ValueError(f"incomplete decoded frame {i}")
            inventory.append(sha256(img.tobytes()).hexdigest())
            if i in selection:
                x,y = selection.index(i)%3*360,selection.index(i)//3*223
                im = Image.fromarray(cv2.cvtColor(img,cv2.COLOR_BGR2RGB))
                sheet.paste(im.resize((360,202),Image.Resampling.LANCZOS),(x,y))
                draw.text((x+5,y+202),f"F{i:03}   {i/FPS:.2f}s",fill="white")
        if reader.read()[0]:
            raise ValueError("extra decoded frame")
    finally:
        reader.release()
    # Confirm concat did not substitute a boundary GOP: compare the first and
    # last decoded pixels of each actual encoded shot to the assembled movie.
    for index,(a,b) in enumerate(offsets,1):
        seg = cv2.VideoCapture(str(output/f"shot{index:02}.mp4"))
        try:
            for seek,dest in ((0,a),(b-a-1,b-1)):
                seg.set(cv2.CAP_PROP_POS_FRAMES,seek)
                ok,frame = seg.read()
                if not ok or sha256(frame.tobytes()).hexdigest()!=inventory[dest]:
                    raise ValueError(f"packet-copy boundary mismatch at {dest}")
        finally:
            seg.release()
    sheet.save(output/"decoded-cuts.jpg",quality=94)
    return {"video_frames":len(inventory),"pts_exact":True,"boundary_frames_equal_shots":True,
            "mp4_mov_picture_packets_equal":True,"mov_exact_mix_pcm":True,"aac_snr_db":snr,
            "aac_peak":float(np.abs(signal).max()),"true_peak_dbtp":peaks}


def finish_preview(recipe,output,plan,offsets,mix,events):
    """Mux only audio into the already assembled master, then verify."""
    mov,mp4,wav = output/"story.mov",output/"story.mp4",output/"story-mix.wav"
    # A millisecond movie header tick truncated 16 samples in the first AAC
    # mux. A 48-kHz movie timescale divides both the audio and picture clocks.
    media._run(["ffmpeg","-nostdin","-v","error","-n","-i",str(mov),"-map","0:v:0","-map","0:a:0",
                 "-c:v","copy","-c:a","aac","-b:a","512k","-movie_timescale","48000",
                 "-video_track_timescale","30000","-movflags","+faststart+write_colr",str(mp4)],output/"mux-mp4.log")
    technical = video_audit(output,offsets,mix)
    report = {"recipe_sha256":digest(recipe),"renderer_sha256":digest(Path(__file__)),
              "source_assets":plan["sources"],"shots_output_span_half_open":offsets,
              "voice_status":"NON_CANONICAL_LOCAL_SCRATCH_VOICE_NOT_HUMAN_ACCEPTED",
              "human_accepted":False,"production_release":False,"cost":0,
              "events":events,**technical,
              "sha256":{p.name:digest(p) for p in (mp4,mov,wav)}}
    media._json(output/"verification.json",report)
    return report


def build(recipe,output):
    if output.exists():
        raise FileExistsError(output)
    plan,assets,offsets = plan_from(recipe)
    mix,effects,voice,events = sound(plan,assets)
    if len(mix)!=offsets[-1][1]*STEP or not np.array_equal(mix.astype(np.int64)-effects,voice):
        raise ValueError("mix clock or original voice altered")
    output.mkdir(parents=True,exist_ok=False)
    wav = output/"story-mix.wav"
    foley.audio.ledger_pour._write_pcm24_wave(wav,mix,RATE)
    for i,shot in enumerate(plan["shots"],1):
        encode_shot(assets[shot["source"]],shot["span"],output/f"shot{i:02}.mp4",output/f"encode-{i}.log")
    listing = output/"shots.ffconcat"
    listing.write_text("ffconcat version 1.0\n"+"".join(f"file 'shot{i:02}.mp4'\n" for i in range(1,4)),
                       encoding="utf-8",newline="\n")
    flags = ["-map","0:v:0","-map","1:a:0","-c:v","copy","-video_track_timescale","30000","-movflags","+faststart+write_colr"]
    prefix = ["ffmpeg","-nostdin","-v","error","-n"]
    mov = output/"story.mov"
    media._run(prefix+["-f","concat","-safe","1","-i",str(listing),"-i",str(wav)]+flags+
               ["-c:a","pcm_s24le",str(mov)],output/"mux-mov.log")
    return finish_preview(recipe,output,plan,offsets,mix,events)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe",type=Path,default=RECIPE)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.recipe,args.output),indent=2))
