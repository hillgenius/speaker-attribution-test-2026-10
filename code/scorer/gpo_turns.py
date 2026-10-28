"""Parse a GPO hearing print (.htm from GovInfo) into an ORDERED list of
(speaker, turn_text) turns, plus a parallel per-ref-word turn-id array that
lines up 1:1 with `normalize(...).split()` of the same body text (using
`datasets/wer_pilot/scripts/score_one.normalize`), so it can be used directly
against jiwer's `process_words` alignment the same way
`datasets/wer_pilot/scripts/build_clusters.py` does.

Promoted from the validated prototype at
`gpo_spike/gpo_turns.py` (its normalized word stream was checked
word-for-word against `score_one.py`'s hardcoded-marker extraction for
CHRG-119hhrg61182: 12258/12258 tokens identical). The one change from the
prototype is that the hearing-body boundaries (where the Chair's spoken
turns begin and where the adjournment ends) are now auto-detected instead of
hardcoded per hearing — `score_one.gpo_spoken_text` requires a literal
"Mr. Biggs. The Subcommittee will come to order." / "With that, we are
adjourned." pair hand-picked for that one hearing, which does not generalize
(the other three hearings in this dataset use different opening/closing
phrasing entirely — one of them ("Strengthening American Leadership in
Wireless Technology", CHRG-119hhrg58876) never says "come to order" at all).

Auto-detection (verified against all four hearings in this dataset, and
cross-checked to reproduce score_one's hardcoded CHRG-119hhrg61182 body
byte-for-byte modulo surrounding whitespace):

  - start = the first line (after HTML->text extraction) that matches the
    speaker-turn header pattern (`Mr./Ms./Mrs./Dr. NAME.` or `All.`) — GPO
    hearing prints never use that pattern in front matter (committee
    rosters, table of contents), only in the transcript body itself.
  - end = the character offset right before the first
    "[Whereupon, ... was adjourned.]" stage direction after `start` — this
    keeps appendix material (submitted statements, questions for the
    record) out of the spoken-turn stream.

If a hearing's print doesn't fit this pattern (e.g. a Senate hearing that
labels turns as "The Chairman." rather than "Mr./Ms. Name."), pass
`start_marker`/`end_marker` explicitly (exact literal substrings of the
extracted text, as `score_one.py` does) to override auto-detection.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "wer_pilot" / "scripts"))
from bs4 import BeautifulSoup
from score_one import normalize

# Two details of this pattern are load-bearing, both found by CHRG-119hhrg59886
# (a8d58bb9) — the fifth GPO-matched hearing, which this dataset never covered:
#
#   `\s?`  GPO does not always set the space after the honorific. That print
#          writes "Mr.Palmer." for all 321 of its turn headers, so a pattern
#          requiring the space matched none of them and the whole hearing parsed
#          as ONE turn by ONE speaker. Nothing raises: the parse succeeds and
#          every downstream number looks reasonable, which is what makes it
#          dangerous. A word-level gold set built on that parse would have
#          labelled 17,287 words with a single speaker.
#
#   `+`    the captured surname needs at least two letters. With `*` a lone
#          middle initial matches, so a chair reading a witness list aloud
#          ("... Mr. J. Alfredo Gomez, Director of ...") opens a spurious turn
#          for a speaker named "J" — and in that same print "J" then owned 100%
#          of the reference words. This was latent before: requiring the space
#          kept the pattern away from those lines. Allowing the optional space
#          exposes it, and it was always wrong.
#
# Verified byte-for-byte no-op on the four hearings this parser was validated
# against — see test_gpo_turns_leader.py.
#
# Two more details were added after the initial four-hearing validation, both
# found by auditing the frozen word-level gold set for turns whose "speaker"
# was not a person:
#
#   negative lookahead   a vocative like "Mr. Chairman. Thank you for holding
#   for role words        this hearing." matches the witness alternative just
#                          as well as a real "Mr. Smith." does, minting a
#                          speaker literally named "Chairman" (9 gold words in
#                          CHRG-119hhrg58876 were labelled this way). Refusing
#                          Chairman/Chairwoman/Chair/Speaker as a captured
#                          surname closes it; "Ranking Member" is two words
#                          and can never match this single-token capture group
#                          regardless.
#
#   stop the surname at   a self-correction like "Mr. Schmidt--Dr. Schmidt,
#   a double hyphen        thank you" let the old character class cross the
#                          em/en-dash rendered as "--" and swallow into the
#                          next honorific, minting a speaker named
#                          "Schmidt--Dr" (262 gold words in CHRG-119hhrg60129).
#                          `(?:[A-Za-z'’]|-(?!-))+` still allows a single
#                          hyphen for a real hyphenated surname (e.g.
#                          "Ocasio-Cortez") but refuses to bridge "--"; since
#                          "Schmidt" has no literal period inside it, the whole
#                          alternative then fails to match at that line, and
#                          the words fall back onto the still-open previous
#                          turn instead of opening a phantom one.
#
# Both fixes rebuild the frozen gold: see build_gold before/after in
# senate-gpo-turns.patch's accompanying report.
#
# Two more header forms, added 2026-09-26 after the Pilot-8 backlog-sweep
# audit (`~/hillgenius-exports/wordgold-tier-a/out/PILOT8-2026-09-26.md`)
# found the House convention also uses a bare/named CHAIR header that neither
# the witness alternative above nor a plain "All." covers:
#
#   The Chairman. / The Chairwoman.     the presiding chair, unnamed (e.g.
#                                        CHRG-119hhrg61488, CHRG-119hhrg61618)
#   Chairman NAME. / Chairwoman NAME.   the presiding chair, named (e.g.
#                                        CHRG-119hhrg60223, CHRG-119hhrg61537)
#
# These two new alternatives are captured with NAMED groups (`role_name`,
# `bare_role`) precisely so `test_gpo_turns_leader.py`'s regression tests,
# which swap `gpo_turns.LEADER` for OLDER two-group patterns that predate this
# fix, keep working unmodified: `m.groupdict().get(...)` returns None against
# a pattern that never defined that name, instead of raising, so the
# resolution code below falls through to the pre-existing group(1)/group(2)
# path exactly as it always did.
#
# Both new forms carry the same false-positive risk PR #310's "Mr. Chairman."
# fix was written for, in a different header shape: GPO's own already-shipped
# print CHRG-119hhrg58876 contains "Chairman Hudson. It is wonderful to be
# back on this committee--", which is Rep. Miller-Meeks addressing the chair
# mid-turn, line-wrapped by GPO's fixed print width to land as the first
# token on its own physical line. Naively widening the header pattern to
# match "Chairman NAME." would mint a phantom "Hudson" turn inside her real
# one and corrupt that already-shipped, frozen 122,010-word gold set.
#
# The guard (`_accepts_role_candidate`, applied everywhere `LEADER` is
# matched, not baked into the regex) requires BOTH:
#
#   1. paragraph start — the line's ORIGINAL, unstripped leading whitespace
#      is GPO's >=4-space print indent, which only a true new paragraph
#      carries; a line-wrapped continuation (like the Hudson example above,
#      confirmed 0 leading spaces in the raw print) never does; and
#   2. known participant — the captured surname (named form) or the resolved
#      bare-chair surname must equal the hearing's own presiding chair,
#      extracted from the front matter's convening sentence ("Hon. NAME
#      [Chairman of the (Sub)committee] presiding.", see
#      `_house_chair_surname`) — not the full-committee roster line, which
#      names the WRONG person for a subcommittee hearing (verified on
#      CHRG-119hhrg61618: the roster's full-committee chair is Thompson, but
#      the subcommittee chair actually presiding — and the one every bare
#      "The Chairman." in that print's body refers to — is Lucas).
#
# Checked against all five frozen Tier-A prints
# (CHRG-119hhrg{61182,60129,60730,59886,58876}): the only place either new
# alternative's syntax appears at all is the one Hudson line above, and its
# 0 leading spaces fail guard 1, so this addition is a byte-for-byte no-op on
# every one of them — see test_gpo_turns_chair_and_titled_witness.py.
#
# Two more header shapes, added 2026-09-27 after the First-3 pilot audit
# (`~/hillgenius-exports/wordgold-tier-a/out/FIRST3-WRONG-CASES-AUDIT-
# 2026-09-27.md`) found the House convention this parser never covered:
#
#   1. Military-rank witness headers -- `General Allvin.` / `General
#      Saltzman.` (CHRG-119hhrg64331, House Armed Services). Neither name
#      ever appeared as a `gold_speaker` anywhere in that hearing despite
#      both men testifying at length: the print's own front-matter WITNESSES
#      listing ("Allvin, Gen David W., USAF, Chief of Staff of the Air
#      Force") shows they ARE real witnesses, just never captioned
#      "Mr./Ms./Mrs./Dr. NAME." the way this parser expected. New
#      `rank_title`/`rank_name` alternative below, modeled on
#      `gpo_turns_senate.SENATE_LEADER`'s rank/cabinet-title witness
#      headers, with the SAME false-positive guard shape (paragraph-start
#      indent + known-participant check) -- see `_accepts_role_candidate`
#      and `_house_front_matter_known_names`. The House print's own
#      front-matter WITNESSES/MEMBERS table of contents ("Surname, Title
#      First...") is the known-participant source, same convention the
#      Senate module's `_front_matter_known_names` already reads.
#
#   2. Multi-word and state-qualified member surnames -- `Ms. McDonald
#      Rivet.`, `Ms. De La Cruz.`, `Mrs. McClain Delaney.` (compound
#      surnames GPO never abbreviates to one word), and `Mr. Austin Scott
#      of Georgia.`, `Ms. Davids of Kansas.` (GPO's own disambiguation for
#      a shared surname, appended as " of STATE") -- all found in
#      CHRG-119hhrg60714 (House Agriculture). The old capture group allowed
#      exactly one capitalized token, so none of these opened a turn; each
#      member's whole exchange folded into whichever single-token header
#      the parser had most recently recognized (usually the chairman).
#      `member_name` below allows 1-3 capitalized tokens (covers a bare
#      compound surname AND a "First Last" pair ahead of " of STATE") plus
#      an optional `member_state` suffix. Resolution in `gpo_turns()`: a
#      state-qualified match keeps only the LAST token of `member_name` as
#      the speaker (`Austin Scott` -> `Scott`, `Davids` -> `Davids`) and
#      carries the state in the turn's `state` field; an unqualified
#      multi-token match keeps the whole compound as the speaker (`McDonald
#      Rivet`, `De La Cruz`, `McClain Delaney` are not split). A 2-3 token
#      capture is far more likely to false-positive on a word-wrapped
#      mid-sentence reference (e.g. a member naming a colleague) than the
#      old single-token form ever was, so any `member_name` match with more
#      than one token, or a `member_state` suffix, is only accepted at
#      GPO's paragraph-start indent (`_accepts_role_candidate`) -- a plain
#      single-token witness/member match (`Mr. Smith.`) is unguarded,
#      unchanged from before this fix.
#
# NOT a no-op on the five frozen Tier-A prints referenced above: checked
# against all five (CHRG-119hhrg{61182,60129,60730,59886,58876}), four of
# them (60129, 60730, 59886, 58876 -- all House) each gain exactly one new
# "Carter" speaker, from a real, previously-missed "Mr. Carter of Georgia."
# header (confirmed present in each print's own "Members present:"/"Also
# present:" roster line, and at true paragraph-start indent) -- this is the
# same bug class as above, not a false positive, and is pinned turn-by-turn
# in test_gpo_turns_leader.py's FIXED_BY_RANK_AND_MULTITOKEN_SURNAME_FIX.
# 61182 is unaffected. (CHRG-119shrg61334/60080 are Senate prints, routed
# through `gpo_turns_senate.py`, untouched by this module.) See
# test_gpo_turns_rank_and_multiword_surname.py for the synthetic-snippet
# coverage of both new header shapes in isolation.
#
# PRESIDING/CONTINUING BRACKET ANNOTATION and civil-honorific witness
# headers, added 2026-09-27 auditing three more GPO gold-parser gaps found
# by hand (word-aligning cluster text against gold for
# CHRG-119shrg61324, CHRG-119hhrg58803, CHRG-119hhrg60547):
#
#   1. `Governor Reynolds.` (CHRG-119hhrg58803, House Oversight): "The
#      Honorable Kim Reynolds", Governor of Iowa, testified at length and
#      never appeared as a gold speaker -- `rank_title` had no alternative
#      beyond military ranks/Secretary. Widened to also accept the same
#      civil honorifics `gpo_turns_senate.SENATE_LEADER` was asked to cover
#      for its own witnesses (Representative/Professor, see that module),
#      plus Mayor/Ambassador/Judge/Commissioner/Director/Administrator --
#      same false-positive guard (`_accepts_role_candidate`'s paragraph-start
#      + known-participant check), unchanged in shape.
#
#      This print's own WITNESSES front matter doesn't use the
#      "Surname, Title First..." table-of-contents convention
#      `_house_front_matter_known_names` reads (that's the MEMBERS listing
#      convention) -- it lists witnesses "The Honorable Kim K. Reynolds,
#      Governor, state of Iowa" / "Mr. Thomas A. Schatz, President, ..."
#      (title-prefix, full name, ROLE), so a second corroboration source,
#      `_house_witness_intro_names`, reads that convention specifically.
#
#   2. `Mr./Ms./Chairman NAME [continuing].` / `NAME [presiding].` /
#      `NAME. [continuing].` -- a speaker's turn is captioned with a
#      bracketed annotation (GPO's own note that this speaker is resuming
#      after an interjection or taking the gavel) either BEFORE the header's
#      terminal period ("Mr. Strong [presiding]. Thank you.",
#      CHRG-119hhrg60547) or as its own trailing mini-sentence AFTER it,
#      period inside the bracket ("Mr. Palmer. [Presiding]. ...") or outside
#      it ("Governor Reynolds. [continuing]. Highlighting...",
#      CHRG-119hhrg58803). No existing alternative allowed anything between
#      the surname and its period, so every one of these fell through
#      unmatched and its text folded into whichever turn was still open --
#      not necessarily the same speaker (CHRG-119hhrg60547: Rep. McIver
#      yields the floor, "Mr. Strong [presiding]." goes unrecognized, and
#      Strong's own opening remarks as the new presiding member fold into
#      McIver's still-open turn).
#
#      Checking for the same three-shape construct across the already-
#      validated/frozen corpus once it was found in one print: it is
#      pervasive, not rare -- all five frozen Tier-A prints already contain
#      dozens of "NAME [continuing]."-style headers for a speaker resuming
#      after a one-line interjection (e.g. CHRG-119hhrg60129: "Senator
#      Klobuchar. Red tape." / "Mr. Gorman [continuing]. Red tape. We are
#      able to focus on..." -- Gorman repeating the word Klobuchar
#      supplied as he picks his sentence back up), each one silently
#      misattributing that speaker's continued words to whoever's turn was
#      still open. `HEADER_TAG_SUFFIX` below replaces every alternative's
#      bare `\.\s+` terminator; it is a no-op everywhere the annotation is
#      absent (all three of its groups are optional) and moves ONLY
#      previously-mis-split words BACK onto their real, already-established
#      speaker -- never introduces a new one. Pinned turn-by-turn in
#      test_gpo_turns_leader.py's FIXED_BY_PRESIDING_CONTINUING_TAG_FIX.
#      Exported un-underscored (unlike this module's other helpers) so
#      `gpo_turns_senate.py` can reuse it exactly, the same "read-only
#      reuse" pattern that module already uses for ADJOURN_BRACKET.
_HEADER_TAG_WORD = r"(?:[Pp]residing|[Cc]ontinuing)"
# The annotation-and-period group WITHOUT the trailing `\s+` -- exported
# separately so gpo_turns_senate.py can slot it inside its own outer
# alternation and apply ONE shared trailing `\s+` after the whole group,
# matching that module's existing structure (see SENATE_LEADER).
HEADER_TAG = (
    r"(?:\s*\[" + _HEADER_TAG_WORD + r"\])?"  # Style A: "NAME [continuing]."
    r"\."  # the header's own required terminal period
    r"(?:\s*\[" + _HEADER_TAG_WORD + r"\.?\]\.?)?"  # Style B/C: "NAME. [Presiding.]" / "NAME. [continuing]."
)
HEADER_TAG_SUFFIX = HEADER_TAG + r"\s+"

# Bare "Chair NAME." header, added 2026-10-16 after the WRONG-TURN audit
# (`~/hillgenius-exports/wordgold-tier-a/out/factcheck_1013/
# WRONG-TURN-AUDIT.md`) and the batch3/batch4 GOLD_WRONG_CLUSTERS
# comments it pointed at (`score_methods_batch3_shipped.py`,
# `score_methods_batch4_shipped.py`) found a THIRD named-chair spelling
# this parser never covered: "Chair Jordan. Thank you, Mr. Chair..." --
# GPO using the bare word "Chair" (not "Chairman"/"Chairwoman") in front
# of the presiding member's surname when recognizing them, in multiple
# House Judiciary/Oversight prints (e.g. "We now go to the Chair of the
# Full Committee, Mr. Jordan... Chair Jordan. Thank you, Mr. Chair.").
# Every occurrence found was the real chair's own brief recognition-turn
# remark, misattributed by the un-fixed parser to whichever subcommittee
# chair spoke immediately before (Roy, Fitzgerald, Issa, Biggs). Added to
# the SAME `role_name` alternative as Chairman/Chairwoman, so it is
# covered by the identical false-positive guard (`_accepts_role_candidate`:
# paragraph-start indent + the captured name must equal the hearing's own
# presiding chair) -- a mid-sentence vocative like "Thank you, Mr. Chair
# Pro Tem Van Drew." can never match it (not at line start, and "Pro" is
# never the presiding chair's surname). Checked against all five frozen
# Tier-A prints: none contains a line starting with "Chair " at all, so
# this is a byte-for-byte no-op on that corpus -- see
# test_gpo_turns_chair_bare_and_state_qualified_speaker.py.
#
# State-qualified member speaker label, changed 2026-10-16 (same audit):
# the 2026-09-27 fix below (`member_name`/`member_state`) resolved a
# state-qualified header's SPEAKER to the plain surname alone ("Mr.
# Carter of Georgia." -> "Carter"), keeping the state only in the
# separate `state` field. That merges two different members who share a
# surname within the same print -- CHRG-119hhrg60129 captions both "Mr.
# Carter of Georgia." (Rep. Buddy Carter) and "Mr. Carter of Louisiana."
# (Rep. Troy Carter) -- into a single "Carter" speaker, exactly the bug
# class the audit's "81 Carter of <State> turns" finding is about. The
# speaker label now keeps the qualifier ("Carter of Georgia" / "Carter of
# Louisiana"), so the two are distinguishable; see `gpo_turns()` below for
# where this is resolved, and its comment for how a caller that only wants
# the bare surname can still get it.
#
# ROSTER-ABSENCE FALLBACK and GUEST-SENATOR HEADER, added 2026-10-16 after
# the RESIDUAL-31 classification of the 31 clusters hand-excluded as
# GOLD_WRONG before the fix above
# (`~/hillgenius-exports/wordgold-tier-a/out_parserfix_1016/residual31/
# RESIDUAL-31-CLASSIFICATION.md`). 28 of those 31 were parser misses, 25 of
# them one mechanism: `_accepts_role_candidate()`'s `role_name`/`member_name`
# branches reject a second-chair or state-qualified/compound-surname header
# unless the candidate appears verbatim in a "Members present:"/"Also
# present:" roster sentence (or, for a chair, equals the single convening-
# sentence chair) -- but many House committee prints in the pool (T&I, Ways
# and Means, Financial Services, Natural Resources Member Day, Judiciary/
# Oversight subcommittees) never contain that roster sentence at all, so the
# guard fails CLOSED instead of OPEN: every otherwise-correct header in that
# print is rejected, right or wrong, because there is nothing to check it
# against.
#
# The fix distinguishes "no roster sentence was found in this print at all"
# from "a roster was found but doesn't list this candidate"
# (`_house_roster_members()` now returns `None`, not `set()`, for the
# former) and adds a SECOND corroboration source for the no-roster case: a
# candidate that recurs as its own paragraph-start header at least twice
# anywhere in the SAME print is accepted even with no roster to check it
# against (`_house_header_candidate_counts()` below) -- a header that is
# never a one-off false positive but repeats (a member asking questions in
# more than one round, or a chair narrating the same recognition twice) is
# strong independent evidence it is a real turn boundary. For a chair
# candidate specifically, the existing convening-sentence match is tried
# FIRST and is unconditional either way (unchanged); the roster/recurrence
# checks are additional ways to accept a second, different chair surname
# (e.g. the full-committee chair stepping into a subcommittee hearing) that
# convening-sentence equality alone would always reject.
#
# A guest Senator's header inside a House print ("Senator JUSTICE.",
# CHRG-119hhrg60081 -- Sen. Jim Justice recognized briefly in a House
# Judiciary hearing) was a separate, sixth missed form: the House `LEADER`
# had no "Senator" alternative at all. New `guest_senator_name`/
# `guest_senator_state` group below, guarded by the SAME roster-or-
# recurs-twice mechanism as a state-qualified/compound member header (not
# unguarded -- "Senator" is rare enough in a House print, and distinctive
# enough as a title, that the false-positive risk is the same shape as a
# member header, not the much lower one a plain "Mr./Ms. NAME." carries).
#
# Checked against all five frozen Tier-A prints (CHRG-119hhrg{61182,60129,
# 60730,59886,58876}): none contains a "Senator " line at all, and the
# roster-absence fallback only WIDENS acceptance for a candidate that was
# already being rejected, so this is a byte-for-byte no-op on that corpus --
# see test_gpo_turns_roster_guard_and_missed_forms.py.
#
# `rank_title` widened 2026-10-18 after the speaker-public-test smoke rerun's
# Gemini cross-check flagged 11 spans of 8+ words on CHRG-119hhrg63873
# (House Armed Services), all one cause
# (`~/hillgenius-exports/speaker-public-test/smoke_rerun/
# SMOKE-RERUN-2026-10-18.md` section 6): "Admiral Sands." never opened its
# own turn, so his answers folded into the questioning member.
#
# The investigation found TWO separate gaps, not one:
#
#   1. Coverage gap -- Armed Services/Veterans/Homeland Security/
#      Appropriations-defense prints routinely caption witnesses with a
#      military rank or civil office this list didn't yet have an
#      alternative for: Rear Admiral, Vice Admiral (already present), Major
#      General, Brigadier General, Sergeant Major, Captain, Commander,
#      Chief, Superintendent, Sheriff, Reverend. Confirmed real (not
#      hypothetical) by grepping the whole Tier-A cache for a paragraph-
#      start `Title Name.` line: "Sergeant Major Weimer."/"Sergeant Major
#      Ruiz." (CHRG-119hhrg62456), "Sheriff Bouchard."
#      (CHRG-119hhrg59561), "Sheriff Gualtieri." (CHRG-119hhrg59605), and
#      the Senate equivalents cataloged in `gpo_turns_senate.py`'s
#      `_TITLED_TITLE` widening below. Each new alternative carries the
#      SAME false-positive guard as the pre-existing rank_title entries
#      (`_accepts_role_candidate`'s paragraph-start + known-participant
#      check) -- nothing here changes that guard's shape.
#
#   2. Root cause of the Sands case specifically -- "Admiral" was ALREADY
#      in this list; "Admiral Sands." failed the known-participant half of
#      the guard, not the title-alternation half. CHRG-119hhrg63873's own
#      front-matter WITNESSES line reads "Sands III, Rear Admiral Milton
#      J., USN, Commander, Naval Special Warfare Command" -- the "III"
#      generational suffix sits between the surname and the comma
#      `_FRONT_MATTER_NAME` expects immediately after it, so that regex
#      never matched the line at all and "Sands" was silently absent from
#      `known_names`, while "Braga"/"Conley"/"Huntley" (no suffix) in the
#      same print's WITNESSES block were picked up correctly. Confirmed
#      with a grep across the whole Tier-A cache for a front-matter
#      "SURNAME {Jr.|Sr.|II|III|IV},"  line: real, not one-off --
#      CHRG-119hhrg61760 ("Wolfe Jr., ADM Johnny..."), CHRG-119hhrg61960
#      ("Anderson IV, Lieutenant General Leonard F...."), and several
#      Senate prints carry the same shape. Fixed at `_FRONT_MATTER_NAME`
#      below (one shared regex change fixes both this module and
#      `gpo_turns_senate.py`'s identical pattern) rather than by widening
#      `rank_title` further -- widening the title list alone could not
#      have fixed Sands, since "Admiral" already matched.
#
# Pinned in test_gpo_turns_rank_title_widening.py (synthetic excerpts) and
# `datasets/speaker_public_test/scorer/REGRESSION.md` (full-print rerun).
#
# Two more header shapes, added 2026-10-26 after the speaker-public-test
# header scan over the 141 population prints (see REGRESSION.md's
# "Population header-scan widening" re-run):
#
#   The Clerk.      the committee clerk calling the roll in a markup vote
#                   ("The Clerk. Mr. Cloud?" / "The Clerk. Mr. Cloud votes
#                   no.") -- 527 lines across 7 prints, 370 of them in
#                   CHRG-119hhrg61406. No existing alternative matched, so
#                   every roll call's clerk lines folded into whichever
#                   member had answered last. Resolved to the role itself,
#                   speaker "Clerk" (the clerk is never named in the print),
#                   the same way "All." resolves to "All"; paragraph-start
#                   indent required, like the other role headers.
#
#   Judge St. Eve.  a `rank_name` surname with a "St." particle
#                   (CHRG-119hhrg60778, 55 turns) -- the old single-token
#                   capture stopped at the particle's own period. The
#                   particle is kept in the speaker label ("St. Eve"), and
#                   `_house_witness_intro_surname` reads it back the same way
#                   from the front matter, so the known-participant guard is
#                   unchanged in shape.
LEADER = re.compile(
    r"^(?:Mr|Ms|Mrs|Dr)\.\s?(?!(?:Chairman|Chairwoman|Chair|Speaker)\.)"
    r"(?P<member_name>[A-Z](?:[A-Za-z'’]|-(?!-))+(?:\s+[A-Z](?:[A-Za-z'’]|-(?!-))+){0,2})"
    r"(?:\s+of\s+(?P<member_state>[A-Z](?:[A-Za-z'’]|-(?!-))+(?:\s+[A-Z](?:[A-Za-z'’]|-(?!-))+){0,2}))?"
    + HEADER_TAG_SUFFIX + r"|^(All)" + HEADER_TAG_SUFFIX
    + r"|^(?:Chairman|Chairwoman|Chair)\s+(?P<role_name>[A-Z](?:[A-Za-z'’]|-(?!-))+)" + HEADER_TAG_SUFFIX
    + r"|^(?P<bare_role>The Chairman|The Chairwoman)" + HEADER_TAG_SUFFIX
    + r"|^(?P<clerk>The Clerk)" + HEADER_TAG_SUFFIX
    + r"|^(?P<rank_title>Lieutenant General|Vice Admiral|Rear Admiral|Major General"
    r"|Brigadier General|Sergeant Major|General|Admiral|Colonel|Captain|Commander"
    r"|Chief|Secretary|Governor|Mayor|Ambassador|Judge|Commissioner|Director"
    r"|Administrator|Superintendent|Sheriff|Reverend|Professor)"
    r"\s+(?P<rank_name>(?:St\.\s)?[A-Z](?:[A-Za-z'’]|-(?!-))+)" + HEADER_TAG_SUFFIX
    + r"|^Senator\s+(?P<guest_senator_name>[A-Z](?:[A-Za-z'’]|-(?!-))+)"
    r"(?:\s+of\s+(?P<guest_senator_state>[A-Z](?:[A-Za-z'’]|-(?!-))+(?:\s+[A-Z](?:[A-Za-z'’]|-(?!-))+){0,2}))?"
    + HEADER_TAG_SUFFIX
)
# Widened 2026-09-26 after the Plan-300 backlog-sweep prebuild
# (`~/hillgenius-exports/wordgold-tier-a/out/PLAN300-GOLD-2026-09-26.md`)
# found 5/291 packages whose adjournment stage direction doesn't fit the
# original literal shape (comma right after "Whereupon", "adjourned.]" right
# at the close, brackets only):
#
#   parens instead of brackets, and "adjourned" BEFORE the time instead of
#   after it -- CHRG-119shrg{58632,58615,60886} (Senate Select Committee on
#   Intelligence), verified against the actual prints:
#     "(Whereupon the session was adjourned at 12:42 p.m.)"        (58632)
#     "(Whereupon, the hearing was adjourned at 12:07 p.m.)"       (58615)
#     "(Whereupon, the proceedings were adjourned at 4:28 p.m. )"  (60886)
#   None of these have a comma after "Whereupon" in two of the three, and
#   none end "adjourned.]"/"adjourned.)" -- "adjourned" is followed by
#   "at TIME.)" -- so the old pattern's requirement that "adjourned." sit
#   immediately before the closing bracket never matched at all.
#
#   comma after the time instead of after "Whereupon" -- CHRG-119hhrg61284:
#     "[Whereupon at 11:34 a.m., the Subcommittee on Workforce
#      Protections was adjourned.]"
#   (no comma after "Whereupon"; the comma lands after the time instead).
#
# The fix: require "Whereupon" and, somewhere later in the SAME bracket/
# paren, the word "adjourned" -- not a fixed comma position and not
# "adjourned" immediately before the close. Matching is still bounded to a
# single `[...]` or `(...)` pair (the negated character class can't cross a
# bracket boundary), so this can't balloon into swallowing unrelated
# content between two separate stage directions. Verified a byte-for-byte
# no-op on every already-passing package: this widens what can match inside
# one already-required "Whereupon...adjourned" bracket, it doesn't change
# which bracket is found first (see gpo_adjourn re-run in this PR).
ADJOURN_BRACKET = re.compile(
    r"\[Whereupon\b[^\]]*?\badjourned\b[^\]]*?\]"
    r"|\(Whereupon\b[^\)]*?\badjourned\b[^\)]*?\)",
    re.IGNORECASE | re.DOTALL,
)

# Fallback for the one Plan-300 package with NO adjournment stage direction
# at all -- CHRG-119hhrg61761 (House Armed Services). Verified against the
# actual print: the public portion ends
#   "[Whereupon, at 4:31 p.m., the subcommittee proceeded in
#    closed session.]"
# immediately followed by the "A P P E N D I X" banner -- structurally the
# same end-of-body role the adjournment bracket plays elsewhere, just a
# different GPO stage-direction phrasing (moving to executive/closed
# session instead of adjourning outright). Deliberately narrow: this must
# NOT fire on a mid-hearing recess ("[Whereupon, the Committee recessed for
# a vote ...]") that later reconvenes with more testimony, so it requires
# the literal phrase "closed session" inside the SAME bracket as
# "Whereupon" -- checked against every cached Plan-300 print: several
# mention "closed session" in ordinary dialogue, but none pair it with a
# "[Whereupon, ...]" stage direction except CHRG-119hhrg61761's true,
# final one (see gpo_adjourn re-run in this PR). Only tried when
# ADJOURN_BRACKET finds no true adjournment marker at all.
#
# `closed\s+session`, not a literal space, since 2026-10-26: CHRG-119hhrg61589
# (House Armed Services) ends "[Whereupon, at 1:10 p.m., the committee
# proceeded in closed \nsession.]" -- GPO's print width wrapped the phrase
# across two lines, so the literal-space form never matched and the print
# raised GPOBodyNotFound.
CLOSED_SESSION_BRACKET = re.compile(
    r"\[Whereupon\b[^\]]*?closed\s+session[^\]]*?\]"
    r"|\(Whereupon\b[^\)]*?closed\s+session[^\)]*?\)",
    re.IGNORECASE | re.DOTALL,
)


def _find_adjourn_end(raw: str, start: int) -> int | None:
    """Character offset where the spoken-turn body ends, searching `raw`
    from `start`, or None if neither marker is found. Tries the true
    adjournment marker first (ADJOURN_BRACKET); falls back to the
    closed-session transition (CLOSED_SESSION_BRACKET) only when no
    adjournment marker exists in the print at all. Shared by the House
    (`_find_bounds`) and Senate (`gpo_turns_senate._find_bounds_senate`)
    bound-detectors so both chambers get the same fallback."""
    m = ADJOURN_BRACKET.search(raw, start)
    if m is not None:
        return m.start()
    m = CLOSED_SESSION_BRACKET.search(raw, start)
    if m is not None:
        return m.start()
    return None

# The convening sentence at the top of every House print's transcript body,
# e.g. "Hon. Mike Rogers [Chairman of the Committee] presiding." or "Hon.
# Frank D. Lucas [Chairman of the Subcommittee] presiding." (parens instead
# of brackets, and lower-case "chairman", both seen in the wild). Deliberately
# NOT the "NAME, State, Chairman" roster block gpo_turns_senate.py's Senate
# fallback uses — that block lists the FULL COMMITTEE chair even when a
# SUBCOMMITTEE chair is presiding and captioned "The Chairman." throughout
# (CHRG-119hhrg61618: roster says Thompson, presiding sentence says Lucas,
# and the body's own "The Chairman." turns are Lucas's).
_PRESIDING_CHAIR = re.compile(
    r"Hon\.\s+([A-Za-z.'’-]+(?:\s+[A-Za-z.'’-]+)*)\s*[\[\(]\s*chair(?:man|woman)\s+of\s+the\s+"
    r"(?:committee|subcommittee)\s*[\]\)]\s*presiding",
    re.IGNORECASE,
)


def _house_chair_surname(front_matter: str) -> str | None:
    """The presiding chair's surname, from the front matter's convening
    sentence (see `_PRESIDING_CHAIR`), or None if it isn't found (in which
    case the new Chairman/Chairwoman alternatives above never accept —
    same as before this fix)."""
    m = _PRESIDING_CHAIR.search(front_matter)
    if not m:
        return None
    words = m.group(1).split()
    if not words:
        return None
    surname = words[-1].rstrip(".,")
    return surname or None


# GPO's front-matter table of contents indexes every member and witness as
# "Surname, Title First M...." (e.g. "Allvin, Gen David W., USAF, Chief of
# Staff of the Air Force", "Rogers, Hon. Mike, a Representative from
# Alabama, Chairman, ..."). Same convention and same regex
# `gpo_turns_senate._front_matter_known_names` already reads for the
# Senate's rank/cabinet-title witness guard; used here to corroborate a
# House `rank_name` candidate — see `_accepts_role_candidate`.
#
# Optional generational-suffix group added 2026-10-18 -- the root cause of
# the Admiral Sands miss on CHRG-119hhrg63873 (see LEADER's rank_title
# comment above): that print's own WITNESSES line reads "Sands III, Rear
# Admiral Milton J., USN, ...", and the old pattern required the comma
# immediately after the bare surname, so " III" sitting in between meant
# the whole line never matched and "Sands" was silently missing from
# `known_names` -- while "Braga,"/"Conley,"/"Huntley," (no suffix) in the
# same print's WITNESSES block matched fine. Not unique to this print:
# CHRG-119hhrg61760 ("Wolfe Jr., ADM Johnny...") and CHRG-119hhrg61960
# ("Anderson IV, Lieutenant General Leonard F....") carry the same shape.
# The suffix is consumed and discarded (group 1 is still just the bare
# surname, e.g. "Sands"), matching how GPO captions that same witness's
# turn header in the body ("Admiral Sands.", never "Admiral Sands III.").
_FRONT_MATTER_NAME = re.compile(
    r"^([A-Z][A-Za-z'’-]+)(?:\s+(?:Jr|Sr|II|III|IV|V)\.?)?,\s"
)


def _house_front_matter_known_names(front_matter: str) -> set[str]:
    """Surnames GPO's own front-matter index lists for this print (the
    "STATEMENTS PRESENTED BY MEMBERS OF CONGRESS" / "WITNESSES"
    table-of-contents lines). A rank-title witness header (see LEADER's
    `rank_title`/`rank_name`) is only trusted as a real turn boundary when
    its surname is in this set — see `_accepts_role_candidate`.

    Each line is matched stripped since 2026-10-26: some prints indent their
    WITNESSES table of contents (CHRG-119hhrg62888: "    Barton, Todd D.,
    Mayor, City of Crawfordsville, Indiana......    15"), and the anchored
    pattern never matched an indented line, so every "Mayor Barton." turn
    failed the known-participant guard."""
    names = set()
    for line in front_matter.splitlines():
        m = _FRONT_MATTER_NAME.match(line.strip())
        if m:
            names.add(m.group(1))
    return names


# Some House prints' WITNESSES section doesn't use the surname-first
# "Surname, Title First..." table-of-contents convention
# `_house_front_matter_known_names` reads at all -- CHRG-119hhrg58803 (House
# Oversight, found auditing the Governor Reynolds gap) lists its witnesses
# title-prefix-first instead: "The Honorable Kim K. Reynolds, Governor,
# state of Iowa", "Mr. Thomas A. Schatz, President, Citizens Against
# Government Waste", "Dr. William G. Resh (Minority Witness), Associate
# Professor of ...". Same GPO front-matter convention
# `gpo_turns_senate._front_matter_known_names` never had to handle either,
# since every validated Senate print used the surname-first form. Matched
# per stripped line: title prefix, then one or more capitalized given-name/
# middle-initial tokens (consumed greedily so the LAST one before the comma
# is the surname), an optional "(...)" qualifier ("(Minority Witness)"),
# then the comma that starts the role clause.
#
# Widened 2026-10-18 (see "TITLE-FIRST FRONT-MATTER WITNESS NAMES" in
# `gpo_turns_senate.py`'s module docstring for the full writeup, and the
# matching Senate fix this mirrors) from Mr./Ms./Mrs./Dr./Hon./The Honorable
# alone to also anchor on every `LEADER` `rank_title` word: checked by
# sweeping all 189 cached House prints before/after this widening (same
# `gpo_turns()` behavioral diff the Senate side ran), found it is a real,
# not speculative, gap here too -- CHRG-119hhrg59561 lists "Sheriff Michael
# Bouchard, Vice President, Government Affairs, Major County Sheriffs of
# America" and CHRG-119hhrg61341 lists "Rear Admiral Adam A. Chamie,
# Assistant Commandant for Response Policy, U.S. Coast Guard", neither
# captured by the old anchor, so "Sheriff Bouchard."/"Admiral Chamie."
# turns in those two prints' bodies (both witnesses already real,
# front-matter-listed, and already-accepted `rank_title` headers) were
# failing the known-participant guard and folding into whoever spoke
# before them -- 350 -> 408 turns and 137 -> 151 turns respectively.
# Re-sweeping against the actual edited file below (not just the prefix
# widening in isolation) surfaced a THIRD, independent diff the scratch
# patch alone had missed: CHRG-119hhrg64440 lists "Lieutenant General
# William H. ``Butch'' Graham, Jr., Chief of Engineers..." -- the
# character-class-based token regex this replaced choked on the
# non-ASCII-quoted nickname ("``Butch''") and never reached "Graham" at
# all, where the plain `.split()` tokenization below just takes the last
# token regardless of what came before it (207 -> 246 turns). No other
# print's turn count or speaker set changed across the full 189-print
# cached House pool -- the 3 named above are the only diffs (177 of the
# remaining 186 are byte-identical before/after; the other 9 raise the
# same pre-existing missing-start-marker error in both old and new code,
# unrelated to this fix) -- verified directly against this file, not a
# stand-in scratch patch. Professor and Representative are deliberately
# NOT added here even though
# `gpo_turns_senate._TITLED_TITLE` has them: no cached House print's
# WITNESSES section anchors a title-first entry on either word, and this
# module's own `rank_title` has no `Representative` alternative at all
# (House members are never captioned that way in the body).
#
# "The Hon." and a bare "Honorable" added 2026-10-26 (population header scan):
# CHRG-119hhrg60778 lists "The Hon. Amy J. St. Eve, Circuit Judge, ..." and
# "The Hon. Michael Y. Scudder, Jr., Circuit Judge, ...", and CHRG-119hhrg63127
# lists "Honorable Kristi Noem, Secretary, U.S. Department of Homeland
# Security" -- neither spelling matched the old anchor, so "Judge Scudder."
# (30 turns) and "Secretary Noem." (80 turns) failed the known-participant
# guard and folded into the questioning member.
_WITNESS_INTRO_PREFIX = re.compile(
    r"^(?:The Honorable|The Hon\.|Honorable|Hon\.|Mr|Ms|Mrs|Dr"
    r"|Lieutenant General|Vice Admiral|Rear Admiral|Major General"
    r"|Brigadier General|Sergeant Major|General|Admiral|Colonel|Captain"
    r"|Commander|Chief|Secretary|Governor|Mayor|Ambassador|Judge"
    r"|Commissioner|Director|Administrator|Superintendent|Sheriff|Reverend"
    r"|Professor)\.?\s+"
)

# A trailing generational suffix ("Jr."/"Sr."/"II"/"III"/"IV"/"V") or a
# military/civil post-nominal ("USN"/"USA"/"USAF"/"USMC"/"Ph.D."/"M.D."/
# "Esq.") sitting between the surname and the role-clause comma is discarded
# before taking the last remaining token as the surname -- same shape, same
# reason, and the same token lists as
# `gpo_turns_senate._title_first_surname`'s identical fix (see that
# function's comment): a title-first line like "Chief Robert Olivarez Jr.,
# National Commander, ..." must still resolve to "Olivarez", not "Jr.". Not
# yet observed in the cached House corpus (every example there puts a comma
# before the suffix, e.g. "Mr. James C. Harris, III, Assistant Director,
# ..."), but handled the same way as the Senate fix rather than skipped
# speculatively, since the suffix/post-nominal class of gap has already
# recurred three times across the two chamber modules (`_FRONT_MATTER_NAME`
# x2, now this).
_WITNESS_INTRO_SUFFIX_TOKENS = {"jr", "sr", "ii", "iii", "iv", "v"}
_WITNESS_INTRO_POST_NOMINAL_TOKENS = {"usn", "usa", "usaf", "usmc", "ph.d", "phd", "m.d", "md", "esq"}


def _house_witness_intro_surname(line: str) -> str | None:
    """The witness's surname from a title-prefix-first WITNESSES line (see
    `_WITNESS_INTRO_PREFIX`) -- the last capitalized token before the first
    comma (or a parenthetical qualifier like "(Minority Witness)"), with a
    trailing generational suffix or post-nominal discarded first. `None` if
    `line` doesn't open with a recognized title at all."""
    m = _WITNESS_INTRO_PREFIX.match(line)
    if not m:
        return None
    rest = line[m.end():]
    end = len(rest)
    comma = rest.find(",")
    if comma != -1:
        end = comma
    paren = rest.find("(")
    if paren != -1 and paren < end:
        end = paren
    tokens = rest[:end].split()
    while tokens:
        bare = tokens[-1].rstrip(".").lower()
        if bare in _WITNESS_INTRO_SUFFIX_TOKENS or bare in _WITNESS_INTRO_POST_NOMINAL_TOKENS:
            tokens.pop()
        else:
            break
    if not tokens:
        return None
    surname = tokens[-1]
    if not re.fullmatch(r"[A-Z][A-Za-z'’-]+", surname):
        return None
    # A "St." particle stays with the surname ("Amy J. St. Eve" -> "St. Eve"),
    # matching how LEADER's `rank_name` captures that witness's own header.
    if len(tokens) >= 2 and tokens[-2] == "St.":
        return f"St. {surname}"
    return surname


