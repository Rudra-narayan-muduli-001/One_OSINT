"""Username permutation generation (blackbird/user-scanner style)."""

from __future__ import annotations

from itertools import permutations


def permute_username(username: str, *, all_variants: bool = False) -> list[str]:
    """Generate username variations.

    Restricted mode (default): only insert separators when the username
    contains at least two word-ish chunks (e.g. ``john.doe`` -> john_doe).
    ``all_variants`` generates everything: reorderings, separator
    substitutions, doubled separators.
    """
    if not username:
        return []
    base = username.replace("_", ".").replace("-", ".").lower()
    parts = [p for p in base.split(".") if p]
    separators = ["", "_", "-", "."]

    variants: set[str] = {username}

    if len(parts) >= 2:
        for sep_combo in separators:
            variants.add(sep_combo.join(parts))
        if all_variants:
            for n_parts in range(2, len(parts) + 1):
                for combo in permutations(parts, n_parts):
                    for sep in separators[1:]:
                        variants.add(sep.join(combo))

    if all_variants and len(parts) == 1:
        variants.add(username + "_")
        variants.add("_" + username)
        variants.add(username + "0")
        variants.add(username + "1")

    ordered: list[str] = sorted(v for v in variants if v)
    return ordered
