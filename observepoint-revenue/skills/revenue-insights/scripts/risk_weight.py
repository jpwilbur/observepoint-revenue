"""Risk-weighting: apply a health-based weight to an amount (the 'undetermined' renewal
bucket). Weights live in the metrics canon / are passed in; nothing is hardcoded here."""


def risk_weighted(amount, health, weights):
    """amount * weights[health] (health matched case-insensitively). Missing health or
    amount -> 0.0. `weights` e.g. {'red': 0.25, 'yellow': 0.5}."""
    if amount is None:
        return 0.0
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        return 0.0
    w = weights.get(str(health or "").strip().lower())
    return amt * w if w is not None else 0.0
