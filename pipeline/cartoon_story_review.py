"""Build the two full Twelve-Dollar Mug story reviews from tracked sources."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
from fractions import Fraction
from itertools import accumulate
import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from pipeline import cartoon_coffee_reaction as reaction
from pipeline import cartoon_current_review as previous
from pipeline import cartoon_ledger_reverse as ledger
from pipeline import cartoon_opening_loan as loan
from pipeline import cartoon_visitor_return as arrival


root, source, cut = previous.ROOT, previous.source, previous.cut
payoff, packets, digest = reaction.payoff, reaction.probe, reaction.digest
SHARED = (
    ("porch",129), ("loan",96), ("return",171), ("ledger-reverse",56),
    ("ledger-detail",112), ("visitor-pov",114), ("coffee-pickup",111),
    ("protected-pour",75), ("coffee-return",48), ("handoff",51),
)
CLOSER = ("protected-closer",228)
REACTION = ("coffee-reaction",30)
VARIANTS = {"handoff":("handoff",), "reaction":("reaction",), "both":("handoff","reaction")}
LOCKS = {
    "loan":("june_opening_loan_v1/opening-loan-proof.json",
            "bfcfbeb9b7458898e358f574990748469f274e83ba7ed0ea9d0ce6f55c4f521b"),
    "arrival":("june_visitor_return_v1/visitor-return-proof.json",
               "0de9c470a9b42bda57cb34d511c8d1459fa3a3507bc86def7754a8eb566d5f63"),
    "handoff":("june_coffee_payoff_v1/payoff-verification.json",
               "4c4899a9867531525315089524df2523bc07ff915cfb0330f446a6b68d456289"),
    "reaction":("june_coffee_reaction_v1/coffee-reaction-proof.json",
                "3f9521da8b8283e09d85264b2e7caaabd37ce50bf6d281b91e442ac85faf8835"),
}


def edit(name):
    if name == "handoff":
        return SHARED+(CLOSER,)
    if name == "reaction":
        return SHARED+(REACTION,CLOSER)
    raise ValueError("unknown story ending")


def clock(rows):
    return (0,*accumulate(n for _,n in rows))


def load_locks(variant):
    selected = ("loan","arrival","handoff","reaction") if "reaction" in VARIANTS[variant] else ("loan","arrival","handoff")
    receipts = {}
    for name in selected:
        relative, expected = LOCKS[name]
        local = root/"collab"/relative
        previous.bound(local,expected)
        receipts[name] = json.loads(local.read_text(encoding="utf-8"))
    for author, module in (("loan",loan),("arrival",arrival)):
        if receipts[author]["source_art"] != {k:list(v) for k,v in module.ART.items()}:
            raise ValueError(f"unreviewed {author} asset bindings")
        for filename, expected in module.ART.values():
            previous.bound(root/"concept/style_frames"/filename,expected)
    previous.bound(payoff.RAW_LOCK,payoff.RAW_LOCK_SHA)
    if "reaction" in selected and receipts["reaction"]["source_art"]!=receipts["arrival"]["source_art"]:
        raise ValueError("unreviewed reaction references")
    return receipts


def check(variant):
    old = previous.check("visitor")
    receipts = load_locks(variant)
    return {
        "cash_cost":0,"external_cache_required":False,"prior_full_movie_required":False,
        "variants":{name:clock(edit(name)) for name in VARIANTS[variant]},
        "source_receipts":{name:LOCKS[name][1] for name in receipts},
        "protected_source_check":old,
    }


def legacy_clips(stage, early):
    # Only the retained porch/ledger plates. The original superseded mug
    # close-up and standing delivery need not be encoded or decoded.
    _,master,paths,_ = source.source_inputs()
    with ExitStack() as stack:
        images = {}
        def read(first,stop):
            for i in range(first,stop):
                scene = source.golden.shot_for_frame(master["shots"],i+1)
                if scene["id"] not in ("GS010","GS040") or scene["source"]["type"]!="plate_sequence":
                    raise ValueError(f"not the expected original plate at F{i}")
                segment = source.golden.segment_for_frame(scene["segments"],i+1)
                key = segment["plate_id"]
                if key not in images:
                    with Image.open(paths[key]) as plate:
                        images[key] = stack.enter_context(plate.convert("RGB"))
                with source.golden.compose_plate_frame(images[key],segment,i+1) as plate:
                    yield i,plate.tobytes(),(scene["id"],i+2-int(scene["start_frame"]))

        for tag,first,stop in (("porch",0,129),("ledger-wide-source",396,452),("ledger-detail",452,564)):
            p = stage/f"{tag}.mp4"
            raw = []
            source.encode_native(read(first,stop),first,stop,p,p.with_suffix(".log"),raw)
            previous.assert_frames(tag,{row["frame"]:row["rgb24_sha256"] for row in raw},
                                   {i:early[i] for i in range(first,stop)})

    # Same aperture/color recipe as the editorial proof. The small decoder
    # source here is generated locally once, never an earlier feature.
    frame = stage/"ledger-reverse.mp4"
    cmd = cut.media.encoder_command("ffmpeg",frame)
    cmd[cmd.index("-f"):cmd.index("-an")] = [
        "-i",str(stage/"ledger-wide-source.mp4"),"-map","0:v:0","-frames:v","56"]
    cmd[cmd.index("-vf")+1] = ("crop="+":".join(map(str,ledger.CROP))+
        ",scale=1920:1080:flags=lanczos,"+cut.media.FRAME_FILTERS.split(",",1)[1])
    cut.media._run(cmd,frame.with_suffix(".log"))


def make_shots(stage, variant, locks, approval_path):
    early, actions, pov = previous.native_inventories("visitor")
    print("Rendering the porch, borrowing, return and ledger…",flush=True)
    legacy_clips(stage,early)
    l = loan.build(stage/"loan-work")
    if l["native_rgb_sha256_by_frame"]!=locks["loan"]["native_rgb_sha256_by_frame"]:
        raise ValueError("loan source frames changed")
    (stage/"loan-work/opening-loan.mp4").rename(stage/"loan.mp4")
    returned = arrival.build(stage/"return-work")
    if {str(k):v for k,v in returned["native_rgb24_sha256"].items()}!=locks["arrival"]["native_rgb24_sha256"]:
        raise ValueError("return source frames changed")
    (stage/"return-work/visitor-return.mp4").rename(stage/"return.mp4")

    print("Rendering the visitor POV and June's coffee action…",flush=True)
    _, data = previous.visitor.animate(stage/"visitor-pov.mp4")
    if data!=pov["visitor"]:
        raise ValueError("visitor POV source frames changed")
    previous.assert_frames("coffee action",previous.coffee.do_frames(stage),actions)
    (stage/"new-678.mp4").rename(stage/"coffee-pickup.mp4")
    (stage/"new-864.mp4").rename(stage/"coffee-return.mp4")
    if payoff.render_insert(stage/"handoff.mp4")!=locks["handoff"]["new_native_rgb24_sha256"]:
        raise ValueError("handoff source frames changed")
    if "reaction" in VARIANTS[variant]:
        if reaction.render(stage/"coffee-reaction.mp4")!=locks["reaction"]["native_picture_sha256"]:
            raise ValueError("reaction source frames changed")

    print("Regenerating the protected pour and original closing performance once…",flush=True)
    protected = stage/"protected"
    source.working.build(protected)
    built = protected/(source.working.NAME+".mov")
    before, after = (ledger.frame_hashes(p) for p in (approval_path,built))
    if len(before)!=303 or before!=after:
        raise ValueError("protected source pixels changed")
    for tag,a,b in (("protected-pour",0,75),("protected-closer",75,303)):
        p = stage/f"{tag}.mp4"
        cut.encode_or_copy("repaired",built,a,b,p,p.with_suffix(".log"))
    return before


def signature_at(clip, frames):
    return [(pts+frames*1000,dts+frames*1000,dt,h,side) for pts,dts,dt,h,side in clip]


def index_segments(stage, variant):
    names = dict(segment for variant_name in VARIANTS[variant] for segment in edit(variant_name))
    index = {}
    for name,size in names.items():
        path = stage/f"{name}.mp4"
        p = packets.packet_info(path,"v:0")
        ledger.prior.validate_gops(p,(0,size))
        decoded = ledger.frame_hashes(path)
        if len(decoded)!=size:
            raise ValueError(f"{name}: missing decoded samples")
        index[name] = (packets.signature(p),decoded,packets.codec_hash(path))
    if len({r[2] for r in index.values()})!=1:
        raise ValueError("incompatible H.264 parameters across new source shots")
    return index


def check_output(name, movie, index, protected):
    rows = edit(name)
    edges = clock(rows)
    actual = packets.packet_info(movie,"v:0")
    ledger.prior.validate_gops(actual,edges)
    packet_reference = []
    frame_reference = []
    for start,(shot,_) in zip(edges,rows):
        signatures,pixels,_ = index[shot]
        packet_reference += signature_at(signatures,start)
        frame_reference += pixels
    if packets.signature(actual)!=packet_reference:
        raise ValueError(f"{name}: mux changed a source picture packet")
    delivered = ledger.frame_hashes(movie)
    if delivered!=frame_reference:
        raise ValueError(f"{name}: mux changed decoded pictures")
    end = reaction.JOIN+(reaction.N if name=="reaction" else 0)
    if delivered[789:864]+delivered[end:]!=protected:
        raise ValueError(f"{name}: original pour or closer pixels drifted")
    return len(delivered)


def _build(output, variant, checked):
    locks = load_locks(variant)
    recipe, paths, caption_contract = cut.load_plan()
    origin, _ = cut.full_mix(recipe,paths,caption_contract)
    current, cues = payoff.extend_sound(origin), payoff.extend_captions(caption_contract)
    stage = output/"source-shots"
    stage.mkdir()
    protected = make_shots(stage,variant,locks,paths["repaired"])
    summary = index_segments(stage,variant)
    proofs = {}
    for name in VARIANTS[variant]:
        print(f"Assembling and checking the {name} ending…",flush=True)
        folder = output/name
        folder.mkdir()
        wav,srt = folder/"mix.wav",folder/"captions.srt"
        mix = reaction.pad_silence(current) if name=="reaction" else current
        caps = reaction.shift_captions(cues) if name=="reaction" else cues
        cut.foley.audio.ledger_pour._write_pcm24_wave(wav,mix,cut.RATE)
        cut.foley.audio.golden_sound.write_captions(caps,srt)
        if name=="handoff":
            previous.bound(wav,ledger.SOURCE_PCM_SHA)
        listing = stage/f"{name}.ffconcat"
        listing.write_text("ffconcat version 1.0\n"+"".join(f"file '{k}.mp4'\n" for k,_ in edit(name)),
                           encoding="ascii")
        mov,mp4 = reaction.mux(folder,listing,wav,srt)
        count = check_output(name,mp4,summary,protected)
        with patch.object(payoff,"TOTAL",count):
            snr = payoff.audit_delivery(mov,mp4,Fraction(count,30),mix,srt)
        peak = cut.beat.true_peak(mp4)
        if peak > -1.0 or cut.media._video_hash(mov,"ffmpeg")!=cut.media._video_hash(mp4,"ffmpeg"):
            raise ValueError(f"{name}: playback clipping or MOV/MP4 picture drift")
        proofs[name] = {
            "movie":str(mp4.relative_to(output)),"pcm_master":str(mov.relative_to(output)),
            "clock":[1920,1080,30,count],"duration_seconds":count/30,
            "verified_source_packets_and_decoded_frames":count,"protected_frames_exact":303,
            "pcm_pairs_exact":len(mix),"pcm_sha256":digest(wav),"all_18_captions_verified":True,
            "preview_aac_snr_db":snr,"preview_true_peak_dbtp":peak,
            "movie_sha256":digest(mp4),"pcm_master_sha256":digest(mov),
        }
    return {"completed":True,"prior_full_movie_used":False,"human_accepted":False,"production_release":False,
            "shared_shots_built_once":True,"variants":proofs,"preflight":checked,
            "source_frame_match":"all authored source clocks and protected renders; prior container SHA not required",
            "builder_sha256":digest(Path(__file__))}


def build(output, variant):
    if output.exists():
        raise FileExistsError(f"choose a new review folder: {output}")
    checked = check(variant)
    output.mkdir(parents=True,exist_ok=False)
    try:
        report = _build(output,variant,checked)
        cut.media._json(output/"story-review-build.json",report)
        return report
    except Exception as exc:
        cut.media._json(output/"story-review-failure.json",{"completed":False,"error":str(exc)})
        raise


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--check",action="store_true",help="check source and prerequisites without rendering")
    cli.add_argument("--variant",choices=VARIANTS,default="both")
    cli.add_argument("--output",type=Path)
    args = cli.parse_args()
    if args.check:
        print(json.dumps(check(args.variant),indent=2))
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output = (args.output or root/"outputs/edit"/f"june-story-review-{stamp}").resolve()
    build(output,args.variant)
    print(f"Verified story reviews: {output}",flush=True)


if __name__=="__main__":
    main()
