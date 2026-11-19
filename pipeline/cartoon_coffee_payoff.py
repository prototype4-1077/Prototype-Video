"""Extend the verified visitor cut with a visible hand approach and coffee payoff."""
from __future__ import annotations

import argparse
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from pipeline import cartoon_coffee_thank_you as handoff
from pipeline import cartoon_compassion_review as probe


ROOT=handoff.ROOT
cut=probe.cut
JOIN=912
LEAD=11
ADDED=LEAD+handoff.N
TOTAL=cut.COUNT+ADDED
SOURCE_SHA="0713f310a26a9dee8f004e48aef7d6403b0155e7f35479a838a488014caeed6b"
RAW_LOCK=ROOT/"collab/june_coffee_thank_you_motion_v1/handoff-proof.json"
RAW_LOCK_SHA="59cf9ca32a2ca3b9bf45eef7ae3a5078ea073bee2264a8b30749a47958498472"
REVIEW_BASE=(868,1007)
LOCKED_MIX_SHA="8c1ad3abe1c2efa3808b9de1febc7e70cda408d1760da080267aeabceb4417de"


def reach_cue(i):
    if type(i) is not int or not 0<=i<=LEAD:
        raise ValueError("outside lead-in")
    # Use the open right-hand key at the start of the lead-in. Ease into
    # contact without moving the cup or the guest. The previous wide shot
    # had June's left hand on the mug, so this is visibly a new reach.
    return handoff.Cue(-handoff.SLIDE,0.,1.-handoff.smooth(i,1,LEAD),0.)


def frame(p,i):
    if type(i) is not int or not 0<=i<ADDED:
        raise ValueError("outside added picture span")
    if i>=LEAD:
        return handoff.paint(p,i-LEAD)
    cue=reach_cue(i)
    with patch.object(handoff,"cues",return_value=cue):
        return handoff.paint(p,0)


def render_insert(file=None):
    if cut.beat.digest(RAW_LOCK)!=RAW_LOCK_SHA:
        raise ValueError("original handoff inventory changed")
    pinned=json.loads(RAW_LOCK.read_text(encoding="utf-8"))
    if cut.beat.digest(Path(handoff.__file__))!=pinned["renderer_sha256"]:
        raise ValueError("original handoff renderer changed")
    p=handoff.prepare()
    raw=[]
    def render(to):
        for i in range(ADDED):
            art=frame(p,i)
            raw.append(sha256(art).hexdigest())
            if to is not None:
                with Image.fromarray(art) as photo:
                    to.write(photo.resize((1920,1080),Image.Resampling.LANCZOS).tobytes())
    if file is None:
        render(None)
    else:
        with file.with_suffix(".log").open("wb") as log,subprocess.Popen(
            cut.media.encoder_command("ffmpeg",file),stdin=subprocess.PIPE,stderr=log
        ) as proc:
            try:
                render(proc.stdin)
            finally:
                proc.stdin.close()
            if proc.wait():
                raise ValueError("coffee payoff picture encoder failed")
    if raw[LEAD:]!=pinned["rgb24_native_frame_sha256"] or len(set(raw[:LEAD]))<9:
        raise ValueError("lead-in or isolated handoff source drifted")
    return raw


def extend_sound(original):
    split=JOIN*cut.STEP
    if original.shape!=(cut.COUNT*cut.STEP,2) or np.any(original[split-1440:split+1440]):
        raise ValueError("approved soundtrack is not silent around the edit")
    pad=np.zeros((ADDED*cut.STEP,2),dtype=original.dtype)
    return np.concatenate((original[:split],pad,original[split:]))


def extend_captions(original):
    out=deepcopy(original)
    shifted=0
    for row in out["dialogue_cues"]:
        if row["start_frame"]<=JOIN<row["end_frame"]:
            raise ValueError(f'cannot interrupt spoken cue {row["id"]}')
        if row["start_frame"]>JOIN:
            row["start_frame"]+=ADDED
            row["end_frame"]+=ADDED
            shifted+=1
    if len(out["dialogue_cues"])!=18 or shifted!=4:
        raise ValueError("unexpected caption count")
    return out


def copy_picture(before,out,first,stop):
    seek=["-ss",str(first/30)] if first else []
    cut.media._run(cut.CLI+seek+["-i",str(before),"-map","0:v:0","-c:v","copy",
        "-frames:v",str(stop-first),"-video_track_timescale","30000",str(out)],out.with_suffix(".log"))


