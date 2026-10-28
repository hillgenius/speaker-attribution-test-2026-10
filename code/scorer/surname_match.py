"""Name cleaning and surname matching, reproduced from the development harness's
`score_methods_pilot7.py` (clean_name/surname_of_name/norm_surname/surname_variants) and
`score_methods_batch10_shipped.py` (edit_distance_le1, strip_of_state_suffix, the
hyphenated-surname widening in surname_match) -- see PROVENANCE.md. Not a byte-identical
vendor copy: consolidated into one module and given one combined entry point
(`surname_match`) instead of being re-derived per batch script.

The job: decide whether a shipped display name ("Rep. Austin Scott (R-GA)", "The
Honorable Marcy Kaptur", "William G. Resh, Ph.D.") names the same person as a GPO print's
turn-header speaker label ("Scott of Georgia", "Kaptur", "Resh"). Spelling/formatting
variants (a two-word surname GPO sometimes prints in full and sometimes abbreviates to its
last token, a hyphenated surname split across a candidate's two name halves, an off-by-one
diacritic/typo) are treated as matches, per the "spelling variants counted correct" rule --
this module does not get to decide who HillGenius actually identified, only whether two
spellings name the same surname.
"""
from __future__ import annotations

import re
import unicodedata

TITLE_RE = re.compile(
    r"^(?:The\s+Honorable|Hon\.?|Rep\.?|Sen\.?|Senator|Representative|"
    r"Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Miss|"
    r"Lieutenant\s+General|Lt\.?\s+Gen\.?|General|Gen\.?|Admiral|Adm\.?|"
    r"Secretary|Sec\.?|Ambassador|Amb\.?|Colonel|Col\.?|Major|Maj\.?|"
    r"Captain|Capt\.?)\s+",
    re.I,
)
SUFFIX_STOP = {"retired", "ret", "usaf", "usa", "usn", "usmc", "uscg",
               "jr", "sr", "ii", "iii", "iv"}
MIDDLE_INITIAL_RE = re.compile(r"^[a-z]\.?$", re.I)

_CREDENTIAL_SUFFIXES = {
    "phd", "md", "jd", "esq", "esquire", "mba", "mph", "rn", "np", "pa",
    "dds", "dmd", "dvm", "dnp", "facp", "facog", "facs", "faap",
    "pharmd", "psyd", "scd", "edd", "drph", "meng", "mfa", "med", "mdiv", "rph",
}

_OF_STATE_SUFFIX_RE = re.compile(r"^(.*\S)\s+of\s+[A-Z][A-Za-z.]*(?:\s+[A-Z][A-Za-z.]*)*$")


def _is_credential_token(t: str) -> bool:
    bare_lower = re.sub(r"\.", "", t).lower()
    if bare_lower in _CREDENTIAL_SUFFIXES or bare_lower in SUFFIX_STOP:
        return True
    letters = re.sub(r"[^A-Za-z]", "", t)
    if not letters:
        return False
    uppercase_share = sum(c.isupper() for c in letters) / len(letters)
    is_initialism = t.count(".") >= 1
    return len(letters) <= 6 and (uppercase_share >= 0.6 or is_initialism)


def _strip_trailing_credential_groups(n: str) -> str:
    parts = n.split(",")
    while len(parts) > 1:
        toks = parts[-1].strip().split()
        if toks and all(_is_credential_token(t) for t in toks):
            parts.pop()
        else:
            break
    return ",".join(parts).strip()


def clean_name(name: str) -> str:
    """Strip a leading title/rank, a trailing (party-state) parenthetical, trailing
    comma-separated credential groups, and trailing rank/branch/status/middle-initial
    tokens, keeping whatever whitespace-separated tokens remain of the surname itself."""
    if not name:
        return ""
    n = TITLE_RE.sub("", name.strip())
    n = re.sub(r"\s*\([^)]*\)\s*$", "", n).strip()
    n = _strip_trailing_credential_groups(n)
    toks = n.split()
    while toks and len(toks) > 1 and (toks[-1].lower().rstrip(".") in SUFFIX_STOP
                                     or _is_credential_token(toks[-1])):
        toks.pop()
    while toks and MIDDLE_INITIAL_RE.match(toks[-1]) and len(toks) > 1:
        toks.pop()
    return " ".join(toks)


