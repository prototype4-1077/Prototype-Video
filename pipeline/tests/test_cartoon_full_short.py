"""Measure the delivered full cut against its approved and original sources."""
from fractions import Fraction
from pathlib import Path
import json
import re
import subprocess
import tempfile
import unittest

import numpy as np

from pipeline import cartoon_full_short as cut


PACKAGE = cut.beat.ROOT / "collab/june_twelve_dollar_mug_repaired_v1"


class FullCutSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan,cls.paths,cls.contract=cut.load_plan()
        cls.mix,cls.audio_report=cut.full_mix(cls.plan,cls.paths,cls.contract)

    def test_last_pour_line_and_original_clock_survive(self):
        self.assertEqual(len(self.mix),1_824_000)
        self.assertEqual(self.contract["dialogue_cues"][13]["text"],"and poured him coffee.")
        self.assertTrue(self.mix[870*1600:910*1600].any())
        self.assertFalse(self.mix[912*1600-1440:912*1600+1440].any())
        for cue in self.contract["dialogue_cues"]:
            self.assertTrue(self.mix[(cue["start_frame"]-1)*1600:cue["end_frame"]*1600].any(),cue["id"])

    def test_approved_sound_is_reused_without_a_procedural_bed(self):
        approved,_=cut.foley.audio.ledger_pour._read_pcm24_wave(self.paths["approved_pcm"])
        np.testing.assert_array_equal(self.mix[912*1600:],approved[75*1600:])
        src,_=cut.foley.audio.ledger_pour._read_pcm24_wave(self.paths["speech"])
        # The restored prefix has no audio in the true gaps around the opening.
        zeros=(src[:789*1600,0]==0)
        self.assertFalse(self.mix[:789*1600][zeros].any())
        # The only pre-closure effect remains the isolated 75-frame recording.
        region=np.s_[789*1600:864*1600]
        reference_clip=approved[:75*1600]
        self.assertTrue(reference_clip.any())
        silent_voice = src[region,0]==0
        np.testing.assert_array_equal(self.mix[region][silent_voice],reference_clip[silent_voice])
        self.assertFalse(self.audio_report["legacy_effects_used"])

    def test_arbitrary_legacy_input_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            bad=Path(td)/"wrong.mp4"
            bad.touch()
            with self.assertRaisesRegex(ValueError,"legacy Phase25 master bytes changed"):
                cut.build(bad,Path(td)/"output")
            self.assertFalse((Path(td)/"output").exists())


class PublishedFullCutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=json.loads((PACKAGE/"verification.json").read_text(encoding="utf-8"))
        cls.plan,cls.paths,cls.contract=cut.load_plan()
        cls.mp4,cls.wav = (PACKAGE/name for name in ("twelve-dollar-mug.mp4","mix.wav"))

    def test_publication_binding_and_no_artistic_approval(self):
        for p in (self.mp4,self.wav,PACKAGE/"captions.srt"):
            self.assertEqual(cut.beat.digest(p),self.report["outputs_sha256"][p.name])
        self.assertEqual(cut.beat.digest(cut.RECIPE),self.report["recipe_sha256"])
        self.assertEqual(cut.beat.digest(Path(cut.__file__)),self.report["renderer_sha256"])
        self.assertIs(self.report["human_acceptance"],False)
        self.assertIs(self.report["production_release"],False)

    def test_preview_and_master_clocks_and_exact_closing_pcm(self):
        streams={t["codec_type"]:t for t in cut.media._probe(self.mp4,"ffprobe")["streams"]}
        self.assertEqual(int(streams["video"]["nb_read_frames"]),1140)
        for k in ("audio","video"):
            s=streams[k]
            self.assertEqual(int(s["duration_ts"])*Fraction(s["time_base"]),38)
        self.assertLessEqual(cut.beat.true_peak(self.mp4),-1)
        pcm,_=cut.foley.audio.ledger_pour._read_pcm24_wave(self.wav)
        expected,_=cut.full_mix(self.plan,self.paths,self.contract)
        np.testing.assert_array_equal(pcm,expected)
        aac=cut.beat.decoded_audio(self.mp4,"f32le","<f4")[:len(pcm)]
        ref=pcm.astype(float)/8388608
        self.assertGreater(10*np.log10(np.mean(ref**2)/np.mean((ref-aac)**2)),40)
        approved,_=cut.foley.audio.ledger_pour._read_pcm24_wave(self.paths["approved_pcm"])
        np.testing.assert_array_equal(pcm[-228*1600:],approved[75*1600:])

    def test_all_eighteen_authored_captions_reach_the_delivery(self):
        data=subprocess.check_output(["ffmpeg","-v","error","-i",str(self.mp4),"-map","0:s:0","-f","srt","pipe:1"])
        entries=re.split(r"\r?\n\r?\n",data.decode("utf-8").strip())
        texts=[entry.splitlines()[2] for entry in entries]
        self.assertEqual(texts,[cue["text"] for cue in self.contract["dialogue_cues"]])


if __name__=="__main__":
    unittest.main()
