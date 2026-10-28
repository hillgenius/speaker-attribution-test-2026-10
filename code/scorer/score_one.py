import json
import re
import sys
import unicodedata
from pathlib import Path


from bs4 import BeautifulSoup
from jiwer import process_words


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("`", "'")
    # Fold accented Latin letters to their base form (e.g. "Luján" -> "lujan")
    # before the ASCII-only strip below, so a name that differs from GPO's
    # print only by a diacritic still matches instead of losing letters.
    # NFKD is compatibility decomposition, not just accent-stripping: it also
    # expands ligatures ("ﬁnal" -> "final", one token, unchanged) and
    # compatibility forms like vulgar fractions ("½" -> "1⁄2", which the
    # ASCII strip below then splits into the two separate tokens "1" and
    # "2" -- previously "½" had no ASCII representation at all and was
    # silently dropped, losing the word entirely).
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9']+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def gpo_spoken_text(path: Path) -> str:
    soup = BeautifulSoup(path.read_text(), "html.parser")
    raw = soup.get_text("\n")
    start = raw.index("Mr. Biggs. The Subcommittee will come to order.")
    end_marker = "With that, we are adjourned."
    end = raw.index(end_marker, start) + len(end_marker)
    body = raw[start:end]
    # Repair GPO's print-layout word wrapping (e.g. "thought-\nprovoking").
    body = re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", "", body)
    spoken = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("["):
            continue
        if line.upper() == line and len(line) < 160:
            continue
        line = re.sub(
            r"^(?:Mr|Ms|Mrs|Dr)\. [A-Z][A-Za-z'’-]*\.\s+|^All\.\s+",
            "",
            line,
        )
        spoken.append(line)
    return " ".join(spoken)


def hillgenius_text(path: Path) -> str:
    segments = json.loads(path.read_text())
    return " ".join(s.get("text", "") for s in segments)


if __name__ == "__main__":
    reference = normalize(gpo_spoken_text(Path(sys.argv[1])))
    hypothesis = normalize(hillgenius_text(Path(sys.argv[2])))
    result = process_words(reference, hypothesis)
    print(json.dumps({
        "reference_words": result.hits + result.substitutions + result.deletions,
        "hypothesis_words": result.hits + result.substitutions + result.insertions,
        "hits": result.hits,
        "substitutions": result.substitutions,
        "deletions": result.deletions,
        "insertions": result.insertions,
        "wer": result.wer,
        "word_accuracy_one_minus_wer": 1 - result.wer,
    }, indent=2))