def _house_witness_intro_names(front_matter: str) -> set[str]:
    """Surnames from the title-prefix-first WITNESSES convention (see
    `_house_witness_intro_surname`) -- a second, additive corroboration
    source for a civil-honorific `rank_name` candidate (LEADER's
    `rank_title`/`rank_name`) alongside `_house_front_matter_known_names`.
    Extra names picked up here are harmless: they only widen the
    known-participant ALLOWLIST a candidate is checked against, they can
    never themselves open a turn."""
    names = set()
    for line in front_matter.splitlines():
        surname = _house_witness_intro_surname(line.strip())
        if surname:
            names.add(surname)
    return names


# The committee and subcommittee roster blocks at the top of a House print
# list each chair as "NAME, State, Chairman" ("FRENCH HILL, Arkansas,
# Chairman", "JIM JORDAN, Ohio, Chair", and in some subcommittee blocks mixed
# case, "Pete Sessions, Texas, Chairman"). Same shape as
# `gpo_turns_senate._ROSTER_CHAIR`, with a mixed-case name allowed. Added
# 2026-10-26 (population header scan) as a corroboration source for a named
# `role_name` header whose surname is not the convening sentence's presiding
# chair: a full committee chair stepping into a subcommittee hearing is
# listed in these blocks but usually not in that subcommittee's roster
# sentence. A chair who speaks more than once is already accepted by
# recurrence (10 "Chairman Hill." turns in CHRG-119hhrg59599, 15 "Chair
# Jordan." in 60070); this source is what accepts one who speaks once
# ("Chairman Mast." in 60454, and "Chairman Comer." in the development-pool
# print 58806). "Vice Chairman" lines never match: the final comma must sit
# directly before the role word.
_HOUSE_ROSTER_BLOCK_CHAIR = re.compile(
    r"^([A-Za-z][A-Za-z '.’-]+),\s*(?:[A-Za-z .]+,\s*)+(?:Chairman|Chairwoman|Chair)\s*$"
)


