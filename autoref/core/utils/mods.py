from aiosu.models.mods import Mods

def canonical_mods(mods) -> list[str]:
    """Normalize mod input → sorted list of 2-char tokens, NF excluded.

    Accepts: aiosu Mods instance, str like "HDHR" / "HD HR", iterable of tokens.
    """
    if mods is None:
        return []
    if isinstance(mods, str):
        s = mods.replace(" ", "")
        toks = [s[i:i + 2].upper() for i in range(0, len(s), 2) if s[i:i + 2]]
    else:
        toks = []
        for m in mods:
            if hasattr(m, "value") or hasattr(m, "name"):
                toks.append(getattr(m, "short_name", None) or m.name if hasattr(m, "name") else str(m))
            else:
                toks.append(str(m))
        toks = [t.upper() for t in toks if t]
    return sorted(t for t in toks if t and t != "NF")
