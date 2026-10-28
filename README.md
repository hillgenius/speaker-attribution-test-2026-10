# HillGenius speaker-attribution public test, October 2026

Every file from the public test of Tiro 1, the HillGenius transcription system, on 100
congressional hearings drawn at random and scored against the official GPO printed record.
Results: https://www.hillgenius.com/tiro-1. Full report:
https://www.hillgenius.com/methodology/speaker-attribution/report (Markdown:
https://www.hillgenius.com/methodology/speaker-attribution.md).

> © 2026 HillGenius. You may download, run and share these files to check the results. All other rights reserved. The GPO prints and govinfo text are U.S. government works. See [NOTICE.md](NOTICE.md).

- By words: 99.4% (1,639,116 of 1,649,095)
- By speakers: 98.8% (1,669 of 1,690)

## Check the headline

[per_hearing.csv](per_hearing.csv) has one row per hearing and a TOTAL row last.

    by words    = sum(word_correct) / (sum(word_correct) + sum(word_wrong))
    by speakers = sum(cluster_correct) / (sum(cluster_correct) + sum(cluster_wrong))

Every file here is listed in [SHA256SUMS](SHA256SUMS): `shasum -a 256 -c SHA256SUMS`.

## Rerun the score

Python 3.12, jiwer 4.0.0, beautifulsoup4 4.14.3. From code/scorer/, for each hearing in
[sampling/sample.json](sampling/sample.json) (use references_corrected/ where it exists):

    python score.py --hearing-id <hearing_id> --chrg <CHRG id> --print <GPO print> \
      --segments ../../transcripts/<hearing_id>.segments.jsonl \
      --reference ../../references/<hearing_id>/reference_final.json \
      --roster-cache ../../roster_cache --out out/<hearing_id>
    python pool.py "out/*/*-per-cluster.jsonl" --out pooled.json

Each GPO print is on GovInfo (links in [prints/prints.json](prints/prints.json)); the three prints GovInfo's
mirror alters are in [prints/](prints/).

## Notes

- The pre-registration promised a calibration of the parser against the AI reading on the 207-hearing development pool; only a 5-hearing pilot was run. The two agreed on 95.9% of words at first and on 98.8% to 100% after parser fixes, on the model used, and the parser was right in all 9 disagreements checked by hand. This does not affect the score. The report's section "Corrections after scoring" lists this with the other
  departures from the pre-registration.
- The score was corrected after scoring by three rules applied to all 100 hearings;
  both numbers are published. See [corrections.json](corrections.json) and [results/locked_run/](results/locked_run/).

## Files

| Path | What it is |
|---|---|
| [summary.json](summary.json) | Headline, chamber split, members-vs-witnesses split, bootstrap interval, coverage, error causes, before-correction figures |
| [per_hearing.csv](per_hearing.csv) | One row per hearing plus a TOTAL row |
| [corrections.json](corrections.json) | The three correction rules and the six voices they changed |
| [PREREGISTRATION.md](PREREGISTRATION.md) | The protocol as written before the draw, plus two sections added after scoring (redacted copy) |
| [NOTICE.md](NOTICE.md) | Copyright notice |
| [SHA256SUMS](SHA256SUMS) | SHA-256 of every file in this repository |
| [results/pooled.json](results/pooled.json) | The pooled score, as written by code/scorer/pool.py |
| [results/per_cluster.jsonl](results/per_cluster.jsonl) | One row per scored voice: print speaker, our label, words, verdict, match rule |
| [results/per_hearing.tsv](results/per_hearing.tsv) | The scorer's own per-hearing table |
| [results/bioguide_check.txt](results/bioguide_check.txt) | Every member id in the references checked against each print's member list |
| [results/member_id_check.jsonl](results/member_id_check.jsonl) | Every scored voice's member id compared with the reference's (code/check_member_ids.py) |
| [results/roles_post_hoc.jsonl](results/roles_post_hoc.jsonl) | Each scored voice as member, witness or other, for the members-vs-witnesses breakdown (made after scoring) |
| [results/locked_run/](results/locked_run/) | The same results before the reference corrections |
| [references/<hearing_id>/](references/) | Frozen reference (reference_final.json), disagreement spans, review sheet, review log, SHA256 |
| [references_corrected/<hearing_id>/](references_corrected/) | Corrected references for the six hearings the corrections touch |
| [transcripts/<hearing_id>.segments.jsonl](transcripts/) | Our transcript as scored: sequence_number, cluster_id, speaker_label, bioguide_id, text |
| [roster_cache/](roster_cache/) | Committee rosters used to resolve names (correction 1 applied; database queries removed) |
| [prints/prints.json](prints/prints.json) | GovInfo link and SHA-256 for every print; prints/ also holds the three prints GovInfo's mirror alters |
| [audit/](audit/) | The 200-turn audit of agreeing reference turns, and the hand check of 12 surname matches (member_id_review.md) |
| [sampling/](sampling/) | Population, its hash and report, pre-draw exclusions, the drawn sample with its beacon seed |
| [code/](code/) | sampler.py, audit, correction and member-id check scripts, and the scorer (code/scorer/) |
| [media/official-record/official-record-errors.json](media/official-record/official-record-errors.json) | The five wrong-speaker passages in the official record: print hashes, line numbers, quotes, video timestamps; clips and images beside it |