def _house_roster_block_chairs(front_matter: str) -> set[str]:
    """Lowercased surnames of every chair listed in the front matter's roster
    blocks -- see `_HOUSE_ROSTER_BLOCK_CHAIR`."""
    names = set()
    for line in front_matter.splitlines():
        m = _HOUSE_ROSTER_BLOCK_CHAIR.match(line.strip())
        if m:
            words = m.group(1).split()
            if words:
                names.add(words[-1].lower())
    return names


# Comma-separated House roster sentences -- "Members present: Representatives
# NAME1, NAME2 of STATE, ..." and, separately, "Also present: Representatives
# NAME1, ..." for members attending from outside the (sub)committee -- are
# GPO's own enumeration of every member in the room, spelled EXACTLY the way
# GPO captions that member's own turn header in the body: a compound surname
# ("De La Cruz", "McDonald Rivet", "McClain Delaney") or a state-
# disambiguating suffix ("Austin Scott of Georgia", "Davids of Kansas")
# appears there in the identical form. This is a much more precise
# corroboration source for a multi-token/state-qualified `member_name`
# candidate than the front-matter WITNESSES/MEMBERS table of contents
# (`_house_front_matter_known_names`) would be: a witness the CHAIR
# introduces by full name in third-person narration (found auditing
# CHRG-119hhrg60129 while validating this fix -- "Dr. Manish Bhatia. Mr.
# Manish Bhatia, executive vice president of global operations...", a real
# GPO paragraph, paragraph-start-indented, that is the Chair's own turn
# introducing the witness, NOT Bhatia's) would pass a known-participant
# check keyed off the witness table of contents, since Bhatia IS a real,
# front-matter-listed witness -- but a witness is never a "Representative",
# so "Manish Bhatia" can never appear in a Members-present/Also-present
# roster line, and this guard correctly rejects it while still accepting
# every multi-token/state-qualified MEMBER header (verified: adding this
# roster check is what took CHRG-119hhrg60129/60730/58876/59886 -- the four
# already-frozen Tier-A prints this widening incidentally touches, all via
# real "Mr. Carter of Georgia." headers those hearings' own old parse never
# recognized either -- from a Bhatia-contaminated diff back to a clean one;
# see test_gpo_turns_rank_and_multiword_surname.py).
#
# Two changes on 2026-10-26 (population header scan):
#
#   - The bare "Present: Representatives ..." form is read too. 76 House
#     population prints caption their roster that way, with no "Members",
#     so `_house_roster_members` saw only an "Also present:" line or
#     nothing, and a single "Ms. Williams of Georgia." turn
#     (CHRG-119hhrg61136), named on that print's own "Present:" line, was
#     rejected.
#   - The roster now corroborates a header but no longer vetoes one (see
#     `_accepts_role_candidate`), because the spelling match described above
#     does not hold in every print. The roster can drop the state ("Carter",
#     twice, for "Mr. Carter of Georgia." and "Mr. Carter of Louisiana." in
#     the development-pool print CHRG-119hhrg58842), spell in mixed case a
#     surname the body captions in capitals ("Alford" for "Chairman
#     ALFORD.", 59421), or leave a speaker out entirely (the Senators at a
#     joint hearing, 60081; a member testifying as a witness, "Mr. Smith of
#     Missouri.", 58836). Under the veto, each of those turns was rejected
#     as soon as the print's roster line was recognized.
_HOUSE_ROSTER_LINE = re.compile(
    r"(?:Members present|Also present|Present):\s*Representatives?\s+(.*?)\.\s",
    re.DOTALL,
)


