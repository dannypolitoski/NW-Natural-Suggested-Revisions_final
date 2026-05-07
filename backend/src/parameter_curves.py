"""
Parameter curve resolution for time-varying scenario inputs.

Any numeric scenario parameter can be overridden with a curve — a set of
(year, value) control points. The model interpolates linearly between points
and holds flat beyond the endpoints.

If a parameter is a plain number, it's returned as-is (backward compatible).
If it's a dict with "points", the curve is resolved for the requested year.
If it's not specified at all, the caller's default is used.

Usage in scenario JSON:
    "electrification_rate": {
        "points": {"2025": 0.02, "2028": 0.04, "2030": 0.06, "2033": 0.05}
    }

This creates a piecewise-linear curve: 2% in 2025, ramps to 4% by 2028,
continues to 6% by 2030, then drops back to 5% by 2033. Any shape you want.
"""

import logging
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)


def _parse_time_key(key) -> float:
    """Parse a time key into a fractional year. Accepts 'YYYY' or 'YYYY-MM'."""
    s = str(key)
    if '-' in s:
        parts = s.split('-')
        year = int(parts[0])
        month = int(parts[1])
        return year + (month - 1) / 12.0
    return float(int(s))


def resolve(param: Any, year: int, default: float = None, month: int = None) -> float:
    """
    Resolve a parameter value for a given year (and optionally month).

    Args:
        param: Either a number (returned as-is), a dict with "points" key
               (interpolated), or None (returns default).
        year: The forecast year to resolve for.
        default: Fallback value if param is None.
        month: Optional month (1-12) for sub-annual resolution.

    Returns:
        The resolved numeric value for this time point.
    """
    # None or missing → use default
    if param is None:
        return default if default is not None else 0.0

    # Plain number → return as-is (backward compatible)
    if isinstance(param, (int, float)):
        return float(param)

    # Dict with "points" → interpolate
    if isinstance(param, dict) and 'points' in param:
        t = year + ((month - 1) / 12.0 if month else 0.0)
        return _interpolate(param['points'], t)

    # Dict without "points" but with year/month keys directly (shorthand)
    if isinstance(param, dict):
        try:
            t = year + ((month - 1) / 12.0 if month else 0.0)
            return _interpolate(param, t)
        except (TypeError, ValueError):
            pass

    # Fallback: try to convert to float
    try:
        return float(param)
    except (TypeError, ValueError):
        return default if default is not None else 0.0


def _interpolate(points: Dict, t: float) -> float:
    """
    Piecewise-linear interpolation between control points.

    Points can use year keys ("2025") or year-month keys ("2025-06").
    Between points: linear interpolation.
    Before first point: hold first value.
    After last point: hold last value.
    """
    # Convert keys to fractional years, sort
    sorted_pts = sorted([(_parse_time_key(k), float(v)) for k, v in points.items()])

    if not sorted_pts:
        return 0.0

    # Before first point
    if t <= sorted_pts[0][0]:
        return sorted_pts[0][1]

    # After last point
    if t >= sorted_pts[-1][0]:
        return sorted_pts[-1][1]

    # Find the two bracketing points and interpolate
    for i in range(len(sorted_pts) - 1):
        t0, v0 = sorted_pts[i]
        t1, v1 = sorted_pts[i + 1]
        if t0 <= t <= t1:
            if t1 == t0:
                return v0
            frac = (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * frac

    return sorted_pts[-1][1]


def describe_curve(param: Any, start_year: int = 2025, end_year: int = 2035) -> str:
    """Return a human-readable description of a parameter curve."""
    if param is None:
        return "not set (using model default)"
    if isinstance(param, (int, float)):
        return f"fixed at {param}"
    if isinstance(param, dict):
        pts = param.get('points', param)
        values = [f"{resolve(param, y):.4f}" for y in range(start_year, end_year + 1)]
        return f"curve: {' → '.join(values)}"
    return str(param)
