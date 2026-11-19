"""Assemble GS060 pickup/return into the exact 38-second pencil-continuity cut."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline import cartoon_coffee_acting as acting
from pipeline import cartoon_compassion_review as old
from pipeline import cartoon_full_short_source as source
from pipeline import cartoon_pour_layers as pour


cut=old.cut
PLAN=(0,678,789,864,912,1140)
CHANGE=((678,789),(864,912))
SAME_NATIVE=((762,789),(864,882))
SOURCE_SHA="5b20ac2291a136798a09aa061853dc12d22f89dc06b88b72829d131d6abc4a1e"
REVIEW=(661,930)
PICK=(678,705,714,721,727,732,738,745,753,761,762,788,789,863,864,
      877,883,890,900,905,911,912)


def new_layer(original_lift, legacy_rgb, p, i):
    kind,t=acting.timing(i)
    if kind=="original" or (kind=="lift" and t==1):
        return None
    animation=acting.raw_frame(p,kind,t)
    # The source drawings derive from raw POSE_45, whose frozen painted
    # fore/midground is already registered x=-16 px into the camera.
    # Transfer changed pixels only; retain clean porch where the original
    # extraction used it, and leave mug/face appearance on the shot clock.
    changed=animation[:,16:].astype(np.int16)-original_lift[:,16:]
    mixed=legacy_rgb.copy()
    mixed[:,:-16]=np.clip(legacy_rgb[:,:-16].astype(np.int16)+changed,0,255).astype(np.uint8)
    return Image.fromarray(mixed).convert("RGBA")


def do_frames(output, inspect_only=False):
    p=acting.prepare()
    digests={}
    samples={}
    with source.render_inputs() as (_,_,_,active):
        contract,bg,layers,smears=active
        pose="POSE_45_POT_LIFT"
        declared=next(row for row in contract["poses"] if row["id"]==pose)
        if pour.registration_offset(declared,contract["contact_registration"])!=(-16,0):
            raise ValueError("legacy POSE_45 registration changed")
        with Image.alpha_composite(bg.convert("RGBA"),layers[pose]).convert("RGB") as fixed:
            legacy_rgb=np.array(fixed)
        for a,b in CHANGE:
            clip=output/f"new-{a}.mp4"
            cmd=cut.media.encoder_command("ffmpeg",clip)
            selected=range(a,b) if not inspect_only else [i for i in PICK if a<=i<b]
            def pixels(i):
                local=i-677
                row=pour.timeline_entry_for_frame(contract["timeline"],local)
                layer=new_layer(p.lift.lifted,legacy_rgb,p,i)
                generated=layer is not None
                if not generated:
                    # Smooth motion already leads into F761; the original
                    # smear there was covering the wrong-hand hard switch.
                    layer=layers[pose] if i==761 else (layers[row["pose_id"]] if row["type"]=="pose" else smears[local])
                pic=None
                try:
                    pic,metrics=pour.compose_pour_frame(bg,layer,contract,local)
                    if metrics["rendered_spill_pixels_source"] or metrics["spout_start_error_px_source"]:
                        raise ValueError(f"liquid missed the mug at F{i}")
                    if i in PICK:
                        samples[i]=pic.resize((384,216),Image.Resampling.LANCZOS)
                    return pic.tobytes()
                finally:
                    if generated:
                        layer.close()
                    if pic is not None:
                        pic.close()
            if inspect_only:
                for i in selected:
                    pixels(i)
                continue
            with clip.with_suffix(".log").open("wb") as log,subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log) as proc:
                try:
                    for i in selected:
                        raw=pixels(i)
                        digests[i]=sha256(raw).hexdigest()
                        proc.stdin.write(raw)
                finally:
                    proc.stdin.close()
                if proc.wait():
                    raise ValueError(f"encoder failed at span {a}:{b}")
    sheet=Image.new("RGB",(3*384,232*((len(samples)+2)//3)),"#1b1513")
    draw=ImageDraw.Draw(sheet)
    for j,(i,pic) in enumerate(samples.items()):
        x,y=(j%3)*384,(j//3)*232
        sheet.paste(pic,(x,y))
        stage,t=acting.timing(i)
        draw.text((x+5,y+216),f"F{i}  {stage}  {t:.2f}",fill="white")
        pic.close()
    sheet.save(output/"native-action-poses.jpg",quality=95)
    return digests


def packet_audit(before,after):
    b=old.packet_info(before,"v:0")
    a=old.packet_info(after,"v:0")
    if len(b)!=1140 or len(a)!=1140:
        raise ValueError("full-cut frame count changed")
    retained=0
    for first,stop in zip(PLAN,PLAN[1:]):
        wanted={i*1000 for i in range(first,stop)}
        for rows in (b[first:stop],a[first:stop]):
            if "K" not in rows[0]["flags"] or {int(r["pts"]) for r in rows}!=wanted:
                raise ValueError(f"non-closed splice {first}:{stop}")
        same=old.signature(a[first:stop])==old.signature(b[first:stop])
        if (first,stop) in CHANGE:
            if same:
                raise ValueError(f"change missing at frame {first}")
        else:
            if not same:
                raise ValueError(f"copy drifted at frame {first}")
            retained+=stop-first
    for stream in ("a:0","s:0"):
        if old.signature(old.packet_info(before,stream))!=old.signature(old.packet_info(after,stream)):
            raise ValueError(f"revised {stream} was not bitstream copied")
    return retained


def comparison(output,before,after,pcm):
    a,b=REVIEW
    step=1600
    count=b-a
    duration=count/30
    for index in REVIEW:
        if np.any(pcm[index*step-1440:index*step+1440]):
            raise ValueError("review audio edge is not silent")
    out=output/"coffee-continuity-review.mp4"
    trim=f"trim=end_frame={count},setpts=PTS-STARTPTS,scale=768:432"
    audio=f"atrim=end_sample={count*step},asetpts=PTS-STARTPTS,afade=t=in:d=0.03,afade=t=out:st={duration-.03:.6f}:d=0.03"
    filters=f"[0:v]{trim}[l];[1:v]{trim}[r];[l][r]hstack[v];[0:a]{audio}[snd]"
    cut.media._run(cut.CLI+["-ss",str(a/30),"-i",str(before),"-ss",str(a/30),"-i",str(after),
        "-filter_complex",filters,"-map","[v]","-map","[snd]","-c:v","libx264","-threads","4",
        "-crf","16","-pix_fmt","yuv420p","-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709",
        "-c:a","aac","-b:a","256k","-ar","48000","-movie_timescale","48000","-movflags","+faststart",str(out)],
        out.with_suffix(".log"))
    v,s=cut.media._probe(out,"ffprobe")["streams"]
    if int(v["nb_read_frames"])!=count or any(abs(float(z["duration"])-duration)>.001 for z in (v,s)):
        raise ValueError("review excerpt drifted")
    return cut.beat.digest(out)


def build(before,output):
    output.mkdir(parents=True,exist_ok=False)
    if cut.beat.digest(before)!=SOURCE_SHA:
        raise ValueError("not the exact pencil-continuity full candidate")
    pcm=old.PACKAGE/"mix.wav"
    plan,paths,contract=cut.load_plan()
    samples,_=cut.full_mix(plan,paths,contract)
    native=do_frames(output)
    clips=[]
    for a,b in zip(PLAN,PLAN[1:]):
        if (a,b) in CHANGE:
            path=output/f"new-{a}.mp4"
        else:
            path=output/f"copied-{a}.mp4"
            seek=[] if a==0 else ["-ss",str(a/30)]
            cut.media._run(cut.CLI+seek+["-i",str(before),"-map","0:v:0","-frames:v",str(b-a),
                "-c:v","copy","-video_track_timescale","30000",str(path)],path.with_suffix(".log"))
        clips.append(path)
    if len({old.codec_hash(path) for path in [before,*clips]})!=1:
        raise ValueError("splice codec descriptors differ")
    listing=output/"clips.ffconcat"
    listing.write_text("ffconcat version 1.0\n"+"".join(f"file '{p.name}'\n" for p in clips),
                       encoding="utf-8",newline="\n")
    film=output/"twelve-dollar-mug-coffee-continuity-v1.mp4"
    master=film.with_suffix(".mov")
    clocks=["-video_track_timescale","30000","-movie_timescale","48000","-movflags","+faststart+write_colr"]
    cut.media._run(cut.CLI+["-f","concat","-safe","1","-auto_convert","0","-i",str(listing),
        "-i",str(before),"-map","0:v:0","-map","1:a:0","-map","1:s:0","-c","copy",*clocks,str(film)],
        output/"mux.log")
    kept=packet_audit(before,film)
    cut.media._run(cut.CLI+["-i",str(film),"-i",str(pcm),"-map","0:v:0","-map","1:a:0","-map","0:s:0",
         "-c","copy","-c:a","pcm_s24le",*clocks,str(master)],output/"mux-pcm.log")
    checked=cut.audit(output,master,film,samples,paths["repaired"])
    if any(checked["same_view_join_mae"][n]>limit for n,limit in (("789",6.5),("864",5.0))):
        raise ValueError("too much new mismatch at a locked-pour join")
    ab=comparison(output,before,film,samples)
    receipt={"clock":[1920,1080,30,1140],"source_sha256":SOURCE_SHA,"candidate_sha256":cut.beat.digest(film),
        "source_assets":{"parked":acting.PARK_SHA,"pencil":acting.POISED_SHA,**acting.lift.HASHES},
        "renderer_sha256":{Path(n).name:cut.beat.digest(Path(n)) for n in (__file__,acting.__file__,acting.lift.__file__)},
        "replaced_spans":CHANGE,"unchanged_video_packets":kept,"original_pose_reused_native_spans":SAME_NATIVE,
        "audio_subtitle_packets_exact":True,"human_accepted":False,"production_release":False,
        "review_span":REVIEW,"review_sha256":ab,**checked}
    cut.media._json(output/"verification.json",receipt)
    cut.media._json(output/"new-native-digests.json",native)
    return receipt


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--before",type=Path)
    args=parser.parse_args()
    if args.before:
        print(json.dumps(build(args.before,args.output),indent=2))
    else:
        args.output.mkdir(parents=True,exist_ok=False)
        do_frames(args.output,inspect_only=True)