def audit_packets(before,after):
    v0,v1=(probe.packet_info(path,"v:0") for path in (before,after))
    if len(v0)!=cut.COUNT or len(v1)!=TOTAL:
        raise ValueError("wrong picture packet census")
    if {int(r["pts"]) for r in v1}!={i*1000 for i in range(TOTAL)}:
        raise ValueError("presentation clock shifted")
    for i in (0,JOIN,JOIN+ADDED):
        if "K" not in v1[i]["flags"]:
            raise ValueError(f"not a closed edit at packet {i}")
    if probe.signature(v0[:JOIN])!=probe.signature(v1[:JOIN]):
        raise ValueError("image packets before the new shot changed")
    tail=[(pts-ADDED*1000,dts-ADDED*1000,dt,h,s)
          for pts,dts,dt,h,s in probe.signature(v1[JOIN+ADDED:])]
    if tail!=probe.signature(v0[JOIN:]):
        raise ValueError("ending packets failed the exact-contents/shift check")


def exact_after_decode(before,after):
    base,new=(cv2.VideoCapture(str(p)) for p in (before,after))
    accepted=0
    try:
        for i in range(TOTAL):
            ok,b=new.read()
            if not ok:
                raise ValueError(f"could not decode alternate frame {i}")
            if JOIN<=i<JOIN+ADDED:
                continue
            a_ok,a=base.read()
            if not a_ok or not np.array_equal(a,b):
                raise ValueError(f"changed a previous frame at alternate frame {i}")
            accepted+=1
        if accepted!=1140 or base.read()[0] or new.read()[0]:
            raise ValueError("did not retain every existing picture")
    finally:
        base.release()
        new.release()
    return accepted


def audit_delivery(movie,mp4,seconds,pcm,srt):
    for path in (movie,mp4):
        rows={s["codec_type"]:s for s in cut.media._probe(path,"ffprobe")["streams"]}
        if set(rows)!={"video","audio","subtitle"}:
            raise ValueError("changed delivery streams")
        v,a=rows["video"],rows["audio"]
        if (v["width"],v["height"],int(v["nb_read_frames"]),v["avg_frame_rate"],
                v.get("color_space"),a["sample_rate"],a["channels"])!=(1920,1080,TOTAL,"30/1","bt709","48000",2):
            raise ValueError("new scene geometry or time base changed")
        if any(int(s["start_pts"]) or int(s["duration_ts"])*Fraction(s["time_base"])!=seconds for s in (v,a)):
            raise ValueError("unexpected video/audio duration")
    expected_text=srt.read_text(encoding="utf-8").strip()
    embedded=subprocess.check_output(["ffmpeg","-nostdin","-v","error","-i",str(mp4),
                   "-map","0:s:0","-f","srt","-"]).decode("utf-8").replace("\r\n","\n").strip()
    if expected_text!=embedded:
        raise ValueError("embedded captions drifted relative to exact cue offset")
    raw=cut.beat.decoded_audio(movie,"s32le","<i4")//256
    if not np.array_equal(raw,pcm):
        raise ValueError("extended PCM is not a pure silent insertion")
    decoded=cut.beat.decoded_audio(mp4,"f32le","<f4")[:len(pcm)]
    if len(decoded)!=len(pcm) or abs(decoded).max()>=1:
        raise ValueError("AAC review lost samples or clipped")
    ref=pcm.astype(np.float64)/8388608.
    snr=float(10*np.log10(np.mean(ref**2)/max(np.mean((ref-decoded)**2),1e-20)))
    if snr<40:
        raise ValueError(f"unexpected AAC degradation ({snr:.2f} dB)")
    return snr


