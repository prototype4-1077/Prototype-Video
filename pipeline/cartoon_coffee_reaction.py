"""Test a quiet visitor close-up after the coffee handoff, with the original closer intact."""
from __future__ import annotations

import argparse
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch

import numpy as np
from PIL import Image

from pipeline import cartoon_ledger_reverse as ledger
from pipeline import cartoon_visitor_return as art


BASE_SHA = "ac132f7b63469231f9fb1eebf2bbd81f8459406daa44eda2111b494be4f655a0"
JOIN, N = 963, 30
BASE_TOTAL, TOTAL = ledger.TOTAL, ledger.TOTAL+N
REVIEW = (868, 1131)
CROP = (416, 0, 1376, 540)
SUPPORT = [(841,208),(864,177),(898,171),(970,181),(1037,199),(1079,239),
           (1075,278),(1048,286),(974,281),(944,252),(875,245)]
reg, cut, probe, digest = art.reg, ledger.cut, ledger.probe, ledger.digest
payoff = ledger.prior.payoff


def expression(i):
    if type(i) is not int or not 0 <= i < N:
        raise ValueError("visitor reaction clock")
    # Read the offer, lift the eyes, then hold. No second blinking rig.
    return .87*art.layer.smooth(i, 6, 19)


def scene():
    first, last = art.load()
    region = reg.region(first, last, art.E, art.EYE_PAIRS, SUPPORT)
    return first, region


def frame(plate, region, i):
    t = expression(i)
    image = plate.copy()
    if t:
        reg.apply_region(image,reg.paint_pair(region,t)[0],region)
    return image[reg.window(CROP)].copy()


def render(path):
    plate,region = scene()
    source_hashes = []
    with path.with_suffix(".log").open("wb") as log, subprocess.Popen(
            cut.media.encoder_command("ffmpeg",path),stdin=subprocess.PIPE,stderr=log) as proc:
        try:
            for i in range(N):
                image = frame(plate,region,i)
                source_hashes.append(sha256(image).hexdigest())
                proc.stdin.write(Image.fromarray(image).resize(
                    (1920,1080),Image.Resampling.LANCZOS).tobytes())
        finally:
            proc.stdin.close()
        if proc.wait():
            raise ValueError("could not encode the visitor reaction")
    if len(set(source_hashes)) < 12:
        raise ValueError("reaction has no authored eye-lift")
    return source_hashes


def open_existing_shot(path, from_path, checked_sha):
    if not checked_sha or digest(from_path) != checked_sha:
        raise ValueError("explicit preserved shot hash required")
    ledger.prior.validate_gops(probe.packet_info(from_path,"v:0"),(0,N))
    if len(ledger.frame_hashes(from_path)) != N:
        raise ValueError("truncated preserved reaction")
    shutil.copyfile(from_path,path)
    plate,region = scene()
    return [sha256(frame(plate,region,i)).hexdigest() for i in range(N)]


def pad_silence(samples):
    if samples.shape != (BASE_TOTAL*cut.STEP,2):
        raise ValueError("unexpected source soundtrack clock")
    at = JOIN*cut.STEP
    if np.any(samples[at-1440:at+1440]):
        raise ValueError("the reaction overlaps non-silent sound")
    return np.concatenate((samples[:at],np.zeros((N*cut.STEP,2),samples.dtype),samples[at:]))


def shift_captions(original):
    cues = deepcopy(original)
    lines = cues["dialogue_cues"]
    if len(lines) != 18 or sum(row["start_frame"]>JOIN for row in lines) != 4:
        raise ValueError("wrong whole-film captions")
    for row in lines:
        if row["start_frame"]<=JOIN<row["end_frame"]:
            raise ValueError("would interrupt a caption mid-line")
        if row["start_frame"]>JOIN:
            row["start_frame"] += N
            row["end_frame"] += N
    return cues


def audit_picture(before, after, new):
    old, edited, shot = (probe.packet_info(p,"v:0") for p in (before,after,new))
    ledger.prior.validate_gops(old,(0,JOIN,BASE_TOTAL))
    ledger.prior.validate_gops(edited,(0,JOIN,JOIN+N,TOTAL))
    ledger.prior.validate_gops(shot,(0,N))
    def offset(rows,n):
        return [(a+n*1000,b+n*1000,d,h,side) for a,b,d,h,side in probe.signature(rows)]
    if (probe.signature(edited) != probe.signature(old[:JOIN]) +
        offset(shot,JOIN) + offset(old[JOIN:],N)):
        raise ValueError("changed or re-encoded a retained picture packet")
    old, edited, shot = (ledger.frame_hashes(p) for p in (before,after,new))
    if ((len(old),len(edited),len(shot)) != (BASE_TOTAL,TOTAL,N) or
        edited != old[:JOIN]+shot+old[JOIN:]):
        raise ValueError("changed retained decoded pixels")
    return len(old)


def embedded(path):
    return subprocess.check_output(["ffmpeg","-v","error","-i",str(path),
        "-map","0:s:0","-f","srt","-"]).decode("utf-8").replace("\r\n","\n").strip()


