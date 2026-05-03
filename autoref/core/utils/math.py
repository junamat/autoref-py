from .mods import canonical_mods

def apply_score_multiplier(score: int | float, mods, multipliers: dict[str, float] | None) -> float:
    """Apply mod multipliers to a raw score.

    Resolution: exact-combo key (sorted concat e.g. "HDHR") wins; otherwise the
    score is multiplied by each per-mod entry cumulatively. Missing mods → 1.0.
    Returns the adjusted score (float — caller rounds/casts as needed).
    """
    if not multipliers or score is None:
        return float(score) if score is not None else 0.0
    toks = canonical_mods(mods)
    if not toks:
        return float(score)
    combo_key = "".join(toks)
    if combo_key in multipliers:
        return float(score) * float(multipliers[combo_key])
    out = float(score)
    for t in toks:
        if t in multipliers:
            out *= float(multipliers[t])
    return out

def merge_multipliers(*dicts: "dict[str, float] | None") -> dict[str, float]:
    """Merge multiplier dicts; later overrides earlier, per-key."""
    out: dict[str, float] = {}
    for d in dicts:
        if d:
            out.update(d)
    return out