def surname_of_name(name: str) -> str:
    """Best-effort single-token surname for display: the last remaining token after
    clean_name()."""
    toks = clean_name(name).split()
    return toks[-1] if toks else ""


def norm_surname(s: str) -> str:
    """Case/diacritic/punctuation-insensitive compare key. NFKD-folds accents the same
    way `score_one.normalize` does, so gold_speaker (itself a normalize() output) and a
    DB name fold the same way (e.g. "Luján" -> "lujan")."""
    if not s:
        return ""
    folded = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z]", "", folded.lower())


def surname_variants(name: str) -> set[str]:
    """Both GPO-comparable forms of a name's surname: the full cleaned name joined with
    no spaces (for a two-word surname GPO prints in full, e.g. "Blunt Rochester") and just
    its last token (for a two-word surname GPO abbreviates to one word, e.g. cl_last
    "Gluesenkamp Perez" -> gold "Perez"). Both a candidate's name and gold_speaker are
    expanded into this same variant set and compared by intersection, so neither print
    convention is penalized as a mismatch."""
    cleaned = clean_name(name)
    toks = cleaned.split()
    if not toks:
        return set()
    variants = {norm_surname(cleaned)}
    variants.add(norm_surname(toks[-1]))
    return {v for v in variants if v}


def strip_of_state_suffix(name: str) -> str | None:
    """A GPO-style "<Full Name> of <State>" nameplate ("Carter of Georgia") has no rule
    in clean_name(); this recovers the plain name when a shipped display name happens to
    carry that same convention."""
    m = _OF_STATE_SUFFIX_RE.match(name.strip())
    return m.group(1) if m else None


