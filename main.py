import os
import json
from core.git_utils import clone_repo
from core.analysis import analyze_file_metrics
from core.detector import detect_anti_patterns
from core.duplicate_detector import detect_duplicate_files   # NEW

DUPLICATE_WEIGHT = 3   # debt points per spec
MAX_FILES = 300        # cap to keep analysis fast
DUP_FILE_LIMIT = 150   # skip O(n²) dup detection above this count


def start_analysis(repo_url):
    # 1. Clone the Repo
    local_path = clone_repo(repo_url)
    if not local_path:
        return

    results = []
    total_loc = 0

    # Collect raw source so we can run cross-file duplicate detection later
    file_codes   = {}   # { filename: source_code }
    file_results = {}   # { filename: result_dict }  (keyed by basename)

    print(f"🔍 Analyzing files in {local_path}...")

    # 2. Walk through files & run per-file analysis
    py_files = []
    for root, dirs, files in os.walk(local_path):
        # Skip hidden / vendor dirs to save time
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'node_modules', '.git')]
        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))

    # Cap to MAX_FILES
    if len(py_files) > MAX_FILES:
        print(f"⚠️  Large repo: capping at {MAX_FILES}/{len(py_files)} files for speed.")
        py_files = py_files[:MAX_FILES]

    for full_path in py_files:
        file = os.path.basename(full_path)
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()

        # 3. Analyze per-file metrics
        metrics = analyze_file_metrics(code)
        if not metrics:
            continue

        total_loc += metrics["loc"]

        # 4. Per-file anti-pattern detection (Long Method, God Class, etc.)
        issues, score = detect_anti_patterns(metrics)

        # Store source for cross-file pass
        file_codes[file] = code

        entry = {
            "filename":   file,
            "path":       full_path,
            "metrics":    metrics,
            "issues":     issues,
            "debt_score": score,
        }
        results.append(entry)
        file_results[file] = entry   # keep a reference for later update

    # 5. Cross-file Duplicate Code detection  (weight 3, threshold 15 %)
    #    Skip for large repos — O(n²) is too slow above DUP_FILE_LIMIT
    if len(file_codes) > DUP_FILE_LIMIT:
        print(f"⚠️  Skipping duplicate detection ({len(file_codes)} files > limit {DUP_FILE_LIMIT}).")
        dup_map = {}
    else:
        print("🔁 Running cross-file duplicate code detection…")
        dup_map = detect_duplicate_files(file_codes, threshold=0.15)

    for fname, dup_info in dup_map.items():
        if fname not in file_results:
            continue
        entry = file_results[fname]

        # Only add the label once per file
        if "Duplicate Code" not in entry["issues"]:
            entry["issues"].append("Duplicate Code")
            entry["debt_score"] += DUPLICATE_WEIGHT

        # Attach duplicate metadata for the report
        entry["duplicate_of"]       = dup_info["duplicates"]
        entry["duplicate_similarity"] = dup_info["max_similarity"]

    # 6. Compute total debt & TDI
    total_debt_score = sum(e["debt_score"] for e in results)

    tdi_score = (total_debt_score / total_loc * 1000) if total_loc > 0 else 0

    # 7. Save report
    output_data = {
        "project_url":    repo_url,
        "total_loc":      total_loc,
        "total_debt_score": total_debt_score,
        "normalized_tdi": round(tdi_score, 2),
        "files_analyzed": len(results),
        "file_details":   results,
    }

    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "output", "analysis_report.json"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=4)

    print(f"\n✅ Analysis Complete!")
    print(f"💰 Total Debt Score : {total_debt_score}")
    print(f"📉 Normalized TDI   : {round(tdi_score, 2)}")
    print(f"🔁 Duplicate files  : {len(dup_map)}")
    print(f"📂 Report saved to  : {output_path}")


if __name__ == "__main__":
    test_url = "https://github.com/psf/requests"
    start_analysis(test_url)