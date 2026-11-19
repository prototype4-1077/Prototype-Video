"""Build either or both current June review cuts directly from tracked source."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path

import cv2
import numpy as np

from pipeline import cartoon_coffee_cut as coffee
from pipeline import cartoon_compassion_review as probe
from pipeline import cartoon_full_short_source as source
from pipeline import cartoon_reaction_continuity as face
from pipeline import cartoon_visitor_insert as visitor


ROOT=source.ROOT
cut=source.cut
EDGES=(0,564,678,789,864,912,1140)
REACTION=(564,678)
PROTECTED=((789,864),(912,1140))
VARIANTS={"face":("face",),"visitor":("visitor",),"both":("face","visitor")}
MIX_SHA="8c1ad3abe1c2efa3808b9de1febc7e70cda408d1760da080267aeabceb4417de"
CAPTIONS_SHA="0100c2c967673cc4ded334f00050c37a0a3f231362590401aa9bb05b6081239e"
LOCKS={
    "early":("june_full_short_source_v1/native-early-frames.json",
             "5e0a0061b9178085509dcc418f4e2bff03440d5f28bc1aea80c07c012c599866"),
    "coffee":("june_coffee_continuity_v1/new-native-digests.json",
              "dbb22387edea6cf5e81f9cc0a4cde1dedba8d6a51e25e9bb81e3c79dcaa6022e"),
    "visitor":("june_visitor_turn_v1/visitor-gs050-native-frames.json",
               "05e9dafcb12ce8d5b57d7ed5cb8cbfc54e1c8863839c23c595f89dda663b2cdc"),
}
REFERENCE_SHA={
    "face":visitor.SHA_SOURCE,
    "visitor":"1c5158f71226f33b9d501f2ba3e8ed59de23f4a789997b8f62f1dcac4f4909ff",
}


def bound(path,expected):
    if cut.beat.digest(path)!=expected:
        raise ValueError(f"tracked asset or review evidence changed: {path.name}")


def native_inventories(variant):
    def load(key):
        name,digest=LOCKS[key]
        path=ROOT/"collab"/name
        bound(path,digest)
        return json.loads(path.read_text(encoding="utf-8"))

    early={row["frame"]:row["rgb24_sha256"] for row in load("early")["frames"] if row["frame"]<564}
    actions={int(i):v for i,v in load("coffee").items()}
    if set(early)!=set(range(564)) or set(actions)!=set(range(678,789))|set(range(864,912)):
        raise ValueError("unexpected tracked shot spans")
    face_hashes=visitor.native_reference()
    choices={"face":face_hashes}
    if "visitor" in VARIANTS[variant]:
        record=load("visitor")
        hashes=record["rgb24_sha256"]
        if record["start_frame_zero_based"]!=564 or len(hashes)!=114:
            raise ValueError("incorrect tracked visitor shot clock")
        diff=[i for i,(a,b) in enumerate(zip(face_hashes,hashes),564) if a!=b]
        if diff!=list(range(*visitor.INSERT)):
            raise ValueError("tracked variant changed outside the story insert")
        choices["visitor"]=hashes
    return early,actions,choices


def check(variant):
    checked=source.preflight()
    native_inventories(variant)
    for name,digest in coffee.acting.lift.HASHES.items():
        bound(coffee.acting.lift.ART/name,digest)
    for name,digest in ((coffee.acting.PARK,coffee.acting.PARK_SHA),(coffee.acting.POISED,coffee.acting.POISED_SHA)):
        bound(coffee.acting.lift.ART/name,digest)
    for stem,digest in face.acting.ASSETS.values():
        bound(ROOT/f"concept/style_frames/june-golden-scene-{stem}-v1.png",digest)
    if "visitor" in VARIANTS[variant]:
        bound(visitor.ART,visitor.ART_SHA)
    return {**checked,"variants":list(VARIANTS[variant]),"source_edl_zero_based":list(EDGES),
            "prior_full_movie_required":False,"protected_picture_regenerates_from_source":True}


def assert_frames(label,actual,expected):
    if set(actual)!=set(expected):
        raise ValueError(f"{label}: native frame census changed")
    for i in sorted(expected):
        if actual[i]!=expected[i]:
            raise ValueError(f"{label}: native pixel mismatch at output frame {i}")


def clip_check(path,count):
    rows=probe.packet_info(path,"v:0")
    if (len(rows)!=count or "K" not in rows[0]["flags"] or
            {int(r["pts"]) for r in rows}!={i*1000 for i in range(count)} or
            any(int(r["duration"])!=1000 for r in rows)):
        raise ValueError(f"incorrect 30fps clip clock at {path.name}")


def only_reaction_differs(a,b):
    first,last=REACTION
    streams=[probe.packet_info(p,"v:0") for p in (a,b)]
    if any(len(v)!=1140 for v in streams):
        raise ValueError("review film picture packet census changed")
    left,right=streams
    for start,stop in ((0,first),(last,1140)):
        if probe.signature(left[start:stop])!=probe.signature(right[start:stop]):
            raise ValueError("story toggle changed another shot")
    if probe.signature(left[first:last])==probe.signature(right[first:last]):
        raise ValueError("story toggle did not change the reaction")
    for kind in ("a:0","s:0"):
        original,alternate=[probe.packet_info(p,kind) for p in (a,b)]
        if not original or probe.signature(original)!=probe.signature(alternate):
            raise ValueError(f"story toggle altered {kind}")
    return {"equal_video_packets_outside_reaction":1026,
            "audio_caption_packets_exact_between_variants":True}


def compare_after(candidate,reference,variant):
    """Compare after delivery. An earlier candidate never feeds the renderer."""
    bound(reference,REFERENCE_SHA[variant])
    decoders=[cv2.VideoCapture(str(path)) for path in (candidate,reference)]
    exact_action=exact_protected=0
    intro=[]
    try:
        for i in range(1140):
            (ok,a),(got,b)=[d.read() for d in decoders]
            if not ok or not got:
                raise ValueError("comparison movie ended unexpectedly")
            exact=np.array_equal(a,b)
            if i<564:
                intro.append(float(cv2.PSNR(a,b)))
            elif any(lo<=i<hi for lo,hi in PROTECTED):
                if not exact:
                    raise ValueError(f"accepted picture drift at F{i}")
                exact_protected+=1
            elif exact:
                exact_action+=1
            else:
                raise ValueError(f"current action picture drift at F{i}")
        if any(d.read()[0] for d in decoders) or min(intro)<32:
            raise ValueError("intro didn't match the existing review above 32dB")
    finally:
        for decoder in decoders:
            decoder.release()
    packet_match={}
    for kind in ("a:0","s:0"):
        a,b=[probe.packet_info(p,kind) for p in (candidate,reference)]
        packet_match[kind]=bool(a) and probe.signature(a)==probe.signature(b)
    if not packet_match["s:0"]:
        raise ValueError("the current review caption packets changed")
    return {"intro_frames_compared":len(intro),"intro_min_psnr_db":min(intro),
            "intro_median_psnr_db":float(np.median(intro)), "exact_reaction_and_coffee_decodes":exact_action,
            "exact_protected_decodes":exact_protected,"audio_packets_exact":packet_match["a:0"],
            "caption_packets_exact":True}


def _build(output,variant,against,checked):
    recipe,paths,contract=cut.load_plan()
    mix,sound=cut.full_mix(recipe,paths,contract)
    wav,srt=output/"mix.wav",output/"captions.srt"
    cut.foley.audio.ledger_pour._write_pcm24_wave(wav,mix,cut.RATE)
    cut.foley.audio.golden_sound.write_captions(contract,srt)
    srt.write_text(srt.read_text(encoding="utf-8"),encoding="utf-8",newline="\r\n")
    bound(wav,MIX_SHA)
    bound(srt,CAPTIONS_SHA)

    stage=output/"segments"
    stage.mkdir()
    expected_early,expected_actions,expected_reaction=native_inventories(variant)
    intro=stage/"intro.mp4"
    print("Rebuilding early shots and the revised coffee action from source…",flush=True)
    early=[]
    with closing(source.earlier_frames()) as stream:
        source.encode_native(stream,0,564,intro,stage/"intro.log",early)
    assert_frames("opening",{row["frame"]:row["rgb24_sha256"] for row in early},expected_early)
    actions=coffee.do_frames(stage)
    assert_frames("coffee action",actions,expected_actions)

    takes={}
    for name in VARIANTS[variant]:
        print(f"Rebuilding the {name} reaction from source…",flush=True)
        path=stage/f"reaction-{name}.mp4"
        render=face.animate if name=="face" else visitor.animate
        _,rows=render(path)
        actual=dict(enumerate(rows,564))
        assert_frames(name,actual,dict(enumerate(expected_reaction[name],564)))
        takes[name]=path

    print("Regenerating the protected pour and closing performance once…",flush=True)
    protected_dir=output/"protected-source"
    working=source.working.build(protected_dir)
    regenerated=protected_dir/(source.working.NAME+".mov")
    if cut.beat.digest(regenerated)!=cut.beat.digest(paths["repaired"]):
        raise ValueError("regenerated protected source was not byte-identical")
    p0,p1=stage/"protected-pour.mp4",stage/"protected-ending.mp4"
    cut.encode_or_copy("repaired",regenerated,0,75,p0,p0.with_suffix(".log"))
    cut.encode_or_copy("repaired",regenerated,75,303,p1,p1.with_suffix(".log"))
    pickup,returning=[stage/f"new-{a}.mp4" for a,_ in coffee.CHANGE]
    segments=(intro,pickup,p0,returning,p1,*takes.values())
    if len({probe.codec_hash(p) for p in segments})!=1:
        raise ValueError("rendered shots use incompatible AVC configurations")

    results={}
    movies={}
    for name,path in takes.items():
        clips=(intro,path,pickup,p0,returning,p1)
        for clip,a,b in zip(clips,EDGES,EDGES[1:]):
            clip_check(clip,b-a)
        listing=stage/f"{name}.ffconcat"
        listing.write_text("ffconcat version 1.0\n"+"".join(f"file '{p.name}'\n" for p in clips),
                           encoding="utf-8",newline="\n")
        folder=output/name
        folder.mkdir()
        movie,preview=cut.mux(folder,listing,wav,srt)
        print(f"Checking the full {name} cut against its frame and sound locks…",flush=True)
        inspected=cut.audit(folder,movie,preview,mix,paths["repaired"])
        if any(inspected["same_view_join_mae"][k]>limit for k,limit in (("789",6.5),("864",5.0))):
            raise ValueError(f"{name}: a pour boundary drifted")
        results[name]={"preview":str(preview.relative_to(output)),"preview_sha256":cut.beat.digest(preview),
            "pcm_master":str(movie.relative_to(output)),"pcm_master_sha256":cut.beat.digest(movie),
            "native_rgb_frames_matched":len(early)+len(actions)+len(expected_reaction[name]),
            "audit":inspected}
        movies[name]=preview
        print(f"Review movie: {preview}",flush=True)
    equivalence=only_reaction_differs(movies["face"],movies["visitor"]) if len(movies)==2 else None
    for name,reference in against.items():
        results[name]["post_render_existing_cut_comparison"]=compare_after(movies[name],reference,name)
    return {"completed":True,"entrypoint_sha256":cut.beat.digest(Path(__file__)),"preflight":checked,
            "prior_full_movie_used_as_source":False,"scene_builds_from_source":1,
            "protected_source_mov_sha256":working["exact_audio_copy"]["sha256"],
            "frame_clock":[1920,1080,30,1140],"sound":sound,"mix_sha256":MIX_SHA,"captions_sha256":CAPTIONS_SHA,
            "variants":results,"same_build_comparison":equivalence,"human_accepted":False,"production_release":False}


def build(output,variant="both",against=None):
    against=against or {}
    if not set(against)<=set(VARIANTS[variant]):
        raise ValueError("reference comparison needs the corresponding selected variant")
    if output.exists():
        raise FileExistsError(f"choose a new output folder: {output}")
    checked=check(variant)
    output.mkdir(parents=True,exist_ok=False)
    try:
        report=_build(output,variant,against,checked)
        cut.media._json(output/"current-review-build.json",report)
        return report
    except BaseException as exc:
        cut.media._json(output/"current-review-failure.json",{"completed":False,"error":str(exc),
                                                             "artifacts_preserved":True})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant",choices=VARIANTS,default="both",help="which reaction take to render")
    parser.add_argument("--output",type=Path,help="new output directory")
    parser.add_argument("--check",action="store_true",help="check source and tools without rendering")
    parser.add_argument("--compare-face",type=Path,help="optional prior face cut for post-render comparison")
    parser.add_argument("--compare-visitor",type=Path,help="optional prior visitor cut for post-render comparison")
    args=parser.parse_args()
    if args.check:
        print(json.dumps(check(args.variant),indent=2))
    else:
        stamp=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        output=args.output or ROOT/"outputs/edit"/f"june-current-review-{stamp}"
        references={k:v.resolve() for k,v in (("face",args.compare_face),("visitor",args.compare_visitor)) if v is not None}
        build(output.resolve(),args.variant,references)
        print(f"Build report: {output.resolve() / 'current-review-build.json'}",flush=True)


if __name__=="__main__":
    main()
