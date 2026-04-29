import os
import json
import sys
import threading
import traceback
import joblib
import pandas as pd
import numpy as np

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Make sure local core/ imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from main import start_analysis  # noqa: E402

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR  = os.path.join(BASE_DIR, "static")
REPORT_PATH = os.path.join(BASE_DIR, "output", "analysis_report.json")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
CORS(app)

# Track analysis state
_analysis_state = {"running": False, "error": None}

# Load ML Models once on startup
MODEL_PATH = os.path.join(BASE_DIR, "model", "risk_random_forest_model_v3.joblib")
ENCODER_PATH = os.path.join(BASE_DIR, "model", "label_encoder_v3.joblib")
ml_model = None
ml_encoder = None

try:
    if os.path.exists(MODEL_PATH) and os.path.exists(ENCODER_PATH):
        ml_model = joblib.load(MODEL_PATH)
        ml_encoder = joblib.load(ENCODER_PATH)
        print("✅ ML Models loaded successfully!")
    else:
        print("⚠️ ML Models not found in backend_engine/model/")
except Exception as e:
    print(f"⚠️ Error loading ML models: {e}")


# ── Serve the frontend ────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


# ── GET current report ────────────────────────────────────────────────────────
@app.route("/api/report")
def get_report():
    if not os.path.exists(REPORT_PATH):
        return jsonify({"error": "No report found. Run an analysis first."}), 404
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


# ── POST trigger analysis ─────────────────────────────────────────────────────
@app.route("/api/analyze", methods=["POST"])
def analyze():
    global _analysis_state
    if _analysis_state["running"]:
        return jsonify({"error": "Analysis already in progress."}), 409

    data = request.get_json(silent=True) or {}
    repo_url = data.get("repo_url", "").strip()
    if not repo_url:
        return jsonify({"error": "repo_url is required."}), 400

    _analysis_state = {"running": True, "error": None}

    def run():
        global _analysis_state
        try:
            start_analysis(repo_url)
            _analysis_state["running"] = False
        except Exception:
            _analysis_state["running"] = False
            _analysis_state["error"] = traceback.format_exc()

    t = threading.Thread(target=run, daemon=True)
    t.start()

    # Auto-reset after 3 minutes to prevent infinite hangs
    def timeout_guard():
        t.join(timeout=180)
        if _analysis_state["running"]:
            print("⏰ Analysis timed out after 3 minutes — resetting.")
            _analysis_state["running"] = False
            _analysis_state["error"] = "Analysis timed out (3 min). Try a smaller repository."

    threading.Thread(target=timeout_guard, daemon=True).start()

    return jsonify({"status": "started"}), 202


# ── GET analysis status ───────────────────────────────────────────────────────
@app.route("/api/status")
def status():
    return jsonify({
        "running": _analysis_state["running"],
        "error":   _analysis_state["error"],
    })


# ── POST cancel running analysis ──────────────────────────────────────────────
@app.route("/api/cancel", methods=["POST"])
def cancel():
    global _analysis_state
    _analysis_state = {"running": False, "error": None}
    return jsonify({"status": "cancelled"})


# ── GET ML prediction ─────────────────────────────────────────────────────────
@app.route("/api/predict")
def predict_risk():
    if not ml_model or not ml_encoder:
        return jsonify({"error": "ML model not loaded."}), 503
    
    if not os.path.exists(REPORT_PATH):
        return jsonify({"error": "No report found. Run analysis first."}), 404
        
    try:
        with open(REPORT_PATH, "r", encoding="utf-8") as f:
            report = json.load(f)
            
        loc = report.get("total_loc", 0)
        tds = report.get("total_debt_score", 0)
        
        max_cc = 0
        anti_patterns = 0
        duplicate_files = 0
        total_files = max(1, len(report.get("file_details", [])))
        
        for fd in report.get("file_details", []):
            m = fd.get("metrics", {})
            max_cc = max(max_cc, m.get("complexity", 0))
            anti_patterns += len(fd.get("issues", []))
            if "Duplicate Code" in fd.get("issues", []):
                duplicate_files += 1
                
        duplication_percent = (duplicate_files / total_files) * 100
        
        sample = pd.DataFrame(
            [[loc, max_cc, duplication_percent, anti_patterns, tds]],
            columns=["LOC", "Complexity", "DuplicationPercent", "AntiPatterns", "TDS"]
        )
        
        # Fixed bin edges for a single sample prediction since training min/max is lost
        sample["Complexity_bin"] = pd.cut(sample["Complexity"], bins=[-1, 10, 20, 30, 50, 9999], labels=False)
        sample["TDS_bin"] = pd.cut(sample["TDS"], bins=[-1, 20, 50, 100, 200, 99999], labels=False)
        sample = sample.fillna(0)
        
        prediction = ml_model.predict(sample)
        predicted_label = ml_encoder.inverse_transform(prediction)
        
        try:
            probs = ml_model.predict_proba(sample)[0]
            confidence = float(max(probs))
        except Exception:
            confidence = 1.0
            
        return jsonify({
            "risk_label": str(predicted_label[0]),
            "confidence": confidence
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    os.makedirs(os.path.join(BASE_DIR, "output"), exist_ok=True)
    app.run(debug=True, port=5000, use_reloader=False)
