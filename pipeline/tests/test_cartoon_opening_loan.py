"""Check the opening beat and the immutable review artifacts."""
from pathlib import Path
import json

import numpy as np
import pytest

from pipeline import cartoon_opening_loan as shot
from pipeline import cartoon_opening_loan_review as review


PACKAGE = shot.ROOT/"collab/june_opening_loan_v1"


def test_grip_sits_before_mug_lifts_and_reaches_the_film_clock():
    q = [shot.cues(f) for f in range(shot.N)]
    assert shot.SPAN == (129,225) and shot.N == 96
    assert q[9].wrap == 0 and q[10].wrap > 0
    assert q[26].wrap < 1 and q[27].wrap == 1
    assert [(p.x,p.y) for p in q[:30]] == [(0.,0.)]*30
    assert q[30].wrap == 1 and q[30].rise > 0
    assert (q[44].x,q[44].y) == (shot.DX,shot.DY)
    assert (q[82].x,q[82].y) == (shot.DX+28,shot.DY+7)
    assert q[-1] == q[82]
    for index in (-1,shot.N,True,2.0):
        with pytest.raises(ValueError):
            shot.cues(index)


def test_mug_is_rigid_cash_does_not_follow_and_shoulder_does_not_slide():
    scene = shot.prepare()
    start,grip,held,drawn = (shot.paint(scene,f) for f in (0,27,44,95))
    for img in (grip,held,drawn):
        np.testing.assert_array_equal(img[540:785,302:545],start[540:785,302:545])
        np.testing.assert_array_equal(img[:400,1200:],start[:400,1200:])
    ys,xs = slice(688,803),slice(645,750)
    np.testing.assert_array_equal(grip[ys,xs],start[ys,xs])
    for img,dx,dy in ((held,shot.DX,shot.DY),(drawn,shot.DX+28,shot.DY+7)):
        np.testing.assert_array_equal(img[ys.start+dy:ys.stop+dy,xs.start+dx:xs.stop+dx],start[ys,xs])
    assert not np.array_equal(grip,start)
    assert not np.array_equal(held,drawn)


def test_comparison_edges_refuse_one_nonzero_sample():
    s = np.zeros((review.TOTAL*1600,2),np.int32)
    review.quiet(s)
    for f in review.PREVIEW:
        s[f*1600-1440,1] = 1
        with pytest.raises(ValueError, match="silence"):
            review.quiet(s)
        s[f*1600-1440,1] = 0


@pytest.mark.skipif(not (PACKAGE/"opening-loan-integration.json").is_file(),
                    reason="review packet not published")
def test_published_review_receipts():
    build = PACKAGE/"opening-loan-proof.json"
    movie = json.loads(build.read_text(encoding="utf-8"))
    edit = json.loads((PACKAGE/"opening-loan-integration.json").read_text(encoding="utf-8"))
    assert movie["clock"] == [1920,1080,30,96]
    assert movie["builder_sha256"] == review.digest(Path(shot.__file__))
    assert len(movie["native_rgb_sha256_by_frame"]) == 96
    assert edit["identical_picture_frames"] == 1095
    assert edit["identical_decoded_audio_pairs"] == 1905600
    assert edit["baseline_movie_sha256"] == review.BASE_SHA
    assert edit["builder_sha256"] == review.digest(Path(review.__file__))
    assert edit["shot_receipt_sha256"] == review.digest(build)
    assert edit["review_sha256"] == review.digest(PACKAGE/"opening-loan-review.mp4")
    assert edit["same_audio_and_caption_packets"] is True
    assert edit["human_accepted"] is False and edit["production_release"] is False