def excerpt(movie,out,first,stop,pcm):
    for i in (first,stop):
        if np.any(pcm[i*cut.STEP-1440:i*cut.STEP+1440]):
            raise ValueError("the review excerpt cuts a spoken line")
    count=stop-first
    length=count/30
    af=(f"atrim=end_sample={count*cut.STEP},asetpts=PTS-STARTPTS,"
        f"afade=t=in:d=0.03,afade=t=out:st={length-.03:.6f}:d=0.03")
    cut.media._run(cut.CLI+["-ss",str(first/30),"-i",str(movie),"-map","0:v:0","-map","0:a:0",
        "-vf",f"trim=end_frame={count},setpts=PTS-STARTPTS,scale=1280:720","-af",af,
        "-c:v","libx264","-threads","4","-crf","16","-pix_fmt","yuv420p","-colorspace","bt709",
        "-color_primaries","bt709","-color_trc","bt709","-c:a","aac","-b:a","256k","-ar","48000",
        "-video_track_timescale","30000","-movie_timescale","48000","-movflags","+faststart",str(out)],
        out.with_suffix(".log"))
    v,a=cut.media._probe(out,"ffprobe")["streams"]
    if int(v["nb_read_frames"])!=count or any(abs(float(s["duration"])-length)>.001 for s in (v,a)):
        raise ValueError("review excerpts drifted")
    return cut.beat.digest(out)


def finish_review(before,output,original,mix,hashes):
    srt=output/"captions.srt"
    mp4=output/"twelve-dollar-mug.mp4"
    mov=mp4.with_suffix(".mov")
    print("Checking every retained picture and the shifted closing audio ...",flush=True)
    audit_packets(before,mp4)
    snr=audit_delivery(mov,mp4,Fraction(TOTAL,30),mix,srt)
    exact=exact_after_decode(before,mp4)
    first,old_stop=REVIEW_BASE
    control=excerpt(before,output/"ending-without-handoff.mp4",first,old_stop,original)
    alternate=excerpt(mp4,output/"ending-with-handoff.mp4",first,old_stop+ADDED,mix)
    result={"source_sha256":SOURCE_SHA,"candidate_sha256":cut.beat.digest(mp4),"clock":[1920,1080,30,TOTAL],
            "builder_sha256":cut.beat.digest(Path(__file__)),
            "inserted_span":[JOIN,JOIN+ADDED],"right_hand_lead_in_frames":LEAD,
            "original_picture_packets_preserved":1140,"original_decoded_frames_exact":exact,
            "original_handoff_native_frames_exact":handoff.N,"new_native_rgb24_sha256":hashes,
            "closing_shift_frames":ADDED,"closing_shift_pcm_sample_pairs":ADDED*cut.STEP,
            "added_audio":"digital silence","pcm_before_and_after_insertion_exact":True,"caption_lines_retained":18,
            "caption_text_and_cue_shift_verified":True,"preview_aac_reencoded":True,"preview_aac_snr_db":snr,
            "excerpt_base_span":[first,old_stop],"excerpt_new_span":[first,old_stop+ADDED],
            "excerpt_base_sha256":control,"excerpt_new_sha256":alternate,
            "human_accepted":False,"production_release":False}
    cut.media._json(output/"payoff-verification.json",result)
    return result


def build(before,output):
    if cut.beat.digest(before)!=SOURCE_SHA:
        raise ValueError("expected the exact clean visitor review")
    if cut.beat.digest(probe.PACKAGE/"mix.wav")!=LOCKED_MIX_SHA:
        raise ValueError("original story mix changed")
    output.mkdir(parents=True,exist_ok=False)
    plan,paths,contract=cut.load_plan()
    original,_=cut.full_mix(plan,paths,contract)
    mix=extend_sound(original)
    wav,srt=output/"mix.wav",output/"captions.srt"
    cut.foley.audio.ledger_pour._write_pcm24_wave(wav,mix,cut.RATE)
    cut.foley.audio.golden_sound.write_captions(extend_captions(contract),srt)
    prefix,insert,suffix=(output/f"{k}.mp4" for k in ("prefix","exchange","suffix"))
    print("Rendering the right-hand approach and the handoff ...",flush=True)
    hashes=render_insert(insert)
    copy_picture(before,prefix,0,JOIN)
    copy_picture(before,suffix,JOIN,1140)
    if len({probe.codec_hash(p) for p in (before,prefix,insert,suffix)})!=1:
        raise ValueError("AVC settings of the three edit sections differ")
    listing=output/"payoff.ffconcat"
    listing.write_text("ffconcat version 1.0\nfile 'prefix.mp4'\nfile 'exchange.mp4'\nfile 'suffix.mp4'\n",
                       encoding="utf-8",newline="\n")
    cut.mux(output,listing,wav,srt)
    return finish_review(before,output,original,mix,hashes)


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--before",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    args=ap.parse_args()
    print(json.dumps({k:v for k,v in build(args.before,args.output).items()
                      if k!="new_native_rgb24_sha256"},indent=2))
