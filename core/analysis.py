import radon.complexity as radon_cc
import radon.raw as radon_raw

def analyze_file_metrics(code_content):
    """
    Analyzes a single Python file and returns:
    - LOC (Lines of Code)
    - Complexity (Cyclomatic Complexity)
    - Methods (Count)
    """
    try:
        # 1. Get Raw Metrics (LOC)
        raw = radon_raw.analyze(code_content)
        loc = raw.loc
        
        # 2. Get Complexity Metrics (Cyclomatic Complexity)
        complexity_blocks = radon_cc.cc_visit(code_content)
        
        # Calculate Average/Max Complexity and Method Count
        if complexity_blocks:
            # Sum complexity of all top-level blocks
            total_cc = sum([block.complexity for block in complexity_blocks])
            max_cc = max([block.complexity for block in complexity_blocks])
            avg_cc = total_cc / len(complexity_blocks)
            
            # FIXED: Correct way to count methods/functions in Radon
            method_count = 0
            for block in complexity_blocks:
                block_type = type(block).__name__ # Get class name 'Function', 'Class', etc.
                
                if block_type == 'Function':
                    method_count += 1
                elif block_type == 'Class':
                    # Classes contain methods, add them to the count
                    # 'methods' is a list of Function objects inside the Class
                    real_methods = getattr(block, 'methods', []) 
                    method_count += len(real_methods)
                    
                    # Update Max CC if a method inside the class is very complex
                    if real_methods:
                        max_inner_cc = max([m.complexity for m in real_methods])
                        max_cc = max(max_cc, max_inner_cc)

        else:
            max_cc = 0
            avg_cc = 0
            method_count = 0

        return {
            "loc": loc,
            "complexity": max_cc,  # Max complexity (Risk Indicator)
            "avg_complexity": avg_cc,
            "methods": method_count
        }

    except SyntaxError:
        return None  # Skip files with syntax errors
    except Exception as e:
        print(f"⚠️ Error analyzing file: {e}")
        return None