def _house_roster_members(raw: str) -> set[str] | None:
    """Every member named in a "Members present:"/"Also present:" roster
    sentence, spelled exactly as GPO captions that member's own turn header
    (see `_HOUSE_ROSTER_LINE`), or `None` if this print contains NO such
    roster sentence at all.

    Returning `None` (not `set()`) for the no-roster case was the fix for
    RESIDUAL-31 forms #2/#3 (2026-10-16), when the guard this corroborates
    (`_accepts_role_candidate`) rejected a candidate a roster did not list
    and fell back to `_house_header_candidate_counts` only when the print
    had no roster at all. Since 2026-10-26 the roster only adds
    corroboration, so the distinction no longer changes that guard's
    decision; the return contract is unchanged.

    Names are split on " and " as well as on commas since 2026-10-26: a
    two-name roster has no comma at all ("Also present: Representatives Knott
    and Moore of North Carolina.", CHRG-119hhrg61247), and the old comma-only
    split kept it as one name, so neither member was found."""
    names = set()
    found = False
    for m in _HOUSE_ROSTER_LINE.finditer(raw):
        found = True
        body = re.sub(r"\s+", " ", m.group(1)).strip()
        for part in re.split(r",|\s+and\s+", body):
            part = re.sub(r"^\s*and\s+", "", part.strip()).strip()
            if part:
                names.add(part)
    return names if found else None


