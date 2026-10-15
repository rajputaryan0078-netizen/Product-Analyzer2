"""
Scan History Manager — VEDANSHU Product Packet Analyser.

Stores a log of past analyses in Streamlit session state.
Each entry records a summary snapshot — not the full result dict — to keep
memory footprint small.

History is session-scoped (cleared when the browser tab closes).
A future enhancement could persist to disk via JSON or SQLite.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

# Session-state key used to store the history list
HISTORY_KEY = "scan_history"
MAX_HISTORY = 20   # cap to avoid unbounded memory growth


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_snapshot(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds a lightweight summary snapshot from a full analysis result dict.

    Stored fields:
      timestamp       str
      product_name    str
      brand           str
      mrp             str
      health_score    int | None
      grade           str | None
      grade_label     str | None
      grade_color     str
      high_alerts     list[str]    nutrient names with HIGH status
      mod_alerts      list[str]    nutrient names with MODERATE status
      allergens       list[str]    allergen names detected
      ingredient_flags list[str]  flag names raised
      is_demo         bool
    """
    fields   = results.get("fields", {})
    risk     = results.get("risk_analysis", {})
    allergen = results.get("allergen_analysis", {})
    score    = results.get("health_score", {})

    high_alerts = [
        a["nutrient"] for a in risk.get("quantitative_alerts", [])
        if a.get("status") == "HIGH"
    ]
    mod_alerts = [
        a["nutrient"] for a in risk.get("quantitative_alerts", [])
        if a.get("status") == "MODERATE"
    ]
    allergens = [
        a["name"] for a in allergen.get("allergens_found", [])
    ]
    ing_flags = [
        f["name"] for f in risk.get("ingredient_flags", [])
    ]

    return {
        "timestamp":       datetime.now().strftime("%d %b %Y  %H:%M"),
        "product_name":    fields.get("product_name") or "Unknown Product",
        "brand":           fields.get("brand_name")   or "—",
        "mrp":             fields.get("mrp")          or "—",
        "health_score":    score.get("score"),
        "grade":           score.get("grade"),
        "grade_label":     score.get("grade_label"),
        "grade_color":     score.get("color", "#94A3B8"),
        "high_alerts":     high_alerts,
        "mod_alerts":      mod_alerts,
        "allergens":       allergens,
        "ingredient_flags": ing_flags,
        "is_demo":         results.get("is_demo", False),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def init_history(session_state) -> None:
    """Initialises the history list in session_state if not already present."""
    if HISTORY_KEY not in session_state:
        session_state[HISTORY_KEY] = []


def add_to_history(session_state, results: Dict[str, Any]) -> None:
    """
    Appends a snapshot of the current analysis to the history list.
    Automatically caps the list at MAX_HISTORY entries (oldest removed first).
    """
    init_history(session_state)
    snapshot = _make_snapshot(results)
    history: List[Dict[str, Any]] = session_state[HISTORY_KEY]
    # Insert at front (most recent first)
    history.insert(0, snapshot)
    if len(history) > MAX_HISTORY:
        history.pop()
    session_state[HISTORY_KEY] = history


def get_history(session_state) -> List[Dict[str, Any]]:
    """Returns the history list (most recent first)."""
    init_history(session_state)
    return session_state.get(HISTORY_KEY, [])


def clear_history(session_state) -> None:
    """Clears all history entries."""
    session_state[HISTORY_KEY] = []


def has_history(session_state) -> bool:
    """Returns True if there is at least one history entry."""
    return len(get_history(session_state)) > 0
