def detect_anti_patterns(metrics):
    """
    Applies rules from the SRS/PDF to detect anti-patterns.
    Returns a list of detected issues and a calculated Debt Score.
    """
    detected_patterns = []
    debt_score = 0
    
    loc = metrics['loc']
    methods = metrics['methods']
    complexity = metrics['complexity']

    # --- RULES FROM PDF ---

    # 1. Long Method (Weight: 2)
    # [cite_start]Rule: if loc > 50 [cite: 64] (Note: usually applied per method, but using file avg for MVP)
    # Let's assume we flag files with HIGH average LOC per method or total LOC for now
    if loc > 200: # Adjusted for file-level (or use per-method logic)
        detected_patterns.append("Long Method / Large File")
        debt_score += 2

    # 2. Large Class (Weight: 3)
    # [cite_start]Rule: methods > 15 [cite: 71]
    if methods > 15:
        detected_patterns.append("Large Class")
        debt_score += 3

    # 3. God Class (Weight: 5)
    # [cite_start]Rule: loc > 300 AND methods > 20 [cite: 82]
    if loc > 300 and methods > 20:
        detected_patterns.append("God Class")
        debt_score += 5

    # 4. High Complexity (Weight: 4)
    # [cite_start]Rule: Cyclomatic Complexity > 10 [cite: 91]
    if complexity > 10:
        detected_patterns.append("High Complexity")
        debt_score += 4

    # 5. Duplicate Code (Weight: 3)
    # [cite_start]Rule: > 15% [cite: 100]
    # (This requires cross-file analysis, we will skip for this specific function)

    return detected_patterns, debt_score