def _house_header_candidate_counts(body: str) -> dict[tuple[str, str], int]:
    """Count how many times each `role_name`/`member_name`(+state)/
    `guest_senator_name`(+state) candidate recurs as its OWN paragraph-start
    `LEADER` header anywhere in `body` — regardless of whether that
    particular occurrence itself already passes `_accepts_role_candidate`
    (this is the corroboration source for cases that don't, so computing it
    from already-accepted turns would be circular).

    Corroboration for RESIDUAL-31 forms #1/#2/#3/#6 (2026-10-16), used
    then only when a print had no roster sentence at all and, since
    2026-10-26, in every print: a candidate that opens a paragraph more than
    once under the identical header is strong independent evidence it is a
    real turn boundary, not a one-off false-positive vocative (a vocative
    like "thank you, Mr. Chair Pro Tem Van Drew" is never itself a
    paragraph-start line, so it can't inflate this count) — see
    `_accepts_role_candidate`. A chair introducing a witness by full name
    does so once ("Dr. Manish Bhatia.", CHRG-119hhrg60129; "Mr. Wade
    Miller.", 61917; "Ms. Julie Margetta Morgan.", 60624), so that paragraph
    counts 1 and stays in the chair's turn."""
    counts: dict[tuple[str, str], int] = {}
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("["):
            continue
        if line.upper() == line and len(line) < 160:
            continue
        if len(raw_line) - len(raw_line.lstrip(" ")) < 4:
            continue
        m = LEADER.match(line)
        if not m:
            continue
        gd = m.groupdict()
        role_name = gd.get("role_name")
        member_name = gd.get("member_name")
        member_state = gd.get("member_state")
        guest_senator_name = gd.get("guest_senator_name")
        guest_senator_state = gd.get("guest_senator_state")
        if role_name:
            key = ("chair", role_name)
        elif member_name is not None and (member_state or " " in member_name):
            full = f"{member_name} of {member_state}" if member_state else member_name
            key = ("member", full)
        elif guest_senator_name is not None:
            full = (f"{guest_senator_name} of {guest_senator_state}"
                     if guest_senator_state else guest_senator_name)
            key = ("senator", full)
        else:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def _accepts_role_candidate(
    m: re.Match,
    raw_line: str,
    chair_surname: str | None,
    known_names: set[str] | None = None,
    roster_members: set[str] | None = None,
    header_counts: dict[tuple[str, str], int] | None = None,
    roster_block_chairs: set[str] | None = None,
) -> bool:
    """True unless `m` is a candidate that fails its false-positive guard:

      - `role_name`/`bare_role` (Chairman/Chairwoman/Chair): paragraph-start
        indent, AND one of: the name equals the hearing's own presiding
        chair (the original, unconditional check — described above
        `LEADER`); OR the front matter's roster blocks list that surname as
        a chair (`roster_block_chairs`, see `_house_roster_block_chairs`);
        OR the name appears in the print's own roster sentence
        (`roster_members`); OR the name recurs as its own paragraph-start
        header at least twice in this print (`header_counts`). These checks
        only widen acceptance of a SECOND, different chair surname (e.g. the
        full-committee chair stepping into a subcommittee hearing) — they
        never relax the original convening-sentence check.
      - `rank_name` (military-rank witness, e.g. "General Allvin."):
        paragraph-start indent + the surname must be a known participant
        from the print's own front-matter WITNESSES/MEMBERS listing (or
        already established as a speaker earlier in this same parse — see
        `gpo_turns()`'s `known_names.add(speaker)`). Unchanged by this fix.
      - `member_name` with more than one token, or carrying a
        `member_state` qualifier (e.g. "Ms. McDonald Rivet.", "Mr. Austin
        Scott of Georgia."), and `guest_senator_name` (a guest Senator's
        header inside a House print, e.g. "Senator JUSTICE."): paragraph-
        start indent AND either the full candidate (name, plus " of " +
        state when present) appears in the print's own roster sentence
        (`roster_members`), or it recurs as its own paragraph-start header
        at least twice in this print (`header_counts`).
      - `clerk` ("The Clerk.", added 2026-10-26): paragraph-start indent,
        like the other role headers.

    Changed 2026-10-26 (population header scan): a roster sentence used to
    be the only check for a print that had one, so a candidate it did not
    list was rejected even when it recurred, and recurrence counted only in
    a print with no roster. The roster is now one corroboration source
    among the others; the comment above `_HOUSE_ROSTER_LINE` lists the
    turns the veto was rejecting. A one-off header from someone the roster
    does not list, such as a chair's full-name introduction of a witness,
    is still rejected. Names are compared with the presiding chair and the
    roster without regard to case: Small Business prints caption "Chairman
    ALFORD.", "Chairman JACK." and "Chairman LALOTA." over a convening
    sentence and roster that spell the name in mixed case.

    Any other `LEADER` match (a plain single-token witness/member, the
    pre-existing "All" alternative, or a match against an older pattern
    that doesn't define these named groups at all) is always accepted,
    unchanged from before this fix."""
    gd = m.groupdict()
    role_name = gd.get("role_name")
    bare_role = gd.get("bare_role")
    rank_name = gd.get("rank_name")
    member_name = gd.get("member_name")
    member_state = gd.get("member_state")
    guest_senator_name = gd.get("guest_senator_name")
    guest_senator_state = gd.get("guest_senator_state")
    indent = len(raw_line) - len(raw_line.lstrip(" "))
    roster = {n.lower() for n in roster_members} if roster_members else set()

    if gd.get("clerk"):
        return indent >= 4
    if role_name or bare_role:
        candidate = role_name or chair_surname
        if indent < 4 or candidate is None:
            return False
        if chair_surname and candidate.lower() == chair_surname.lower():
            return True
        if role_name and roster_block_chairs and role_name.lower() in roster_block_chairs:
            return True
        if candidate.lower() in roster:
            return True
        return header_counts is not None and header_counts.get(("chair", candidate), 0) >= 2
    if rank_name:
        return indent >= 4 and known_names is not None and rank_name in known_names
    if member_name is not None and (member_state or " " in member_name):
        if indent < 4:
            return False
        full = f"{member_name} of {member_state}" if member_state else member_name
        if full.lower() in roster:
            return True
        return header_counts is not None and header_counts.get(("member", full), 0) >= 2
    if guest_senator_name is not None:
        if indent < 4:
            return False
        full = (f"{guest_senator_name} of {guest_senator_state}"
                 if guest_senator_state else guest_senator_name)
        if full.lower() in roster:
            return True
        return header_counts is not None and header_counts.get(("senator", full), 0) >= 2
    return True


