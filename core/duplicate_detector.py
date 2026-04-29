"""
duplicate_detector.py
─────────────────────
Cross-file duplicate code detection using Jaccard similarity on line-level
k-gram shingles.

Algorithm
---------
1.  Normalize every file: strip whitespace, drop blank lines & pure comments.
2.  Build a set of overlapping 3-line "shingles" (n-grams) per file.
3.  For every pair of files compute:
        Jaccard(A, B) = |A ∩ B| / |A ∪ B|
4.  If Jaccard > threshold (default 0.15 → 15 %) both files are flagged as
    containing "Duplicate Code" and receive a debt weight of +3.

Returns
-------
detect_duplicate_files(file_codes, threshold)
    file_codes : dict  { filename: source_code_string }
    threshold  : float (default 0.15)
    → dict  { filename: {"duplicates": [...], "max_similarity": float} }
      Only files that exceed the threshold appear in the result.
"""

from itertools import combinations


# ── helpers ──────────────────────────────────────────────────────────────────

def _normalize_lines(code: str) -> list:
    """
    Return a list of 'meaningful' lines:
      - stripped of leading/trailing whitespace
      - blank lines removed
      - pure comment lines removed
    """
    result = []
    for line in code.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            result.append(stripped)
    return result


def _shingles(lines: list, k: int = 3) -> set:
    """
    Build a set of k-line overlapping n-grams (shingles).
    Falls back to individual lines when the file has fewer than k lines.
    """
    if len(lines) < k:
        return set(tuple(lines))          # tiny file: whole file is one shingle
    return {tuple(lines[i : i + k]) for i in range(len(lines) - k + 1)}


def _jaccard(set_a: set, set_b: set) -> float:
    """Jaccard similarity in [0.0, 1.0]."""
    if not set_a or not set_b:
        return 0.0
    union = set_a | set_b
    return len(set_a & set_b) / len(union)


# ── public API ────────────────────────────────────────────────────────────────

def detect_duplicate_files(file_codes: dict, threshold: float = 0.15) -> dict:
    """
    Parameters
    ----------
    file_codes : dict
        Mapping of  { filename: source_code_string }  for every .py file.
    threshold : float
        Jaccard similarity above which two files are considered duplicates.
        Default is 0.15 (15 %) matching the project spec.

    Returns
    -------
    dict
        { filename: { "duplicates": [other_filename, ...],
                      "max_similarity": float (0-100 %) } }
        Only files that are flagged (similarity > threshold) are included.
    """
    # 1. Build shingle sets for every file
    shingle_map = {}
    for fname, code in file_codes.items():
        lines = _normalize_lines(code)
        shingle_map[fname] = _shingles(lines)

    # 2. Compare every pair
    similarity_hits = {fname: {"duplicates": [], "max_similarity": 0.0}
                       for fname in file_codes}

    for f1, f2 in combinations(file_codes.keys(), 2):
        sim = _jaccard(shingle_map[f1], shingle_map[f2])
        if sim > threshold:
            pct = round(sim * 100, 1)
            similarity_hits[f1]["duplicates"].append(f2)
            similarity_hits[f1]["max_similarity"] = max(
                similarity_hits[f1]["max_similarity"], pct
            )
            similarity_hits[f2]["duplicates"].append(f1)
            similarity_hits[f2]["max_similarity"] = max(
                similarity_hits[f2]["max_similarity"], pct
            )

    # 3. Return only files that were actually flagged
    return {
        fname: info
        for fname, info in similarity_hits.items()
        if info["duplicates"]
    }
