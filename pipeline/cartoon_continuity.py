"""Master-sequence continuity: one cartoon world serves several narration scenes
through reaction shots, inserts, camera variants and continuation beats.
"""
from __future__ import annotations

MASTER_SEQUENCES = {
  "the-emotion-scam-cartoon-v2": {
    "emotion-club-entry":        [1,2,3],
    "emotion-control-booth":     [4,5,6,7,8],
    "emotion-production-machine": [9,10,11,12],
    "emotion-song-ingredients":  [13,14,15,16],
    "emotion-attention-labels":  [17,18,19,20],
    "emotion-boundary-grounding":[21,22,23,24],
  },
  "june-oxley-folks-aint-roadblocks-cartoon-v2": {
    "june-diner":        [1,2,3,4,16],
    "june-town-stage":   [5,6,8,9,10,13,14,21,22],
    "june-road":         [7],
    "june-fence-porch":  [15,17,18,19,20],
    "june-evening-porch":[23,24],
  },
}

def master_of(slug, scene_num):
    for mid, scenes in MASTER_SEQUENCES.get(slug, {}).items():
        if scene_num in scenes:
            return mid
    return None

def scenes_of(slug, master_id):
    return MASTER_SEQUENCES.get(slug, {}).get(master_id, [])

def serves_multiple(slug, master_id):
    return len(scenes_of(slug, master_id)) > 1

def group_consistency(scene_dicts):
    """A continuity group must keep the same location_id and character set."""
    errs = []
    locs = {s.get("location_id") for s in scene_dicts}
    if len(locs) > 1:
        errs.append(f"continuity group spans multiple locations: {locs}")
    return errs