class GPOBodyNotFound(ValueError):
    """Raised when the hearing body's start/end can't be auto-detected."""


def _find_bounds(raw: str) -> tuple[int, int]:
    """Auto-detect (start_offset, end_offset) of the spoken-turn body within
    `raw` (soup.get_text("\\n") of the GPO .htm). See module docstring."""
    lines = raw.splitlines(keepends=True)
    offsets = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line)

    chair_surname = _house_chair_surname(raw)
    known_names = _house_front_matter_known_names(raw) | _house_witness_intro_names(raw)
    roster_members = _house_roster_members(raw)
    start_line = None
    for i, line in enumerate(lines):
        m = LEADER.match(line.strip())
        if m and _accepts_role_candidate(m, line, chair_surname, known_names, roster_members):
            start_line = i
            break
    if start_line is None:
        raise GPOBodyNotFound(
            "No line matching the Mr./Ms./Mrs./Dr./All./Chairman/Chairwoman "
            "speaker-turn pattern was found — pass start_marker explicitly "
            "for this hearing."
        )
    start = offsets[start_line]

    end = _find_adjourn_end(raw, start)
    if end is None:
        raise GPOBodyNotFound(
            "No '[Whereupon, ... was adjourned.]' (or closed-session "
            "transition) stage direction was found after the detected "
            "start — pass end_marker explicitly for this hearing."
        )
    return start, end


