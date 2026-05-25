from typing import Any, Dict


def fallback_to_baseline_analysis(baseline_analysis: Any) -> Dict[str, Any]:
    if isinstance(baseline_analysis, dict) and baseline_analysis:
        return baseline_analysis
    return {
        "recommendation": "NEUTRAL",
        "signal": "NEUTRAL",
        "indicators": {},
        "weighted_scores": {"buy": 0, "sell": 0, "neutral": 1},
    }