def edit_distance_le1(a: str, b: str) -> bool:
    """True if `a` and `b` differ by at most one character insertion, deletion, or
    substitution (a cheap Levenshtein<=1 check, not full edit distance)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diffs = sum(1 for x, y in zip(a, b) if x != y)
        return diffs <= 1
    if la > lb:
        a, b = b, a
        la, lb = lb, la
    i = j = 0
    skipped = False
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
        elif not skipped:
            skipped = True
            j += 1
        else:
            return False
    return True


def surname_match(pred_variants: set[str], gold_surname: str, allow_fuzzy: bool = True) -> bool:
    """True if a candidate's surname variants and a GPO gold_speaker label name the same
    person: exact variant-set intersection, a hyphenated gold label split into its two
    halves (a GPO turn header like "Farfan-Mendez" is one whitespace-token to
    surname_variants(), so it never intersects a roster entry carrying only one half, e.g.
    "Cecilia Farfan, Ph.D."), or, when `allow_fuzzy` is left True, an edit-distance<=1
    fallback between any pair of variants at least 4 characters long (a spelling/OCR-level
    typo, not a different person).

    `allow_fuzzy=False` is for `roster.py`'s reference-side resolution of a GPO print's
    own surname to a roster bioguide id: there, a one-edit slip is far more likely to be
    two genuinely different surnames ("Hasten" vs "Casten") than an OCR/spelling variant
    of the SAME print's own typo, since the print text and the roster both come from
    clean, independently-sourced data (not a noisy transcript) -- see REGRESSION.md. The
    fuzzy fallback stays available (default True) for comparing OUR shipped transcript
    label against a gold print label (`gold_surname_match`, used by `score.py`) and for
    comparing two independent segmentations' speaker labels (`compare_refs.py`'s
    `speakers_agree`), where a genuine spelling/typo slip in HillGenius's own output is
    exactly the case this fallback exists to tolerate."""
    if not pred_variants:
        return False
    gold_variants = set(surname_variants(gold_surname))
    if "-" in gold_surname:
        for half in gold_surname.split("-"):
            gold_variants |= surname_variants(half)
    if pred_variants & gold_variants:
        return True
    if not allow_fuzzy:
        return False
    for pv in pred_variants:
        for gv in gold_variants:
            if len(pv) >= 4 and len(gv) >= 4 and edit_distance_le1(pv, gv):
                return True
    return False


US_STATE_ABBR = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY", "district of columbia": "DC", "puerto rico": "PR", "guam": "GU",
    "american samoa": "AS", "virgin islands": "VI", "northern mariana islands": "MP",
}

_GOLD_STATE_RE = re.compile(r"^(.*\S)\s+of\s+([A-Za-z][A-Za-z ]*)$")
_PARTY_STATE_RE = re.compile(r"\(([A-Za-z]{1,2})-([A-Za-z]{2})\)\s*$")


def split_state_qualifier(gold_surname: str) -> tuple[str, str | None]:
    """Splits a GPO gold label's state-disambiguation suffix ("Carter of Georgia" ->
    ("Carter", "Georgia")) from its base surname. The fixed `gpo_turns.py`/
    `gpo_turns_senate.py` (PR #402, 2026-10-16) started emitting these whenever two
    members/senators sharing a surname both appear in one hearing ("Mr. Austin Scott of
    Georgia." / "Senator Scott of Florida."); before that, GPO prints disambiguated the
    SAME way but the parser only kept the last token, so no caller needed to handle this.
    Returns `(gold_surname, None)` unchanged when there is no " of <state>" suffix, or
    when the trailing word(s) after "of" are not a recognized state/territory name (so a
    turn header that happens to end in "...of the Committee" or similar is never
    mis-split)."""
    if not gold_surname:
        return gold_surname, None
    m = _GOLD_STATE_RE.match(gold_surname.strip())
    if not m:
        return gold_surname, None
    state = m.group(2).strip()
    if state.lower() in US_STATE_ABBR:
        return m.group(1).strip(), state
    return gold_surname, None


def shipped_state_abbr(shipped_name: str) -> str | None:
    """Pulls the two-letter state abbreviation from a shipped display name's trailing
    "(party-state)" parenthetical, e.g. "Rep. Buddy Carter (R-GA)" -> "GA". Returns
    None when the name carries no such parenthetical (e.g. a witness's roster-fallback
    name, which never has one -- witnesses don't get state-qualified gold labels, so
    this is only consulted for member/senator shipped names anyway)."""
    m = _PARTY_STATE_RE.search(shipped_name or "")
    return m.group(2).upper() if m else None


def gold_surname_match(shipped_name: str, shipped_variants_set: set[str], gold_surname: str,
                        state_required: bool = False) -> bool:
    """`surname_match()`, widened to handle a state-qualified gold label ("Carter of
    Georgia"). Always matches on the base surname first (split via
    `split_state_qualifier`); only when the caller sets `state_required=True` -- meaning
    two or more *different* gold speakers in this same hearing share that base surname,
    so the base alone can't tell them apart -- does it additionally require the shipped
    name's own "(party-state)" parenthetical to agree with the qualifier. Reported by the
    2026-10-16 207-hearing re-score (`RESCORE-207-PARSERFIX-2026-10-16.md` §4): the fixed
    parser started emitting `Carter of Georgia`/`Carter of Louisiana`/`Scott of Florida`
    for members who share a surname within one hearing, and the exact-string matcher
    scored all 15 of those clusters "wrong" even though every one's shipped surname was
    already correct -- a scorer gap, not a model error. When state information is
    missing on either side (a witness with no party-state parenthetical, or an
    unrecognized state name), falls back to an exact full-string match rather than
    silently crediting a possibly-wrong same-surname member."""
    base, state = split_state_qualifier(gold_surname)
    if not surname_match(shipped_variants_set, base):
        return False
    if state and state_required:
        want = US_STATE_ABBR.get(state.lower())
        got = shipped_state_abbr(shipped_name)
        if want and got:
            return want == got
        return surname_match(shipped_variants_set, gold_surname)
    return True


def shipped_variants(name: str) -> tuple[str, set[str]]:
    """surname_of_name()/surname_variants() for a shipped display name, widened with the
    "of STATE" nameplate fallback (see strip_of_state_suffix)."""
    surname = surname_of_name(name)
    variants = set(surname_variants(name))
    stripped = strip_of_state_suffix(name)
    if stripped:
        surname = surname_of_name(stripped)
        variants |= set(surname_variants(stripped))
    return surname, variants