def gpo_turns(path: Path, start_marker: str | None = None, end_marker: str | None = None):
    """Returns an ordered list of {"speaker": str, "text": str, "state": str
    | None} turns. `state` is only set for a state-qualified member header
    ("Mr. Austin Scott of Georgia." -> speaker="Scott", state="Georgia");
    every other turn carries `state=None`.

    `start_marker`/`end_marker`, if given, are literal substrings of the
    extracted text (matching score_one.py's convention) that override
    auto-detection of the hearing body's bounds.
    """
    soup = BeautifulSoup(path.read_text(), "html.parser")
    raw = soup.get_text("\n")

    if start_marker is not None and end_marker is not None:
        start = raw.index(start_marker)
        end = raw.index(end_marker, start) + len(end_marker)
    else:
        start, end = _find_bounds(raw)

    turns = []  # list of {"speaker":..., "lines":[...], "state":...}
    for raw_line, line, header in house_body_lines(raw, start, end):
        if header is None:
            continue
        if header:
            speaker, state, rest = header
            turns.append({"speaker": speaker, "lines": [rest], "state": state})
        elif not turns:
            # shouldn't happen given the start marker, but guard anyway
            turns.append({"speaker": "UNKNOWN", "lines": [line], "state": None})
        else:
            turns[-1]["lines"].append(line)

    out = []
    for t in turns:
        text = " ".join(t["lines"])
        out.append({"speaker": t["speaker"], "text": text, "state": t.get("state")})
    return out


