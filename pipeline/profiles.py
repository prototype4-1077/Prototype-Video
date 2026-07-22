"""Opt-in character profiles for video-specific creative direction.

Profiles are deliberately separate from ``genre``. A genre describes the subject
matter (for example, DMT); a profile describes the recurring character's world.
Nothing in this module changes an unprofiled video.
"""
from __future__ import annotations

import re


JUNE_OXLEY = "june_oxley"

_ALIASES = {
    "june_oxley": JUNE_OXLEY,
    "juneoxley": JUNE_OXLEY,
    "june": JUNE_OXLEY,
    "papa_june": JUNE_OXLEY,
    "grandpa_june": JUNE_OXLEY,
    "granpa_june": JUNE_OXLEY,
}

_JUNE_ORDINARY = (
    "old white man sitting on wooden front porch daylight",
    "hands steering old pickup truck rural road",
    "cornfield moving in wind warm daylight",
    "barking dog beside chain link fence backyard",
    "weathered rural house mirror warm window light",
    "small country church interior ceiling fan",
    "fireplace rocking chair lived in old house",
    "small town traffic seen through windshield",
    "worn work boots walking dusty country road",
    "old white man smoking on porch golden hour",
    "unpaid bills spread across kitchen table",
    "deer staring at camera beside rural road",
    "sunset through tall grass in country field",
    "rusted mailbox beside gravel road daylight",
    "coffee mug on porch rail morning sunlight",
    "empty rocking chair on weathered front porch",
)

_JUNE_STRANGE = (
    "surreal eye made of stars vintage animation",
    "cosmic light appearing over ordinary cornfield",
    "old mirror reflecting impossible universe",
    "church ceiling fan turning beneath starry sky",
)

_VISION_WORDS = (
    "astral", "cosmic", "cosmos", "dmt", "dream", "fractal", "galaxy",
    "illusion", "infinite", "mystical", "psychedelic", "spirit", "universe",
    "vision", "wormhole",
)

_JUNE_HUMAN_CUES = (
    "driver", "hands steering", "man ", " man", "narrator", "person ",
    " person", "sitting", "smoking", "standing", "walking",
)

_OTHER_SUBJECTS = (
    "boy", "child", "cousin", "crowd", "daughter", "dog", "girl", "neighbor",
    "people", "woman", "wife",
)


def _key(value) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def resolve(script: dict | None, strict: bool = False) -> str | None:
    """Return the canonical profile name from supported script fields.

    ``profile`` is canonical. ``character`` and ``character_style`` are accepted so
    a human-authored script that says "June Oxley" still does the right thing.
    """
    script = script or {}
    raw = next((script.get(k) for k in ("profile", "character_style", "character")
                if script.get(k)), None)
    if raw is None:
        return None
    found = _ALIASES.get(_key(raw))
    if found is None and strict:
        raise ValueError(f"unknown profile {raw!r}; supported: june_oxley")
    return found


def detect_from_text(text: str) -> str | None:
    """Detect an explicitly named profile in an issue/request description."""
    t = " ".join(str(text).lower().split())
    if re.search(r"\b(june oxley|papa june|grandpa june|granpa june)\b", t):
        return JUNE_OXLEY
    return None


def is_visionary(text: str) -> bool:
    t = str(text).lower()
    return any(word in t for word in _VISION_WORDS)


def identity_query(text: str, profile: str | None) -> str:
    """Keep June's recurring human subject correct without rewriting other characters."""
    q = " ".join(str(text).split()).strip()
    if profile != JUNE_OXLEY or not q:
        return q
    # Repair the exact stale identity that prompted this profile correction. More general
    # race mentions may describe a neighbor or another character and remain untouched.
    q = re.sub(r"\bold(?:er)?\s+black\s+(?:southern\s+)?man\b",
               "old white Southern man", q, flags=re.I)
    low = q.lower()
    if re.search(r"\bwhite(?:\s+southern)?\s+man\b", low) or \
            any(subject in low for subject in _OTHER_SUBJECTS):
        return q
    if any(cue in low for cue in _JUNE_HUMAN_CUES):
        return f"{q} old white Southern man"
    return q


def query_variants(query: str, profile: str | None) -> list[str]:
    """Search literal meaning plus a light profile cue; never replace the literal query."""
    q = identity_query(query, profile)
    if profile != JUNE_OXLEY or not q:
        return [q] if q else []
    if is_visionary(q):
        styled = f"{q} grounded Southern folk surrealism vintage practical"
    else:
        styled = f"{q} rural Southern small town documentary warm daylight"
    return [styled, q]


def semantic_query(query: str, profile: str | None) -> str:
    q = identity_query(query, profile)
    if profile != JUNE_OXLEY:
        return q
    if is_visionary(q):
        return (f"literal {q}; grounded folk-surreal image entering an ordinary Southern "
                "rural world, tactile and deadpan rather than glossy fantasy")
    return (f"literal {q}; candid lived-in Southern rural or small-town life, warm natural "
            "light, weathered practical details, everyday clothing, dry documentary humor")


def fallback_queries(profile: str | None, genre: str | None = None) -> tuple[str, ...] | None:
    if profile != JUNE_OXLEY:
        return None
    # June's ordinary world remains the anchor even when the subject is visionary.
    return _JUNE_ORDINARY + (_JUNE_STRANGE if genre == "dmt" else _JUNE_STRANGE[:2])


def hero_style(profile: str | None, genre: str | None = None) -> str | None:
    if profile != JUNE_OXLEY:
        return None
    return (", grounded Southern folk-surrealism, lived-in rural America, warm natural "
            "daylight, weathered wood and practical details, contemporary everyday clothing, "
            "dry deadpan humor, unpolished realistic documentary film still")


def hero_prompt(prompt: str, profile: str | None) -> str:
    return identity_query(prompt, profile)


def writer_context(profile: str | None) -> str:
    if profile != JUNE_OXLEY:
        return ""
    return """JUNE OXLEY PROFILE (apply only to this explicitly named video):
- June is a retired old white Southern man with a slow, raspy, half-distracted delivery.
- His humor is dry, raw, and observant. Begin in mundane life, then let it wander naturally
  into consciousness or spiritual absurdity without losing the front-porch voice.
- Visual queries should be literal and ordinary first: porch, old truck, small town, dog,
  cornfield, kitchen table, church fan, weathered house, bills. Let only occasional images
  become cosmic or surreal; the contrast is the joke and the identity.
- Avoid costume-Western stereotypes, glossy country-music imagery, and generic dark mysticism.
- Set the top-level JSON field exactly to \"profile\": \"june_oxley\"."""


def display_name(profile: str | None) -> str:
    return "June Oxley" if profile == JUNE_OXLEY else "default"
