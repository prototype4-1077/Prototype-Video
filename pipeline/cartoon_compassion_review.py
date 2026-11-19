"""Replace only GS050 in the committed full cut; copy everything else."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np

from pipeline import cartoon_compassion_acting as acting
from pipeline import cartoon_full_short as cut
from pipeline import cartoon_full_short_source as sources
from pipeline import cartoon_golden_master as golden


BASELINE = sources.REFERENCE
PACKAGE = BASELINE.parent
BASE_SHA256 = sources.REFERENCE_SHA256
START,STOP = acting.SPAN


def packet_info(path,selector):
    raw=subprocess.check_output(["ffprobe","-v","error","-select_streams",selector,
        "-show_packets","-show_data_hash","sha256","-of","json",str(path)])
    return json.loads(raw)["packets"]


def signature(rows):
    return [(int(p["pts"]),int(p["dts"]),int(p["duration"]),p["data_hash"],
             p.get("side_data_list",[])) for p in rows]


def locked_base():
    if cut.beat.digest(BASELINE)!=BASE_SHA256:
        raise ValueError("full-cut comparison bytes changed")
    packets=packet_info(BASELINE,"v:0")
    if len(packets)!=1140:
        raise ValueError("unexpected baseline video packet count")
    for a,b in ((0,START),(START,STOP),(STOP,1140)):
        if "K" not in packets[a]["flags"] or {int(p["pts"]) for p in packets[a:b]}!={i*1000 for i in range(a,b)}:
            raise ValueError("GS050 trims are not closed-GOP boundaries")
    return packets


def codec_hash(path):
    raw=subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0",
        "-show_entries","stream=extradata_hash","-show_data_hash","sha256","-of","json",str(path)])
    return json.loads(raw)["streams"][0]["extradata_hash"]


def copy_range(output,first,stop):
    seek=["-ss",str(first/30)] if first else []
    cut.media._run(cut.CLI+seek+["-i",str(BASELINE),"-map","0:v:0","-an","-c:v","copy",
        "-frames:v",str(stop-first),"-video_track_timescale","30000",str(output)],
        output.with_suffix(".log"))


def animate(output):
    p=acting.prepare()
    cmd=cut.media.encoder_command("ffmpeg",output)
    previous=None
    deltas=[[],[]]
    digests=[]
    zones=(acting.window(acting.HEAD_ROI), acting.window(acting.HAND_ROI))
    end=acting.load_art()["end"]
    old=[float(np.abs(p.start[z].astype(np.float32)-end[z]).mean()) for z in zones]
    with output.with_suffix(".log").open("wb") as log,subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log) as proc:
        try:
            for i in range(STOP-START):
                raw=acting.plate(p,i)
                if not np.array_equal(raw[:,943:],p.start[:,943:]):
                    raise ValueError("actor patch moved the mug or porch")
                if previous is not None:
                    for z,delta in zip(zones,deltas):
                        delta.append(float(np.abs(raw[z].astype(np.float32)-previous[z]).mean()))
                previous=raw
                frame=i+START+1
                with acting.Image.fromarray(raw) as art:
                    seg=golden.segment_for_frame(p.segments,frame)
                    with golden.compose_plate_frame(art,seg,frame) as deliver:
                        data=deliver.tobytes()
                proc.stdin.write(data)
                digests.append(sha256(data).hexdigest())
        finally:
            proc.stdin.close()
        if proc.wait():
            raise ValueError("GS050 encode failed")
    peak=[max(values) for values in deltas]
    if any(a>=.65*b for a,b in zip(peak,old)):
        raise ValueError(f"unexpected pose pop: {peak}; old jump {old}")
    return {"old_plate_region_jump_rgb_mae":old,"max_new_adjacent_region_rgb_mae":peak,
            "native_frames_changed":len(set(digests)),"input_art":acting.ASSETS},digests


def verify_copy(output,baseline):
    current=packet_info(output,"v:0")
    if len(current)!=1140:
        raise ValueError("replacement shifted video clock")
    for a,b in ((0,START),(STOP,1140)):
        if signature(current[a:b])!=signature(baseline[a:b]):
            raise ValueError("video outside GS050 was not packet-identical")
    for kind in ("a:0","s:0"):
        if signature(packet_info(output,kind))!=signature(packet_info(BASELINE,kind)):
            raise ValueError(f"{kind} bitstream, sample clock or priming changed")
    if all(a["data_hash"]==b["data_hash"] for a,b in zip(current[START:STOP],baseline[START:STOP])):
        raise ValueError("replacement picture did not land")


def build(output: Path):
    if output.exists():
        raise FileExistsError(output)
    baseline=locked_base()
    plan,paths,contract=cut.load_plan()
    original_mix,_=cut.full_mix(plan,paths,contract)
    pcm=PACKAGE/"mix.wav"
    if cut.beat.digest(pcm)!="8c1ad3abe1c2efa3808b9de1febc7e70cda408d1760da080267aeabceb4417de":
        raise ValueError("published full-cut mix changed")
    output.mkdir(parents=True,exist_ok=False)
    first,turn,last=[output/f"shot{i:02}.mp4" for i in range(1,4)]
    copy_range(first,0,START)
    motion,digests=animate(turn)
    copy_range(last,STOP,1140)
    cut.media._json(output/"gs050-native-frames.json",{"start_frame_zero_based":START,"rgb24_sha256":digests})
    if len({codec_hash(path) for path in (BASELINE,first,turn,last)})!=1:
        raise ValueError("could not prove compatible AVC configuration for exact packet copy")
    listing=output/"shots.ffconcat"
    listing.write_text("ffconcat version 1.0\nfile 'shot01.mp4'\nfile 'shot02.mp4'\nfile 'shot03.mp4'\n",
                       encoding="utf-8",newline="\n")
    preview,master=output/"twelve-dollar-mug-reaction-v1.mp4",output/"twelve-dollar-mug-reaction-v1.mov"
    clocks=["-video_track_timescale","30000","-movie_timescale","48000","-movflags","+faststart+write_colr"]
    cut.media._run(cut.CLI+["-f","concat","-safe","1","-auto_convert","0","-i",str(listing),"-i",str(BASELINE),
                       "-map","0:v:0","-map","1:a:0","-map","1:s:0","-c","copy"]+clocks+[str(preview)],output/"mux.log")
    cut.media._run(cut.CLI+["-i",str(preview),"-i",str(pcm),"-map","0:v:0","-map","1:a:0","-map","0:s:0",
                            "-c","copy","-c:a","pcm_s24le"]+clocks+[str(master)],output/"mux-pcm.log")
    verify_copy(preview,baseline)
    checked=cut.audit(output,master,preview,original_mix,paths["repaired"])
    result={"clock":[1920,1080,30,1140],"replaced_span_half_open":[START,STOP],
            "strictly_copied_video_packets":1140-STOP+START,"audio_subtitle_packets_exact":True,
            "motion":motion,"audit":checked,"human_accepted":False,"production_release":False,
            "baseline_sha256":BASE_SHA256,"candidate_sha256":cut.beat.digest(preview),
            "acting_source_sha256":cut.beat.digest(Path(acting.__file__)),
            "wrapper_source_sha256":cut.beat.digest(Path(__file__))}
    cut.media._json(output/"reaction-proof.json",result)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    print(json.dumps(build(parser.parse_args().output),indent=2))