def house_body_lines(raw: str, start: int, end: int):
    """Walk the body `raw[start:end]` line by line exactly as `gpo_turns()`
    reads it, yielding `(raw_line, line, header)` for every physical line:

      - `header is None`: a line the parser skips outright (blank, a bracketed
        stage direction, or an all-caps section heading);
      - `header is False`: a line that continues whichever turn is open;
      - `header == (speaker, state, rest)`: a line that opens a new turn.

    Split out of `gpo_turns()` so `header_scan.py` classifies each line with
    the parser's own decision -- the same front-matter slice, the same
    recurrence counts, and the same running `known_names` -- instead of a
    re-derivation that can drift from it."""
    body = raw[start:end]
    # Repair GPO's print-layout word wrapping (e.g. "thought-\nprovoking").
    body = re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", "", body)

    chair_surname = _house_chair_surname(raw[:start])
    known_names = _house_front_matter_known_names(raw[:start]) | _house_witness_intro_names(raw[:start])
    roster_members = _house_roster_members(raw[:start])
    header_counts = _house_header_candidate_counts(body)
    roster_block_chairs = _house_roster_block_chairs(raw[:start])

    body_lines = body.splitlines()
    for idx, raw_line in enumerate(body_lines):
        line = raw_line.strip()
        if not line or line.startswith("["):
            yield raw_line, line, None
            continue
        if line.upper() == line and len(line) < 160:
            yield raw_line, line, None
            continue
        m = LEADER.match(line)
        if m is None:
            # Form #7 (RESIDUAL-31, 2026-10-16): a header that is the
            # ENTIRE paragraph-start line, with no speech text at all
            # before the next physical line, fails LEADER's required
            # trailing `\s+` (there is nothing left on this line once it's
            # `.strip()`ed to match against) -- CHRG-119hhrg60092 captions
            # "    Mrs. Radewagen.\n    [Foreign language spoken.]\n    Good
            # afternoon. Thank you, Chairwoman Kim...". Recognized ONLY
            # when paragraph-start-indented AND the very next physical line
            # is itself a bracketed stage direction -- deliberately narrow:
            # a header missing its trailing text for the much more common
            # OTHER reason (a line-wrapped mid-sentence vocative at 0
            # indent, e.g. "...My questions are of\nMr. Turk.", confirmed
            # in the already-frozen CHRG-119hhrg60129) must NOT be accepted
            # here, and isn't -- it both fails the indent check and is
            # never followed by a bracket line. Reuses LEADER unchanged
            # (matched against `line + " "`, a single padding space, so the
            # existing `\s+` requirement is satisfied without widening the
            # shared pattern/constant for every other caller) so this
            # candidate still goes through the exact same named-group
            # resolution and `_accepts_role_candidate` guard as every other
            # header shape below.
            indent = len(raw_line) - len(raw_line.lstrip(" "))
            if indent >= 4 and idx + 1 < len(body_lines) and body_lines[idx + 1].strip().startswith("["):
                m2 = LEADER.match(line + " ")
                if m2 is not None and m2.end() == len(line) + 1:
                    m = m2
        speaker = None
        state = None
        rest = None
        if m and _accepts_role_candidate(m, raw_line, chair_surname, known_names, roster_members, header_counts,
                                         roster_block_chairs):
            gd = m.groupdict()
            role_name = gd.get("role_name")
            bare_role = gd.get("bare_role")
            rank_name = gd.get("rank_name")
            member_name = gd.get("member_name")
            member_state = gd.get("member_state")
            guest_senator_name = gd.get("guest_senator_name")
            guest_senator_state = gd.get("guest_senator_state")
            if role_name or bare_role:
                speaker = role_name or chair_surname
            elif rank_name:
                speaker = rank_name
            elif member_name:
                if member_state:
                    # State-qualified header ("Mr. Austin Scott of
                    # Georgia.", "Ms. Davids of Kansas.", "Mr. Carter of
                    # Georgia."): the plain surname is the LAST token
                    # before " of STATE" — GPO only prepends a first name
                    # when disambiguating a shared surname, the surname
                    # itself is still the tail token.
                    #
                    # The speaker label KEEPS the state qualifier
                    # ("Carter of Georgia", not just "Carter") -- fixed
                    # 2026-10-16 after the WRONG-TURN audit
                    # (~/hillgenius-exports/wordgold-tier-a/out/
                    # factcheck_1013/WRONG-TURN-AUDIT.md) found
                    # CHRG-119hhrg60129 captions BOTH "Mr. Carter of
                    # Georgia." (Rep. Buddy Carter) and "Mr. Carter of
                    # Louisiana." (Rep. Troy Carter) in the same print;
                    # dropping the state here (as the 2026-09-27 fix
                    # originally did) merged two different members into
                    # one "Carter" speaker. `state` still carries the
                    # qualifier on its own for a caller that wants it
                    # separately; a caller that only wants the plain
                    # surname can still get it by splitting the speaker
                    # string on " of ".
                    speaker = f"{member_name.split()[-1]} of {member_state}"
                    state = member_state
                else:
                    # Compound surname with no state qualifier ("Ms.
                    # McDonald Rivet.", "Ms. De La Cruz.", "Mrs. McClain
                    # Delaney."): GPO never abbreviates these to one word,
                    # so the whole captured phrase is the surname.
                    speaker = member_name
            elif guest_senator_name:
                # A guest Senator's header inside a House print ("Senator
                # JUSTICE.") -- same " of STATE" resolution as a House
                # member header or a Senate-print "Senator NAME of STATE."
                # header: keep the qualifier in the speaker label so two
                # same-surname guests are never merged.
                if guest_senator_state:
                    speaker = f"{guest_senator_name.split()[-1]} of {guest_senator_state}"
                    state = guest_senator_state
                else:
                    speaker = guest_senator_name
            elif gd.get("clerk"):
                speaker = "Clerk"
            else:
                speaker = m.group(1) if m.group(1) else "All"
            rest = line[m.end():]
        if speaker is not None:
            known_names.add(speaker)
            yield raw_line, line, (speaker, state, rest)
        else:
            yield raw_line, line, False


def build_ref_turn_index(path: Path, start_marker: str | None = None, end_marker: str | None = None):
    """Returns (ref_words, turn_id_per_word, turns) where turn_id_per_word[i]
    is the index into `turns` for ref_words[i]. `ref_words` is exactly
    `normalize(" ".join(turn texts)).split()` word-for-word, so it lines up
    1:1 with the `ref` array jiwer's `process_words` operates on when you
    pass `" ".join(ref_words)` as the reference string.
    """
    turns = gpo_turns(path, start_marker, end_marker)
    ref_words = []
    turn_id = []
    for ti, t in enumerate(turns):
        toks = normalize(t["text"]).split()
        ref_words.extend(toks)
        turn_id.extend([ti] * len(toks))
    return ref_words, turn_id, turns


if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parent.parent.parent / "wer_pilot" / "gpo-CHRG-119hhrg61182.htm"
    )
    turns = gpo_turns(p)
    print(f"{p.name}: {len(turns)} turns")
    for t in turns[:8]:
        print(f"  [{t['speaker']}] {t['text'][:80]!r}")

    ref_words, turn_id, _ = build_ref_turn_index(p)
    print(f"ref_words={len(ref_words)} turn_id={len(turn_id)}")