def mux(output, listing, wav, srt):
    # The usual concat's Annex B round trip injects/tidies parameter-set NALs
    # at some reviewed cuts. All three inputs here share one AVC configuration,
    # so disable that conversion and verify each packet after delivery.
    mov,mp4 = output/"twelve-dollar-mug.mov",output/"twelve-dollar-mug.mp4"
    maps = ["-map","0:v:0","-map","1:a:0","-map","2:s:0"]
    clocks = ["-video_track_timescale","30000","-movie_timescale","48000",
              "-movflags","+faststart+write_colr"]
    cut.media._run(cut.CLI+["-f","concat","-safe","1","-auto_convert","0",
        "-i",str(listing),"-i",str(wav),"-i",str(srt)]+maps+
        ["-c:v","copy","-c:a","pcm_s24le","-c:s","mov_text",
         "-metadata:s:s:0","language=eng","-disposition:s:0","0"]+clocks+[str(mov)],
        output/"mux-mov.log")
    cut.media._run(cut.CLI+["-i",str(mov),"-map","0:v:0","-map","0:a:0","-map","0:s:0",
        "-c:v","copy","-c:a","aac","-b:a","512k","-c:s","copy",
        "-disposition:s:0","0"]+clocks+[str(mp4)],output/"mux-mp4.log")
    return mov,mp4


def build(before, pcm, output, *, existing_shot=None, checked_sha=None):
    if digest(before)!=BASE_SHA or digest(pcm)!=ledger.SOURCE_PCM_SHA:
        raise ValueError("not the exact current short and original soundtrack")
    ledger.prior.validate_gops(probe.packet_info(before,"v:0"),(0,JOIN,BASE_TOTAL))
    original,pmeta = cut.foley.audio.ledger_pour._read_pcm24_wave(pcm)
    if pmeta["sample_rate"] != 48000:
        raise ValueError("soundtrack must be 48kHz")
    mix = pad_silence(original)
    _,_,contract = cut.load_plan()
    existing_captions = payoff.extend_captions(contract)
    captions = shift_captions(existing_captions)
    output.mkdir(parents=True,exist_ok=False)
    wav,srt = output/"mix.wav",output/"captions.srt"
    base_srt = output/"source-captions.srt"
    cut.foley.audio.golden_sound.write_captions(existing_captions,base_srt)
    if base_srt.read_text(encoding="utf-8").strip() != embedded(before):
        raise ValueError("the source caption text/timing does not match the receipt")
    cut.foley.audio.ledger_pour._write_pcm24_wave(wav,mix,48000)
    cut.foley.audio.golden_sound.write_captions(captions,srt)
    prefix,new,suffix = (output/f"{name}.mp4" for name in ("prefix","reaction","suffix"))
    source_hashes = (render(new) if existing_shot is None
                     else open_existing_shot(new,existing_shot,checked_sha))
    payoff.copy_picture(before,prefix,0,JOIN)
    payoff.copy_picture(before,suffix,JOIN,BASE_TOTAL)
    if len({probe.codec_hash(p) for p in (prefix,new,suffix)}) != 1:
        raise ValueError("incompatible H.264 encoder configuration")
    listing = output/"reaction.ffconcat"
    listing.write_text("ffconcat version 1.0\nfile 'prefix.mp4'\nfile 'reaction.mp4'\nfile 'suffix.mp4'\n",
                       encoding="ascii")
    mov,mp4 = mux(output,listing,wav,srt)
    picture = audit_picture(before,mp4,new)
    with patch.object(payoff,"TOTAL",TOTAL):
        snr = payoff.audit_delivery(mov,mp4,Fraction(TOTAL,30),mix,srt)
    first,stop = REVIEW
    control,variant = output/"ending-handoff-only.mp4",output/"ending-with-visitor-reaction.mp4"
    review_shas = [payoff.excerpt(before,control,first,stop,original),
                   payoff.excerpt(mp4,variant,first,stop+N,mix)]
    result = {
        "base_sha256": BASE_SHA, "source_pcm_sha256": ledger.SOURCE_PCM_SHA, "source_art": art.ART,
        "builder_sha256": digest(Path(__file__)), "native_picture_sha256": source_hashes,
        "movie_sha256": digest(mp4), "pcm_master_sha256": digest(mov), "reaction_sha256": digest(new),
        "reused_checked_shot": existing_shot is not None,
        "insert_frames": [JOIN,JOIN+N], "duration_seconds": TOTAL/30,
        "original_frames_retained": picture, "added_pcm_zero_pairs": N*cut.STEP,
        "original_audio_samples_exact_around_insertion": True, "review_aac_snr_db": snr,
        "caption_lines": 18, "caption_lines_shifted": 4, "closing_time_shift_frames": N,
        "old_excerpt_frames": REVIEW, "new_excerpt_frames": [first,stop+N], "excerpt_sha256": review_shas,
        "crop_xyxy": CROP,"human_accepted": False,"production_release": False,
    }
    cut.media._json(output/"coffee-reaction-proof.json",result)
    return result


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("before","pcm","output"):
        parser.add_argument("--"+flag,type=Path,required=True)
    parser.add_argument("--existing-shot",type=Path)
    parser.add_argument("--checked-shot-sha")
    args = parser.parse_args()
    print(json.dumps({k:v for k,v in build(args.before,args.pcm,args.output,
                      existing_shot=args.existing_shot,checked_sha=args.checked_shot_sha).items()
                      if k!="native_picture_sha256"},indent=2))
