"""Deterministic taste scoring against the team's learned rules (the LACE "weigh" output).

The LLM is only used afterwards to phrase the explanation; ranking never depends on it,
so the Curator still works when the model is slow or unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Fit:
    asset_id: str
    score: float
    fits: list[str] = field(default_factory=list)  # rule texts the asset satisfies
    breaks: list[str] = field(default_factory=list)  # rule texts the asset breaks
    members: list[str] = field(default_factory=list)  # who taught the rules it fits


def rules_for(rules: list[dict], member_id: str) -> list[dict]:
    """Team rules apply to everyone; personal rules only to their owner; split rules never."""
    out = []
    for r in rules:
        if r["scope"] == "team" or (r["scope"] == "personal" and member_id in r["members"]):
            out.append(r)
    return out


def _check(rule: dict, asset: dict) -> bool | None:
    """True if the asset satisfies the rule, False if it breaks it, None if not applicable."""
    req = rule.get("requires") or {}
    if rule["applies_to"] == "illustration" and asset["kind"] != "illustration":
        return None
    if not req:
        return None
    ok = True
    if "style" in req:
        ok &= asset.get("style") == req["style"]
    if "max_colours" in req:
        ok &= asset.get("colours", 99) <= req["max_colours"]
    if "palette_includes" in req:
        ok &= req["palette_includes"] in asset.get("palette", [])
    return ok


def score_asset(asset: dict, rules: list[dict], member_id: str, budget_cents: int | None, licence: str) -> Fit:
    fit = Fit(asset_id=asset["id"], score=0.0)
    for rule in rules_for(rules, member_id):
        verdict = _check(rule, asset)
        if verdict is None:
            continue
        weight = (rule["kept"] + 1) / (rule["kept"] + rule["undone"] + 2)  # Beta posterior mean
        if verdict:
            fit.score += weight
            fit.fits.append(rule["text"])
            fit.members.extend(m for m in rule["members"] if m not in fit.members)
        else:
            fit.score -= weight
            fit.breaks.append(rule["text"])
    price = asset["prices"].get(licence)
    if price is None:
        fit.score -= 5
    elif budget_cents is not None and price > budget_cents:
        fit.score -= 1.5
        fit.breaks.append("over budget")
    return fit


def rank(catalog: list[dict], kind: str, rules: list[dict], member_id: str, budget_cents: int | None,
         licence: str, limit: int = 4) -> list[Fit]:
    pool = [a for a in catalog if a["kind"] == kind]
    price = {a["id"]: a["prices"].get(licence, 10**9) for a in pool}
    scored = [score_asset(a, rules, member_id, budget_cents, licence) for a in pool]
    # Ties go to the cheaper asset: same taste fit, less of the team's budget.
    scored.sort(key=lambda f: (-round(f.score, 6), price[f.asset_id], f.asset_id))
    return scored[:limit]
